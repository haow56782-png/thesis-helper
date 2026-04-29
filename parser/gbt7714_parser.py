"""
gbt7714_parser.py
------------------
解析"知网 / 万方 GB/T 7714 文本格式"参考文献，输出 hayagriva YAML（Typst 原生格式）。

支持的类型代码（GB/T 7714-2015 附录 B）：
  [M] 专著      → book
  [J] 期刊      → article
  [C] 会议论文  → article  (parent is conference)
  [D] 学位论文  → thesis
  [R] 报告      → report
  [S] 标准      → legislation (兜底)
  [N] 报纸      → newspaper
  [P] 专利      → patent
  [Z] 其他      → misc
  [EB/OL] 网络  → web

设计：
  - 不强求 100% 解析准确——失败的条目原样保留为 misc 兜底，并在 lint 报告中标记
  - 优先正确解析"作者. 标题[X]. 期刊/出版社, 年份, 卷(期): 页码."这种主流格式
  - 中文人名用"姓名"整体处理；西文人名按"Family I"格式入 yaml
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
import sys

# 类型代码 → hayagriva entry type
TYPE_MAP = {
    "M": "book",
    "J": "article",
    "C": "article",
    "D": "thesis",
    "R": "report",
    "S": "legislation",
    "N": "newspaper",
    "P": "patent",
    "Z": "misc",
    "G": "misc",
    "EB/OL": "web",
    "DB/OL": "web",
    "J/OL": "article",
    "M/OL": "book",
}


@dataclass
class ParsedEntry:
    key: str
    raw: str                           # 原始行
    entry_type: str = "misc"
    type_code: str = "Z"
    authors: list[str] = field(default_factory=list)
    title: str = ""
    container: str = ""                # 期刊名 / 出版社 / 会议名
    place: str = ""                    # 出版地
    year: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    parse_warnings: list[str] = field(default_factory=list)


# 知网格式条目正则（贪婪解析）
# 形态：[N] 作者. 标题[X]. 容器, 年份[, 卷(期)][: 页码].
NUM_RE = re.compile(r"^\s*\[(\d+)\]\s*")
TYPE_CODE_RE = re.compile(r"\[([A-Z]{1,2}(?:/[A-Z]{2})?)\]")  # [J], [M], [EB/OL]
YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
VOL_ISSUE_RE = re.compile(r"(\d+)\s*\((\d+(?:[-–]\d+)?)\)")  # 521(7553)
PAGES_RE = re.compile(r"[:：]\s*([\d]+(?:[-–][\d]+)?)\s*\.?\s*$")


def split_authors(raw: str) -> list[str]:
    """切分作者，处理中英文混合 + '等'/'et al'."""
    raw = raw.strip().rstrip(".")
    raw = re.sub(r"[,，]\s*等\s*\.?$", "", raw)
    raw = re.sub(r",?\s*et\s+al\.?$", "", raw, flags=re.I)
    # 分隔符：中文逗号 / 英文逗号
    parts = re.split(r"[,，]\s*", raw)
    return [p.strip() for p in parts if p.strip()]


def author_to_hayagriva(name: str) -> str | dict:
    """中文姓名整体作为 string；西文按 'Family, Given' 转为 'Given Family' 并保留首字母缩写格式。
    Hayagriva 接受 string 形式："First Last" 或 "Last, First"。
    """
    name = name.strip()
    if not name:
        return name
    # 含 CJK 字符 → 中文姓名
    if re.search(r"[\u4e00-\u9fff]", name):
        return name
    # "He K" / "LeCun Y" → 已经是 Family Given 形式
    # "Vaswani A" → 保持
    # "He, Kaiming" → 转 "Kaiming He"
    if "," in name:
        last, first = [s.strip() for s in name.split(",", 1)]
        return f"{first} {last}"
    return name


def parse_one_line(line: str, idx: int) -> ParsedEntry | None:
    """解析单条参考文献。"""
    line = line.strip()
    if not line:
        return None
    m = NUM_RE.match(line)
    if not m:
        # 非编号行（可能是续行），返回 None 让上层处理
        return None
    num = m.group(1)
    body = line[m.end():].strip()
    entry = ParsedEntry(key=f"ref{num}", raw=line)

    # 找类型代码
    tm = TYPE_CODE_RE.search(body)
    if tm:
        entry.type_code = tm.group(1)
        entry.entry_type = TYPE_MAP.get(entry.type_code.split("/")[0], "misc")
        # 作者部分 = 类型代码之前到上一个 "." 的内容
        before = body[:tm.start()].rstrip()
        # 作者+标题：通常是 "作者. 标题"
        # 但作者也可能含点（"等."）。简化：找最后一个 ". " 切分；
        # 中文论文常见 "国务院.国务院关于..." 这种无空格分隔，回退到搜索 "."
        authors_raw = ""
        last_dot = before.rfind(". ")
        if last_dot > 0:
            authors_raw = before[:last_dot]
            entry.title = before[last_dot + 2:].strip()
        else:
            # 退化：找最后一个单纯的 "." （注意不要切到"等."这种）
            # 启发式：如果前面有"."，取第一个"."切分（中文格式："作者.标题"）
            first_dot = before.find(".")
            if 0 < first_dot < len(before) - 1:
                authors_raw = before[:first_dot]
                entry.title = before[first_dot + 1:].strip()
            else:
                entry.title = before.strip()
                entry.parse_warnings.append("无法分离作者与标题")
        entry.authors = [author_to_hayagriva(a) for a in split_authors(authors_raw)]
        # 类型代码之后：容器、年份、卷期、页码
        after = body[tm.end():].lstrip(". ").strip()
        entry = _parse_after(entry, after)
    else:
        entry.parse_warnings.append("缺少类型代码 [J]/[M]/...，按 misc 处理")
        entry.title = body.rstrip(".").strip()

    return entry


def _parse_after(entry: ParsedEntry, after: str) -> ParsedEntry:
    """解析类型代码之后的部分：容器, 年份, 卷(期): 页码."""
    after = after.strip().rstrip(".")
    if not after:
        return entry

    # 提取页码（如果存在）
    pm = PAGES_RE.search(after)
    if pm:
        entry.pages = pm.group(1).replace("–", "-")
        after = after[:pm.start()].rstrip(",.; ")

    # 提取卷(期)
    vm = VOL_ISSUE_RE.search(after)
    if vm:
        entry.volume = vm.group(1)
        entry.issue = vm.group(2)
        after = (after[:vm.start()] + after[vm.end():]).rstrip(",. ")
    else:
        # 仅有卷号，无期号
        only_vol = re.search(r",\s*(\d+)\s*$", after)
        if only_vol and not entry.year:
            # 不直接吞掉，可能是年份；让 year 优先
            pass

    # 提取年份（4 位数）
    ym_all = YEAR_RE.findall(after)
    if ym_all:
        entry.year = ym_all[-1]   # 取最后一个 4 位数
        # 把年份从 after 中去掉
        after = re.sub(r"[,，]\s*\d{4}\s*[,，]?\s*", ", ", after)
        after = re.sub(r"\s*\d{4}\s*$", "", after).rstrip(",. ")

    # 剩余内容当 container（期刊名 / 出版社）
    # 形如 "北京: 清华大学出版社" → place="北京", container="清华大学出版社"
    if ":" in after or "：" in after:
        place_part, container_part = re.split(r"[:：]", after, 1)
        entry.place = place_part.strip()
        entry.container = container_part.strip()
    else:
        entry.container = after.strip()

    return entry


def merge_continuation_lines(lines: list[str]) -> list[str]:
    """把多行续写的条目合并为一行。条目以 [N] 开头，下一行不以 [N] 开头则视为续行。"""
    merged = []
    cur = ""
    for ln in lines:
        if NUM_RE.match(ln):
            if cur:
                merged.append(cur)
            cur = ln.strip()
        else:
            if cur:
                cur += " " + ln.strip()
            elif ln.strip():
                # 没有归属的续行，丢弃或独立处理
                cur = ln.strip()
    if cur:
        merged.append(cur)
    return merged


def parse_text(text: str) -> list[ParsedEntry]:
    lines = [ln for ln in text.splitlines()]
    merged = merge_continuation_lines(lines)
    entries = []
    for i, line in enumerate(merged, 1):
        e = parse_one_line(line, i)
        if e:
            entries.append(e)
    return entries


def to_hayagriva_yaml(entries: list[ParsedEntry]) -> str:
    """渲染为 hayagriva YAML（Typst 原生支持）。"""
    out_lines = []
    for e in entries:
        out_lines.append(f"{e.key}:")
        out_lines.append(f"  type: {e.entry_type}")
        if e.title:
            out_lines.append(f"  title: {_yaml_str(e.title)}")
        if e.authors:
            out_lines.append("  author:")
            for a in e.authors:
                out_lines.append(f"    - {_yaml_str(a)}")
        if e.year:
            out_lines.append(f"  date: {e.year}")
        if e.container:
            # hayagriva：article 用 parent.title；book 用 publisher
            if e.entry_type == "article":
                out_lines.append("  parent:")
                out_lines.append(f"    type: periodical")
                out_lines.append(f"    title: {_yaml_str(e.container)}")
            elif e.entry_type == "book":
                out_lines.append(f"  publisher: {_yaml_str(e.container)}")
            else:
                out_lines.append(f"  publisher: {_yaml_str(e.container)}")
        if e.place:
            out_lines.append(f"  location: {_yaml_str(e.place)}")
        if e.volume:
            out_lines.append(f"  volume: {e.volume}")
        if e.issue:
            out_lines.append(f"  issue: {e.issue}")
        if e.pages:
            out_lines.append(f"  page-range: {_yaml_str(e.pages)}")
        out_lines.append("")
    return "\n".join(out_lines)


def _yaml_str(s: str) -> str:
    """安全地把字符串放进 yaml（不需要转义就裸写，否则用双引号）。"""
    if not s:
        return '""'
    s_clean = s.strip()
    # 含特殊字符时用双引号
    if any(c in s_clean for c in [':', '#', '@', '"', "'", '\n', '[', ']', '{', '}', ',']):
        return '"' + s_clean.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s_clean


# ========== Lint：参考文献条目质量检查 ==========

def lint_entries(entries: list[ParsedEntry]) -> list[dict]:
    """检查参考文献条目，返回问题列表。"""
    issues = []
    for e in entries:
        loc = f"[{e.key}]"
        if e.parse_warnings:
            for w in e.parse_warnings:
                issues.append({"key": e.key, "severity": "warn",
                               "message": w, "snippet": e.raw[:60]})
        if not e.title:
            issues.append({"key": e.key, "severity": "error",
                           "message": "缺少标题", "snippet": e.raw[:60]})
        if not e.authors:
            issues.append({"key": e.key, "severity": "warn",
                           "message": "未识别到作者", "snippet": e.raw[:60]})
        if not e.year:
            issues.append({"key": e.key, "severity": "warn",
                           "message": "缺少年份", "snippet": e.raw[:60]})
        if e.entry_type == "article" and not e.container:
            issues.append({"key": e.key, "severity": "warn",
                           "message": "期刊文章缺少期刊名", "snippet": e.raw[:60]})
        if e.pages and not re.match(r"^\d+(-\d+)?$", e.pages):
            issues.append({"key": e.key, "severity": "info",
                           "message": f"页码格式可能不规范：{e.pages}", "snippet": e.raw[:60]})
    return issues


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gbt7714_parser.py <input.txt> <output.yml> [--lint]")
        sys.exit(1)
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    entries = parse_text(text)
    yml = to_hayagriva_yaml(entries)
    Path(sys.argv[2]).write_text(yml, encoding="utf-8")
    print(f"✅ Parsed {len(entries)} entries → {sys.argv[2]}")
    if "--lint" in sys.argv:
        issues = lint_entries(entries)
        if issues:
            print(f"\n参考文献质量检查：{len(issues)} 条问题")
            for i in issues:
                icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}[i["severity"]]
                print(f"  {icon} {i['key']}  {i['message']}  「{i['snippet']}」")
        else:
            print("✅ 参考文献条目无明显问题")
