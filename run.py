#!/usr/bin/env python3
"""
run.py — 一键流水线 v0.2
  python run.py <input.docx> <paper_meta.yaml> --school <school_id> [--out output_dir]
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "parser"))

from docx_to_ir import parse_docx
from ir_to_typst import render_typst
from lint import lint_docx, render_report
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("meta")
    ap.add_argument("--school", default="generic")
    ap.add_argument("--out", default="output/run")
    ap.add_argument("--no-lint", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    docx = Path(args.docx)
    meta_path = Path(args.meta)
    school_yaml = HERE / "templates" / "schools" / f"{args.school}.yaml"
    if not school_yaml.exists():
        avail = [p.stem for p in (HERE / "templates" / "schools").glob("*.yaml")]
        print(f"❌ Unknown school '{args.school}'. Available: {avail}")
        sys.exit(1)
    core_typ = HERE / "templates" / "core.typ"

    if not args.no_lint:
        issues = lint_docx(docx)
        report = render_report(issues)
        (out / "lint.txt").write_text(report, encoding="utf-8")
        (out / "lint.json").write_text(
            json.dumps([asdict(i) for i in issues], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(report); print()

    print("→ Parsing docx ...")
    ir = parse_docx(docx, out)
    (out / "ir.json").write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    kinds = {}
    for b in ir["blocks"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print(f"  {len(ir['blocks'])} blocks  {kinds}")

    print(f"→ Rendering Typst (school = {args.school}) ...")
    school_config = yaml.safe_load(school_yaml.read_text(encoding="utf-8")) or {}
    # 占位状态警告
    status = school_config.get("_status", "")
    if status == "placeholder":
        note = school_config.get("_status_note", "")
        print(f"  ⚠️  WARNING: 学校配置 '{args.school}' 处于 placeholder 状态")
        print(f"     {note}")
        print(f"     ⚠️  生成的 PDF 不能保证符合该校规范，请勿直接交付！")
    paper_meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    paper_meta = paper_meta or {}
    shutil.copy2(core_typ, out / "core.typ")

    # ---- 参考文献来源处理：优先级 bib > yaml > 知网文本 ----
    bib_text_path = paper_meta.get("bibliography_text_path")
    bib_path = paper_meta.get("bibliography_path")

    if bib_text_path and not bib_path:
        # 从知网文本生成 hayagriva yaml
        from gbt7714_parser import parse_text, to_hayagriva_yaml, lint_entries
        src_text = (meta_path.parent / bib_text_path).resolve()
        if src_text.exists():
            text = src_text.read_text(encoding="utf-8")
            entries = parse_text(text)
            yml_str = to_hayagriva_yaml(entries)
            generated_yml = out / "references.yml"
            generated_yml.write_text(yml_str, encoding="utf-8")
            paper_meta["bibliography_path"] = "references.yml"
            print(f"  CNKI text → {len(entries)} entries → {generated_yml}")
            # 参考文献条目的 lint 加进总报告
            ref_issues = lint_entries(entries)
            if ref_issues:
                ref_report_lines = [f"\n参考文献条目检查：{len(ref_issues)} 条"]
                for i in ref_issues:
                    icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}[i["severity"]]
                    ref_report_lines.append(f"  {icon} {i['key']}  {i['message']}  「{i['snippet']}」")
                ref_report = "\n".join(ref_report_lines)
                # 追加到 lint.txt
                if (out / "lint.txt").exists():
                    with (out / "lint.txt").open("a", encoding="utf-8") as f:
                        f.write(ref_report + "\n")
                print(ref_report)
        else:
            print(f"  ⚠️  bibliography_text_path 找不到: {src_text}")

    elif bib_path:
        src_bib = (meta_path.parent / bib_path).resolve()
        if src_bib.exists():
            shutil.copy2(src_bib, out / Path(bib_path).name)
            paper_meta["bibliography_path"] = Path(bib_path).name
            print(f"  bib → {out / Path(bib_path).name}")
        else:
            print(f"  ⚠️  bibliography_path 找不到: {src_bib}")

    main_typ = out / "main.typ"
    main_typ.write_text(
        render_typst(ir, school_config, paper_meta, core_rel="core.typ"),
        encoding="utf-8",
    )
    print(f"  {main_typ}")

    if args.no_pdf: return
    print("→ Compiling PDF ...")
    pdf = out / "final.pdf"
    cmd = ["typst", "compile", "--root", str(out.resolve()), str(main_typ), str(pdf)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("⚠️  Typst compile failed:"); print(proc.stderr); sys.exit(1)
    warnings = [l for l in proc.stderr.splitlines()
                if l.startswith(("error", "warning:")) and "unknown font" not in l]
    for w in warnings: print("  ", w)
    print(f"✅ PDF: {pdf}  ({pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
