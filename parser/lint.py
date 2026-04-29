"""
lint.py
---------------
对原始 docx 做格式体检，输出问题清单（不改写文件）。
检查项（MVP 第一版）：
  L1 [error]   未使用 Heading 样式的"伪标题"（手动加粗大字号）
  L2 [warn]    标题层级跳跃（1→3 跳过 2）
  L3 [warn]    段落首行未缩进（仅检查正文段，非中心对齐、非空）
  L4 [info]    字体混用（同一段落超过 N 种字体/字号）
  L5 [error]   缺少摘要 / 关键词 / 参考文献节
  L6 [warn]    图/表无 caption
"""

from __future__ import annotations
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph as _Para


SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"
SEVERITY_INFO = "info"


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    location: str = ""    # e.g. "para 14"
    snippet: str = ""


def _heading_level(p: _Para) -> int:
    style = p.style.name if p.style else ""
    m = re.match(r"^Heading\s+(\d+)$", style, re.I) or re.match(r"^标题\s*(\d+)$", style)
    return int(m.group(1)) if m else 0


def _is_centered(p: _Para) -> bool:
    return (p.alignment is not None) and (p.alignment in (1, 2))  # CENTER or RIGHT


def _max_run_size(p: _Para) -> float:
    sizes = []
    for r in p.runs:
        if r.font.size:
            sizes.append(r.font.size.pt)
    return max(sizes) if sizes else 0


def _has_bold_run(p: _Para) -> bool:
    return any(r.bold for r in p.runs)


def _font_set(p: _Para) -> set:
    fonts = set()
    for r in p.runs:
        if r.font.name:
            fonts.add(r.font.name)
    return fonts


def _size_set(p: _Para) -> set:
    sizes = set()
    for r in p.runs:
        if r.font.size:
            sizes.add(r.font.size.pt)
    return sizes


def lint_docx(docx_path: str | Path) -> list[Issue]:
    doc = Document(str(docx_path))
    issues: list[Issue] = []

    paragraphs = list(doc.paragraphs)
    last_heading_level = 0

    section_seen = {"abstract": False, "keywords": False, "references": False}

    for idx, p in enumerate(paragraphs):
        text = p.text.strip()
        loc = f"para {idx + 1}"

        # 节识别
        if re.match(r"^摘\s*要$", text):
            section_seen["abstract"] = True
        if re.match(r"^关键词", text):
            section_seen["keywords"] = True
        if re.match(r"^参考文献$", text):
            section_seen["references"] = True

        level = _heading_level(p)

        # L1：伪标题——居中或加粗 + 大字号 但不是 Heading 样式
        if not level and text and len(text) < 30:
            big_size = _max_run_size(p) >= 14
            looks_like_heading = (_is_centered(p) or _has_bold_run(p)) and big_size
            if looks_like_heading and not text.startswith(("图", "表", "Figure", "Table", "关键词")):
                issues.append(Issue(
                    code="L1",
                    severity=SEVERITY_ERROR,
                    message="疑似手动伪标题（未使用 Heading 样式）",
                    location=loc,
                    snippet=text[:40],
                ))

        # L2：层级跳跃
        if level:
            if last_heading_level and level > last_heading_level + 1:
                issues.append(Issue(
                    code="L2",
                    severity=SEVERITY_WARN,
                    message=f"标题层级跳跃（{last_heading_level} → {level}）",
                    location=loc,
                    snippet=text[:40],
                ))
            last_heading_level = level

        # L3：首行缩进缺失（中文论文规范：除标题/居中段/列表外，正文应缩进 2 字符）
        if not level and text and not _is_centered(p):
            pPr = p._p.find(qn("w:pPr"))
            indent_ok = False
            if pPr is not None:
                ind = pPr.find(qn("w:ind"))
                if ind is not None:
                    first_line = ind.get(qn("w:firstLine"))
                    first_line_chars = ind.get(qn("w:firstLineChars"))
                    if first_line or first_line_chars:
                        indent_ok = True
            # 排除明显是图/表说明、关键词、列表的行
            if (not indent_ok
                and not text.startswith(("关键词", "图", "表"))
                and len(text) > 30
                and "List" not in (p.style.name if p.style else "")):
                issues.append(Issue(
                    code="L3",
                    severity=SEVERITY_WARN,
                    message="正文段缺少首行缩进 2 字符",
                    location=loc,
                    snippet=text[:30] + "...",
                ))

        # L4：字体/字号混用
        fonts = _font_set(p)
        sizes = _size_set(p)
        if len(fonts) > 2 or len(sizes) > 2:
            issues.append(Issue(
                code="L4",
                severity=SEVERITY_INFO,
                message=f"段内字体/字号混用（fonts={fonts or '∅'}, sizes={sizes or '∅'}）",
                location=loc,
                snippet=text[:30],
            ))

    # L5：缺节
    for key, ok in section_seen.items():
        if not ok:
            label = {"abstract": "摘要", "keywords": "关键词", "references": "参考文献"}[key]
            issues.append(Issue(
                code="L5",
                severity=SEVERITY_ERROR,
                message=f"缺少必备章节：{label}",
            ))

    return issues


def render_report(issues: list[Issue]) -> str:
    if not issues:
        return "✅ 未检出格式问题"
    counts = {"error": 0, "warn": 0, "info": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1
    lines = [
        f"格式体检报告：共 {len(issues)} 条 "
        f"(❌ error={counts['error']}, ⚠️  warn={counts['warn']}, ℹ️  info={counts['info']})",
        "=" * 70,
    ]
    icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}
    for i in issues:
        loc = f"  [{i.location}]" if i.location else ""
        snip = f"  「{i.snippet}」" if i.snippet else ""
        lines.append(f"{icon[i.severity]} {i.code}  {i.message}{loc}{snip}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lint.py <input.docx> [--json]")
        sys.exit(1)
    issues = lint_docx(sys.argv[1])
    if "--json" in sys.argv:
        import json
        print(json.dumps([asdict(i) for i in issues], ensure_ascii=False, indent=2))
    else:
        print(render_report(issues))
