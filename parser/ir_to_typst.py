"""
ir_to_typst.py  v0.2
---------------------
- 读取 IR JSON + 学校 config yaml + 论文 meta yaml
- 生成调用 core.typ::thesis(config:, meta:, body) 的 main.typ
- 处理"无编号章节"（致谢、参考文献）→ 用 #unnumbered-heading 渲染
- 列表识别（用 ordered 字段）
"""

from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import yaml


import re as _re_math

# 公式段保护：$$...$$ (display) 和 $...$ (inline) 整段不转义
_MATH_BLOCK_RE = _re_math.compile(r"\$\$.+?\$\$|\$[^\$\n]+?\$", _re_math.DOTALL)


def escape_typst(text: str) -> str:
    """Typst 转义。
    - 公式段（$...$ 或 $$...$$）整段透传（Typst 数学语法兼容大部分简单 LaTeX）
    - 非公式段：转义 # < > \\，保留 @ 用于引用
    """
    # 切分：保护公式段，仅对其余部分做转义
    out = []
    last = 0
    for m in _MATH_BLOCK_RE.finditer(text):
        out.append(_escape_text_only(text[last:m.start()]))
        out.append(m.group(0))   # 公式段原样保留
        last = m.end()
    out.append(_escape_text_only(text[last:]))
    return "".join(out)


def _escape_text_only(text: str) -> str:
    """对非公式文本做 Typst 转义。"""
    text = text.replace("\\", "\\\\")
    for ch in ["#", "<", ">"]:
        text = text.replace(ch, "\\" + ch)
    # 把孤立的 $（不成对的）也转义掉，避免歧义
    text = text.replace("$", "\\$")
    return text


UNNUMBERED_PATTERNS = [
    re.compile(r"^(参考文献|References)$", re.I),
    re.compile(r"^(致\s*谢|Acknowledge?ments?)$", re.I),
    re.compile(r"^(附\s*录[A-Z]?|Appendix\s*[A-Z]?)$", re.I),
]

SECTION_PATTERNS = {
    "abstract_cn":  re.compile(r"^摘\s*要$"),
    "abstract_en":  re.compile(r"^Abstract$", re.I),
    "keywords_cn":  re.compile(r"^关键词[：: ]"),
    "keywords_en":  re.compile(r"^Keywords?[：: ]", re.I),
}


def is_unnumbered(title: str) -> bool:
    return any(p.match(title.strip()) for p in UNNUMBERED_PATTERNS)


def transform_bracket_citations(text: str) -> str:
    """把正文里的中括号引用 `[1]`, `[2, 3]`, `[1-3]` 转换为 Typst 的 @refN 形式。
    关键：避免误伤"图表名 [1]"或文献条目本身的 [1]——本函数只在正文渲染时调用，
    参考文献章节已被 ir_to_typst 跳过，所以是安全的。
    """
    def expand(m):
        inside = m.group(1)
        keys = []
        for part in inside.split(","):
            part = part.strip()
            if not part:
                continue
            range_m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
            if range_m:
                a, b = int(range_m.group(1)), int(range_m.group(2))
                if 1 <= a <= b <= 999:
                    keys.extend(f"ref{i}" for i in range(a, b + 1))
                else:
                    return m.group(0)
            elif part.isdigit():
                keys.append(f"ref{int(part)}")
            else:
                return m.group(0)
        if not keys:
            return m.group(0)
        return "".join(f"@{k}" for k in keys)

    return re.sub(r"\[(\d[\d,\s\-–]*)\]", expand, text)


# 全局开关：仅在有参考文献来源时才转换中括号引用，
# 否则用户写 [1] 会被 Typst 当成不存在的标签报错。
_BRACKET_TRANSFORM_ENABLED = True


def _maybe_transform(text: str) -> str:
    return transform_bracket_citations(text) if _BRACKET_TRANSFORM_ENABLED else text


def render_block(b: dict) -> str:
    kind = b["kind"]
    text = b.get("text", "")
    if kind == "heading":
        clean = re.sub(r"^(第[一二三四五六七八九十百零\d]+章\s*|[\d.]+\s+)", "", text).strip()
        if b["level"] == 1 and is_unnumbered(clean):
            return f'#unnumbered-heading("{escape_typst(clean)}")'
        return "=" * b["level"] + " " + escape_typst(clean)
    if kind == "para":
        return _maybe_transform(escape_typst(text))
    if kind == "list_item":
        marker = "+" if b.get("ordered") else "-"
        return f"{marker} {_maybe_transform(escape_typst(text))}"
    if kind == "equation":
        body = text.strip()
        return f"$ {body} $"
    if kind == "figure":
        img = b.get("image_path", "")
        cap = escape_typst(b.get("caption") or "图")
        return (
            f'#figure(\n'
            f'  image("{img}", width: 80%),\n'
            f'  caption: [{cap}],\n'
            f")"
        )
    if kind == "table":
        rows = b.get("rows") or []
        if not rows:
            return ""
        ncols = max(len(r) for r in rows)
        cells = []
        for row in rows:
            for cell in row:
                cells.append(f"[{escape_typst(cell)}]")
            for _ in range(ncols - len(row)):
                cells.append("[]")
        return (
            f"#figure(\n"
            f"  table(\n"
            f"    columns: {ncols},\n"
            f"    align: center,\n"
            f"    {', '.join(cells)}\n"
            f"  ),\n"
            f"  caption: [表]\n"
            f")"
        )
    return ""


def split_special_sections(blocks: list[dict]) -> dict:
    sections = {
        "abstract_cn": [], "abstract_en": [],
        "keywords_cn": "", "keywords_en": "",
        "body": [],
    }
    mode = "body"
    for b in blocks:
        text = b.get("text", "").strip()
        if b["kind"] == "para" and SECTION_PATTERNS["abstract_cn"].match(text):
            mode = "abstract_cn"; continue
        if b["kind"] == "para" and SECTION_PATTERNS["abstract_en"].match(text):
            mode = "abstract_en"; continue
        if b["kind"] == "para" and SECTION_PATTERNS["keywords_cn"].match(text):
            sections["keywords_cn"] = re.sub(r"^关键词[：: ]\s*", "", text); mode = "body"; continue
        if b["kind"] == "para" and SECTION_PATTERNS["keywords_en"].match(text):
            sections["keywords_en"] = re.sub(r"^Keywords?[：: ]\s*", "", text, flags=re.I); mode = "body"; continue
        if b["kind"] == "heading":
            mode = "body"
        if mode in ("abstract_cn", "abstract_en"):
            sections[mode].append(b)
        else:
            sections["body"].append(b)
    return sections


def _to_typst_value(v):
    if v is None: return "none"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str):
        s = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'
    if isinstance(v, (list, tuple)):
        items = ", ".join(_to_typst_value(x) for x in v)
        return f"({items}{',' if len(v) == 1 else ''})"
    if isinstance(v, dict):
        items = [f'"{k}": {_to_typst_value(val)}' for k, val in v.items()]
        return "(" + ", ".join(items) + ")"
    return f'"{str(v)}"'


def render_typst(ir: dict, school_config: dict, paper_meta: dict, core_rel: str) -> str:
    sections = split_special_sections(ir["blocks"])

    abs_cn_paras = [escape_typst(b["text"]) for b in sections["abstract_cn"] if b["kind"] == "para"]
    abs_en_paras = [escape_typst(b["text"]) for b in sections["abstract_en"] if b["kind"] == "para"]
    abs_cn = "\n\n".join(abs_cn_paras) or "（摘要内容缺失）"
    abs_en = "\n\n".join(abs_en_paras) or "(Abstract missing)"

    kw_cn = [k.strip() for k in re.split(r"[；;,，]", sections["keywords_cn"]) if k.strip()] \
            or paper_meta.get("keywords_cn", ["关键词"])
    kw_en = [k.strip() for k in re.split(r"[;,，]", sections["keywords_en"]) if k.strip()] \
            or paper_meta.get("keywords_en", ["keyword"])

    meta_dict = {
        "title_cn":    paper_meta.get("title_cn") or ir["meta"].get("title_guess") or "本科毕业论文",
        "title_en":    paper_meta.get("title_en", ""),
        "author":      paper_meta.get("author") or ir["meta"].get("author_guess") or "佚名",
        "student_id":  str(paper_meta.get("student_id", "")),
        "school":      paper_meta.get("school") or school_config.get("school_name", ""),
        "department":  paper_meta.get("department", ""),
        "major":       paper_meta.get("major", ""),
        "advisor":     paper_meta.get("advisor", ""),
        "advisor_title": paper_meta.get("advisor_title", "教授"),
        "date":        paper_meta.get("date", ""),
        "keywords_cn": kw_cn,
        "keywords_en": kw_en,
    }

    # 参考文献：如果用户提供了 bibliography_path，遇到"参考文献"章节时
    # 不渲染原文里手写的 [1][2][3]，而是调用 #cn-bibliography
    bib_path = paper_meta.get("bibliography_path")
    bib_style = (school_config.get("bibliography") or {}).get("style", "gb-7714-2015-numeric")

    # 没有参考文献来源时关闭 [N] 中括号转换，避免 [1] 被转成不存在的 @ref1 报错
    global _BRACKET_TRANSFORM_ENABLED
    _BRACKET_TRANSFORM_ENABLED = bool(bib_path)

    body_parts = []
    skip_until_next_h1 = False
    for b in sections["body"]:
        if b["kind"] == "heading" and b["level"] == 1:
            clean = re.sub(r"^(第[一二三四五六七八九十百零\d]+章\s*|[\d.]+\s+)", "", b["text"]).strip()
            if bib_path and re.match(r"^(参考文献|References)$", clean, re.I):
                # 用 cn-bibliography 替代
                body_parts.append(
                    f'#cn-bibliography("{bib_path}", style: "{bib_style}", title: "{clean}")'
                )
                skip_until_next_h1 = True
                continue
            else:
                skip_until_next_h1 = False
        if skip_until_next_h1:
            continue
        rendered = render_block(b)
        if rendered:
            body_parts.append(rendered)

    body_typst = "\n\n".join(body_parts)

    config_lit = _to_typst_value(school_config)
    meta_lit = _to_typst_value(meta_dict)

    return f'''#import "{core_rel}": thesis, unnumbered-heading, cn-bibliography

#let school_config = {config_lit}

#let paper_meta = {meta_lit} + (
  abstract_cn: [
{abs_cn}
  ],
  abstract_en: [
{abs_en}
  ],
)

#show: thesis.with(
  config: school_config,
  meta: paper_meta,
)

{body_typst}
'''


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: ir_to_typst.py <ir.json> <school_config.yaml> <paper_meta.yaml> <out.typ> [core_rel]")
        sys.exit(1)
    ir = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    school_config = yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8")) or {}
    paper_meta = yaml.safe_load(Path(sys.argv[3]).read_text(encoding="utf-8")) or {}
    core_rel = sys.argv[5] if len(sys.argv) > 5 else "core.typ"
    src = render_typst(ir, school_config, paper_meta, core_rel)
    Path(sys.argv[4]).write_text(src, encoding="utf-8")
    print(f"Typst source written: {sys.argv[4]}")
