#!/usr/bin/env python3
"""
prototype/build.py — 从模板重新生成 index.html

用法：
    cd prototype/
    python build.py

依赖：
    pip install pillow

生成文件：
    preview-data.json   — assets/ 里的 PNG base64 编码
    index.html          — 最终单文件原型（约 1.5 MB）

如果 assets/ 里没有 PNG 缩略图，脚本会给出提示。
缩略图应该是运行 run.py 后从 output/ 里复制过来的页面截图：
    cp ../output/accounting/pa-01.png assets/preview-cover.png
    cp ../output/accounting/pa-04.png assets/preview-toc.png
    cp ../output/accounting/pa-09.png assets/preview-body.png
    cp ../output/accounting/pa-12.png assets/preview-bib.png
"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
TEMPLATE = HERE / "index.template.html"
OUT_DATA = HERE / "preview-data.json"
OUT_HTML = HERE / "index.html"

PAGES = {
    "cover": "preview-cover.png",
    "toc":   "preview-toc.png",
    "body":  "preview-body.png",
    "bib":   "preview-bib.png",
}

def resize_and_encode(src: Path, max_width: int = 900) -> str:
    """Resize to max_width px and return data-URI string."""
    try:
        from PIL import Image
    except ImportError:
        print("  ⚠  Pillow 未安装，将使用原始尺寸（文件较大）")
        print("     pip install pillow")
        return "data:image/png;base64," + base64.b64encode(src.read_bytes()).decode()

    img = Image.open(src)
    w, h = img.size
    if w > max_width:
        nh = int(h * max_width / w)
        img = img.resize((max_width, nh), Image.LANCZOS)

    import io
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    print("── 论文格式助手 · 原型构建脚本 ──")

    # 检查模板
    if not TEMPLATE.exists():
        print(f"✗  找不到模板：{TEMPLATE}")
        sys.exit(1)

    # 检查并编码图片
    missing = [k for k, f in PAGES.items() if not (ASSETS / f).exists()]
    if missing:
        print(f"\n✗  以下缩略图缺失：{missing}")
        print("   请先运行 run.py 生成论文，然后把对应页面 PNG 复制到 assets/：")
        for k, f in PAGES.items():
            if k in missing:
                print(f"   cp ../output/<任意论文>/pa-XX.png assets/{f}")
        sys.exit(1)

    print("\n1. 编码预览图片…")
    data = {}
    for k, f in PAGES.items():
        src = ASSETS / f
        print(f"   {k}: {src.stat().st_size // 1024} KB → ", end="", flush=True)
        data[k] = resize_and_encode(src)
        print(f"{len(data[k]) // 1024} KB (base64)")

    OUT_DATA.write_text(json.dumps(data), encoding="utf-8")
    print(f"   → preview-data.json: {OUT_DATA.stat().st_size // 1024} KB")

    print("\n2. 注入模板…")
    template = TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("__IMGS__", json.dumps(data))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"   → index.html: {OUT_HTML.stat().st_size // 1024} KB ✓")

    print(f"\n✓  完成！双击 index.html 在浏览器中打开即可。")


if __name__ == "__main__":
    main()
