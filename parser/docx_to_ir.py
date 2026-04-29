"""
docx_to_ir.py
---------------
解析 docx 提取语义结构，丢弃所有原始格式。
输出统一的中间表示（IR）：纯结构化 JSON，供 Typst 模板渲染。

设计原则：
  - 只识别 "是什么"（标题/段落/列表/表格/图），不关心 "长什么样"
  - 标题层级按 Word 内置 Heading 1/2/3 样式判断（用户不按规范用样式 → lint 报错）
  - 表格、图片、公式做兜底解析；公式 OMML 转 Typst 是后续工作
"""

from __future__ import annotations
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Any

from docx import Document
from docx.document import Document as _Doc
from docx.oxml.ns import qn
from docx.table import Table as _Table
from docx.text.paragraph import Paragraph as _Para


@dataclass
class Block:
    kind: str                      # "heading" | "para" | "list_item" | "table" | "figure" | "equation" | "raw"
    level: int = 0                 # 标题层级（1/2/3）；列表层级
    text: str = ""
    rows: list[list[str]] | None = None      # 表格用
    image_path: str | None = None            # 图片用（导出后的相对路径）
    caption: str = ""
    ordered: bool = False                    # 列表用
    meta: dict = field(default_factory=dict)


def iter_block_items(parent: _Doc):
    """按文档顺序遍历段落和表格（python-docx 默认 API 不保序）。"""
    if isinstance(parent, _Doc):
        body = parent.element.body
    else:
        body = parent._element
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield _Para(child, parent)
        elif child.tag == qn("w:tbl"):
            yield _Table(child, parent)


HEADING_STYLE_RE = re.compile(r"^Heading\s+(\d+)$", re.IGNORECASE)
LIST_STYLE_HINT = ("List", "list")


def detect_heading_level(p: _Para) -> int:
    style = p.style.name if p.style else ""
    m = HEADING_STYLE_RE.match(style)
    if m:
        return int(m.group(1))
    # 中文 Word 常见的"标题 1 / 标题 2"
    cm = re.match(r"^标题\s*(\d+)$", style)
    if cm:
        return int(cm.group(1))
    return 0


def detect_list(p: _Para) -> tuple[bool, bool]:
    """返回 (is_list, is_ordered)。
    优先用 numPr 检测（最准），找不到则回退到样式名匹配。
    """
    style_name = p.style.name if p.style else ""
    is_bullet_by_name = ("Bullet" in style_name) or ("项目符号" in style_name)
    is_number_by_name = ("Number" in style_name) or ("List Paragraph" == style_name) \
                        or ("编号" in style_name) or ("List 2" == style_name)
    has_numPr = False
    pPr = p._p.find(qn("w:pPr"))
    if pPr is not None:
        has_numPr = pPr.find(qn("w:numPr")) is not None
    if has_numPr or is_bullet_by_name or is_number_by_name:
        ordered = not is_bullet_by_name
        return True, ordered
    return False, False


def extract_images(doc: _Doc, output_dir: Path) -> dict[str, str]:
    """提取所有内嵌图片到 output_dir/images/，返回 rId → 相对路径 的映射。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    img_dir = output_dir / "images"
    img_dir.mkdir(exist_ok=True)
    mapping = {}
    for rel_id, rel in doc.part.rels.items():
        if "image" in rel.target_ref:
            ext = Path(rel.target_ref).suffix or ".png"
            target = img_dir / f"img_{rel_id}{ext}"
            target.write_bytes(rel.target_part.blob)
            mapping[rel_id] = f"images/{target.name}"
    return mapping


def get_para_image_rids(p: _Para) -> list[str]:
    """段落里的内嵌图片 rId 列表。"""
    rids = []
    for blip in p._p.iter(qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        if rid:
            rids.append(rid)
    return rids


# ============ OMML 公式处理（通过 pandoc） ============

OMML_PLACEHOLDER = "\u0001OMML_{idx}\u0001"  # 用控制字符当 sentinel，避免与正文冲突


def get_para_omml_count(p: _Para) -> int:
    """段落里的 OMML 数学块数量（包括 oMath 和 oMathPara）。"""
    return len(p._p.findall(".//" + qn("m:oMath")))


def is_para_display_math(p: _Para) -> bool:
    """段落是否是 m:oMathPara（块级公式独占段落）。"""
    return p._p.find(".//" + qn("m:oMathPara")) is not None


def extract_all_formulas_typst(docx_path: Path) -> list[str]:
    """用 Pandoc 抽出 docx 中所有公式（按文档顺序），返回 Typst 数学语法字符串列表。
    若 pandoc 不可用，返回空列表（降级：占位符保留为可见标签）。
    """
    if not shutil.which("pandoc"):
        return []
    try:
        # Step 1: docx → pandoc JSON AST
        proc = subprocess.run(
            ["pandoc", str(docx_path), "-t", "json"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        ast = json.loads(proc.stdout)
    except Exception as e:
        print(f"[OMML] pandoc 提取 JSON 失败: {e}", file=sys.stderr)
        return []

    # Step 2: 递归遍历 AST 收集 Math 节点（按文档顺序）
    formulas_latex: list[tuple[str, str]] = []  # [(kind, tex), ...]

    def walk(node):
        if isinstance(node, dict):
            t = node.get("t")
            if t == "Math":
                kind = node["c"][0]["t"]   # InlineMath / DisplayMath
                tex = node["c"][1]
                formulas_latex.append((kind, tex))
            else:
                for v in node.values():
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ast)

    if not formulas_latex:
        return []

    # Step 3: 把所有 LaTeX 公式合并成单个 markdown，让 pandoc 一次转 typst
    # 用 \n\n 分隔便于回切；display math 用 $$，inline 用 $
    md_parts = []
    for kind, tex in formulas_latex:
        if kind == "DisplayMath":
            md_parts.append(f"$${tex}$$")
        else:
            md_parts.append(f"${tex}$")
    md_doc = "\n\n".join(md_parts)

    try:
        proc = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "typst"],
            input=md_doc, capture_output=True, text=True, check=True, timeout=30,
        )
    except Exception as e:
        print(f"[OMML] pandoc 转 typst 失败: {e}", file=sys.stderr)
        return []

    typst_out = proc.stdout
    # 从 typst 输出按段落切回（pandoc 把每行公式独立成段）
    typst_segments = [seg.strip() for seg in typst_out.split("\n\n") if seg.strip()]

    # 数量必须对齐——否则只能放弃，按原数量返回空段
    if len(typst_segments) != len(formulas_latex):
        # 尝试按 $...$ 段提取
        pattern = re.compile(r"\$[^\$]+?\$|\$\s.*?\s\$", re.DOTALL)
        re_segments = pattern.findall(typst_out)
        if len(re_segments) == len(formulas_latex):
            typst_segments = re_segments
        else:
            print(f"[OMML] 数量不齐：pandoc 给出 {len(typst_segments)} 段，期望 {len(formulas_latex)} 段", file=sys.stderr)
            return []

    return typst_segments


def parse_docx(docx_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    docx_path = Path(docx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = Document(str(docx_path))
    img_map = extract_images(doc, output_dir)

    # 公式提取：按整个文档顺序拿到所有公式的 Typst 字符串
    all_formulas = extract_all_formulas_typst(docx_path)
    formula_idx = [0]   # 用列表当可变指针，闭包内修改

    def take_n_formulas(n: int) -> list[str]:
        nonlocal_idx = formula_idx[0]
        out = all_formulas[nonlocal_idx:nonlocal_idx + n] if all_formulas else []
        formula_idx[0] = nonlocal_idx + n
        return out

    blocks: list[Block] = []

    for item in iter_block_items(doc):
        if isinstance(item, _Para):
            # 公式处理优先于其他判断
            n_omml = get_para_omml_count(item)
            display_only = is_para_display_math(item) and not item.text.strip()

            if n_omml > 0 and display_only:
                # 块级独立公式段
                seg = take_n_formulas(n_omml)
                for s in seg:
                    body = s.strip()
                    # pandoc 输出形如 "$ ... $"（块级用单 $ 包但 Typst 块级是 $ 内空格）
                    # 确保块级形态：$ ... $
                    body = re.sub(r"^\$+|\$+$", "", body).strip()
                    blocks.append(Block(kind="equation", text=body, meta={"display": True}))
                continue

            text = item.text.strip()
            rids = get_para_image_rids(item)
            if rids:
                for rid in rids:
                    if rid in img_map:
                        blocks.append(Block(kind="figure", image_path=img_map[rid]))
                if text:
                    if re.match(r"^(图|Figure|Fig\.?)\s*\d", text):
                        if blocks and blocks[-1].kind == "figure":
                            blocks[-1].caption = text
                            continue
                continue

            if not text and n_omml == 0:
                continue

            # 行内公式插入：把段落 OMML 替换为 sentinel，再插入对应 Typst
            if n_omml > 0:
                # python-docx 的 .text 不包含 m:oMath（默认丢弃），所以要重组段落文本
                rebuilt = _rebuild_para_text_with_formulas(item, take_n_formulas(n_omml))
                level = detect_heading_level(item)
                if level:
                    blocks.append(Block(kind="heading", level=level, text=rebuilt))
                else:
                    blocks.append(Block(kind="para", text=rebuilt))
                continue

            level = detect_heading_level(item)
            if level:
                blocks.append(Block(kind="heading", level=level, text=text))
                continue
            is_list, ordered = detect_list(item)
            if is_list:
                blocks.append(Block(kind="list_item", text=text, ordered=ordered))
                continue
            blocks.append(Block(kind="para", text=text))
        elif isinstance(item, _Table):
            rows = [[cell.text.strip() for cell in row.cells] for row in item.rows]
            blocks.append(Block(kind="table", rows=rows))

    title_guess = doc.core_properties.title or ""
    if not title_guess:
        for b in blocks:
            if b.kind == "heading" and b.level == 1:
                title_guess = b.text
                break

    return {
        "source": str(docx_path.name),
        "meta": {
            "title_guess": title_guess,
            "author_guess": doc.core_properties.author or "",
            "n_formulas": len(all_formulas),
        },
        "blocks": [asdict(b) for b in blocks],
    }


def _rebuild_para_text_with_formulas(p: _Para, formulas: list[str]) -> str:
    """重组段落文本：按 docx XML 顺序遍历 w:r 和 m:oMath，把行内公式插入到正确位置。
    formulas 是已经转好的 Typst 字符串列表，按段内出现顺序对齐。
    """
    parts = []
    f_iter = iter(formulas)
    # 遍历段落直接子元素（保留顺序）
    for child in p._p.iterchildren():
        tag = child.tag
        if tag == qn("w:r"):
            # 普通文本 run：抽出所有 w:t
            for t in child.iter(qn("w:t")):
                if t.text:
                    parts.append(t.text)
        elif tag == qn("m:oMath") or tag == qn("m:oMathPara"):
            try:
                seg = next(f_iter).strip()
                # 行内公式确保是 $...$ 形态
                if not seg.startswith("$"):
                    seg = "$" + seg
                if not seg.endswith("$"):
                    seg = seg + "$"
                parts.append(" " + seg + " ")
            except StopIteration:
                parts.append("[公式提取失败]")
        # 其他 tag（pPr 等）忽略
    return "".join(parts).strip()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python docx_to_ir.py <input.docx> <output_dir>")
        sys.exit(1)
    ir = parse_docx(sys.argv[1], sys.argv[2])
    out_json = Path(sys.argv[2]) / "ir.json"
    out_json.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"IR written to {out_json}")
    print(f"Blocks: {len(ir['blocks'])}")
    kinds = {}
    for b in ir["blocks"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print(f"Block kinds: {kinds}")
