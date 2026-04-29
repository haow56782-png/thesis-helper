"""
server.py — 最小本地 Flask 后端
让 prototype/index.html 真的能上传 docx，调用 run.py 流水线，返回 PDF + lint 报告。

启动：
  python server.py
  浏览器打开 http://127.0.0.1:5000/

API：
  GET  /                  → 返回 prototype/index.html
  POST /api/process       → 上传 docx + meta.yaml(可选) + bib.txt(可选) + school
                            返回 JSON：{ok, lint_issues, pdf_url, score}
  GET  /api/pdf/<run_id>  → 返回该次运行生成的 PDF
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent           # thesis-helper/
sys.path.insert(0, str(PROJECT_ROOT / "parser"))

from docx_to_ir import parse_docx
from ir_to_typst import render_typst
from lint import lint_docx, render_report
from gbt7714_parser import parse_text, to_hayagriva_yaml, lint_entries
import yaml

app = Flask(__name__, static_folder=str(HERE / "assets"))

# 运行结果暂存目录
RUNS_DIR = Path(tempfile.gettempdir()) / "thesis-helper-runs"
RUNS_DIR.mkdir(exist_ok=True)


@app.route("/")
def index():
    """注入 WIRED=true 让前端切换到真实模式。"""
    html = (HERE / "index.html").read_text(encoding="utf-8")
    # 在 <head> 末尾注入旗标
    html = html.replace(
        "</head>",
        "<script>window.WIRED = true;</script>\n</head>",
        1,
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(HERE / "assets", filename)


@app.route("/api/process", methods=["POST"])
def process():
    """主流水线入口。"""
    if "docx" not in request.files:
        return jsonify({"ok": False, "error": "缺少 docx 文件"}), 400
    docx_file = request.files["docx"]
    school = request.form.get("school", "generic")

    # 创建本次运行的目录
    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    docx_path = run_dir / "input.docx"
    docx_file.save(docx_path)

    # 处理可选的参考文献文本
    bib_text = request.form.get("bib_text", "").strip()
    bib_path = None
    if bib_text:
        entries = parse_text(bib_text)
        yml = to_hayagriva_yaml(entries)
        bib_path = run_dir / "references.yml"
        bib_path.write_text(yml, encoding="utf-8")

    # 元信息：从前端表单取，也可以让前端不传走默认
    meta = {
        "title_cn": request.form.get("title_cn", "本科毕业论文"),
        "title_en": request.form.get("title_en", ""),
        "author":   request.form.get("author", ""),
        "school":   request.form.get("school_name", ""),
        "department": request.form.get("department", ""),
        "major":    request.form.get("major", ""),
        "advisor":  request.form.get("advisor", ""),
        "advisor_title": request.form.get("advisor_title", "教授"),
        "date":     request.form.get("date", ""),
        "keywords_cn": [k.strip() for k in request.form.get("keywords_cn", "").split(",") if k.strip()],
        "keywords_en": [k.strip() for k in request.form.get("keywords_en", "").split(",") if k.strip()],
    }
    if bib_path:
        meta["bibliography_path"] = "references.yml"

    # Step 1: lint
    issues = lint_docx(docx_path)

    # Step 2: parse + render
    school_yaml_path = PROJECT_ROOT / "templates" / "schools" / f"{school}.yaml"
    if not school_yaml_path.exists():
        return jsonify({"ok": False, "error": f"未知学校：{school}"}), 400
    school_config = yaml.safe_load(school_yaml_path.read_text(encoding="utf-8"))
    is_placeholder = school_config.get("_status") == "placeholder"

    ir = parse_docx(docx_path, run_dir)

    # 拷 core.typ
    shutil.copy2(PROJECT_ROOT / "templates" / "core.typ", run_dir / "core.typ")
    typst_src = render_typst(ir, school_config, meta, core_rel="core.typ")
    main_typ = run_dir / "main.typ"
    main_typ.write_text(typst_src, encoding="utf-8")

    # Step 3: compile
    pdf_path = run_dir / "final.pdf"
    proc = subprocess.run(
        ["typst", "compile", "--root", str(run_dir.resolve()), str(main_typ), str(pdf_path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return jsonify({
            "ok": False,
            "error": "Typst 编译失败",
            "stderr": proc.stderr[:2000],
        }), 500

    # 评分
    counts = {"error": 0, "warn": 0, "info": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1
    score = max(0, 100 - counts["error"] * 8 - counts["warn"] * 3 - counts["info"] * 1)

    return jsonify({
        "ok": True,
        "run_id": run_id,
        "score": score,
        "lint": {
            "counts": counts,
            "items": [
                {"severity": i.severity, "code": i.code, "message": i.message,
                 "location": i.location, "snippet": i.snippet}
                for i in issues
            ],
        },
        "pdf_url": f"/api/pdf/{run_id}",
        "n_blocks": len(ir["blocks"]),
        "n_formulas": ir["meta"].get("n_formulas", 0),
        "school_warning": is_placeholder,
        "school_warning_note": school_config.get("_status_note", "") if is_placeholder else "",
    })


@app.route("/api/pdf/<run_id>")
def get_pdf(run_id):
    pdf = RUNS_DIR / run_id / "final.pdf"
    if not pdf.exists():
        return "PDF not found", 404
    return send_file(pdf, mimetype="application/pdf")


@app.route("/api/lint-text/<run_id>")
def get_lint_text(run_id):
    """返回 lint 报告纯文本（供下载）。"""
    items_json = (RUNS_DIR / run_id / "lint.json")
    if items_json.exists():
        return send_file(items_json, mimetype="application/json")
    return "Not found", 404


@app.route("/api/schools")
def list_schools():
    """供前端动态填充学校下拉。"""
    schools = []
    for f in (PROJECT_ROOT / "templates" / "schools").glob("*.yaml"):
        cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        schools.append({
            "id": f.stem,
            "name": cfg.get("school_name", f.stem),
            "is_placeholder": cfg.get("_status") == "placeholder",
        })
    return jsonify(schools)


if __name__ == "__main__":
    print("=" * 60)
    print("论文格式助手 · 本地服务器")
    print("=" * 60)
    print(f"  浏览器打开：http://127.0.0.1:5000/")
    print(f"  运行结果暂存：{RUNS_DIR}")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
