# 论文格式助手 · 项目断点恢复手册

> **写给未来的自己**：三个月后重新打开这个项目，读完这份文档，5 分钟内就能接着干。
>
> 最后更新：2026-05-01
> 当前版本：v0.5
> GitHub：https://github.com/haow56782-png/thesis-helper（Private）

---

## 一、项目是什么 / 做到哪了

### 一句话定位
本科毕业论文一键排版工具：学生提交 `.docx` + 知网参考文献文本 → 工具自动体检格式、排版、编译出符合 GB/T 7714-2015 的 PDF。

### 当前能力（v0.5 已实现，全部验证过）

| 能力 | 状态 | 备注 |
|---|---|---|
| docx → PDF 完整闭环 | ✅ | 含封面/摘要/目录/正文/致谢/参考文献 |
| 格式体检（lint）6 类规则 | ✅ | 评分 + 问题列表 |
| 知网参考文献文本一键转换 | ✅ | 支持 J/M/D/R/C/EB/OL 等 12 种类型代码 |
| 中括号引用 `[1]`/`[2,3]`/`[1-3]` | ✅ | 自动转 GB/T 7714 上标，含边界保护 |
| Word 公式编辑器（OMML）→ Typst | ✅ | Pandoc 驱动，行内 + 块级 |
| 文本数学 `$...$` 透传 | ✅ | |
| 多校 yaml 配置 | ✅ | generic / nju 完成；cqcst 是 placeholder |
| Web 交互原型（SPA） | ✅ | `prototype/index.html` 双击即跑 |
| Flask 通电后端 | ✅ | `prototype/server.py` |

### 样本论文（演示用）
- **会计学**：数字经济背景下中小企业财务共享服务中心建设研究（数智经济管理学院 · 重庆城市科技学院）
  - 输入：`examples/accounting_thesis.docx` + `examples/cnki_refs_accounting.txt`
  - 元信息：`examples/accounting_meta.yaml`
  - 输出：`output/accounting/final.pdf`（13 页）

---

## 二、一条命令跑起来

```bash
# 环境
pip install python-docx pyyaml lxml flask pillow
apt install pandoc fonts-noto-cjk     # Ubuntu
# brew install pandoc                 # macOS
# typst 二进制：https://github.com/typst/typst/releases

# 最快验证（会计学样本）
export PATH=/path/to/typst:$PATH
python run.py examples/accounting_thesis.docx examples/accounting_meta.yaml \
              --school cqcst --out output/test

# 本地 Web 原型（演示模式，不需要后端）
open prototype/index.html

# 本地 Web 原型（通电模式，真实运行）
python prototype/server.py
# 浏览器打开 http://127.0.0.1:5000/
```

---

## 三、项目结构（只看这里）

```
thesis-helper/
│
├── run.py                    ← CLI 入口，一条命令跑完整流水线
│
├── parser/                   ← 核心引擎（改功能主要改这里）
│   ├── docx_to_ir.py         ← docx → 语义 IR JSON
│   │                            重点：extract_all_formulas_typst()（OMML 提取）
│   ├── ir_to_typst.py        ← IR → Typst 源码
│   │                            重点：_BRACKET_TRANSFORM_ENABLED 全局开关
│   │                                  render_block() / render_typst()
│   ├── gbt7714_parser.py     ← 知网文本 → hayagriva YAML
│   │                            重点：parse_line() 里的 first_dot 回退逻辑
│   └── lint.py               ← 6 类格式规则检测
│
├── templates/
│   ├── core.typ              ← 参数化 Typst 核心模板（字号/页边距/字体从 yaml 注入）
│   └── schools/
│       ├── generic.yaml      ← 通用范本（完整参数，新学校从这复制）
│       ├── nju.yaml          ← 南京大学（已完整）
│       └── cqcst.yaml        ← 重庆城市科技学院（⚠️ PLACEHOLDER，见下）
│
├── examples/                 ← 演示输入文件（不要删）
│   ├── accounting_thesis.docx        会计学完整论文
│   ├── accounting_meta.yaml          元信息
│   ├── cnki_refs_accounting.txt      12 条知网参考文献
│   └── make_accounting_thesis.py     重新生成 docx 的脚本
│
├── prototype/
│   ├── index.template.html   ← SPA 原型模板源文件（改样式改这个）
│   ├── index.html            ← 构建产物（build.py 生成，不要手改）
│   ├── build.py              ← 重新生成 index.html 的脚本
│   ├── server.py             ← Flask 后端（接入真实流水线）
│   └── assets/               ← demo.pdf + 4 张预览 PNG
│
└── output/                   ← 编译产物（git 忽略，本地可以删）
```

---

## 四、当前最大卡点：cqcst.yaml 真实化

**这是 v0.6 的 P0 任务。**

现状：`templates/schools/cqcst.yaml` 里所有格式参数都是猜测值（从 generic 复制），每次运行都会打警告。代码已经做好了：
- 运行时 `⚠️ WARNING: 学校配置 'cqcst' 处于 placeholder 状态`
- 文件头部有详细的"待确认字段清单"
- 状态机：`placeholder → draft → verified → proven`

**解锁条件（任意一个）：**
1. 取得该校《本科毕业论文撰写规范》PDF/Word
2. 拿到同学已通过答辩的 docx 样本（逆向推规范）
3. 手动整理关键参数清单（字号/行距/页眉要求）

**一旦拿到资料，修改方式：**
打开 `templates/schools/cqcst.yaml`，把 `❓` 标记的字段填上真实值，把 `_status: placeholder` 改成 `_status: draft`，运行一次对比截图，确认后改成 `_status: verified`。**不需要改任何 Python 代码**。

---

## 五、下一版（v0.6）待做清单

按优先级排列：

### P0（下次开工第一件事）
- [ ] **cqcst.yaml 真实化** — 依赖资料，见上

### P1（功能补完）
- [ ] **通电模式元信息表单** — `prototype/index.html` 里上传 docx 后应该弹出表单让用户填 title/author/advisor/date，当前只用文件名当 title。改 `prototype/index.template.html` 里 `processRealFile()` 函数，在 FormData append 那里加字段，然后重跑 `build.py`。
- [ ] **bib_text textarea** — 前端没有暴露参考文献粘贴入口，后端 `server.py` 已经支持 `bib_text` 字段，只需要在配置面板加一个 textarea。
- [ ] **gbt7714_parser [C] 类型代码** — 会议论文 `[C]` 目前被当 `[J]` 渲染（hayagriva 没有专门的 conference 类型），需要自定义 CSL 或者 fallback 到 `article`+标注。
- [ ] **公式编号 + 交叉引用** — Typst 原生支持 `$ ... $ <eq:label>`，需要让用户在 docx 里能写 `@eq:...` 并被识别。

### P2（体验优化）
- [ ] **移动端响应式精修** — 目前 `< 920px` 有基础降级但没在真手机上测过
- [ ] **预览 PDF 加载状态** — 通电模式下 iframe 加载 PDF 时右侧空白，需要加个 spinner
- [ ] **下载卡片 PDF 大小** — 通电模式下应该显示真实 KB 数，目前写死 "359 KB"

### P3（长期）
- [ ] 图/表 caption 自动提取（解析 "图 1.1：..." 模式）
- [ ] 多份历史记录管理（当前每次上传产生新 run_id 但没有历史列表）
- [ ] 真实 lint 问题可跳转到 docx 行号

---

## 六、已知 Bug / 已修复记录

| 版本 | Bug | 修复位置 | 状态 |
|---|---|---|---|
| v0.3 | 用户上传不带 bib 的 docx 时，`[1]` 被误转 `@ref1` 导致编译失败 | `ir_to_typst.py::_BRACKET_TRANSFORM_ENABLED` 加 bib 判断 | ✅ 已修 |
| v0.4 | `gbt7714_parser` 处理 `国务院.国务院关于...`（作者+标题无空格分隔）崩溃 `UnboundLocalError` | `gbt7714_parser.py::parse_line()` 加 `first_dot` 回退 | ✅ 已修 |
| v0.4 | Flask 后端 500 错误（Typst 有 stderr 警告但 returncode=0，被误判为失败）| `server.py` 改为只检查 returncode | ✅ 已修 |
| 已知 | `[C]` 会议论文类型代码丢失，被 hayagriva 渲染为期刊 | `gbt7714_parser.py` 需自定义 CSL | ⚠️ 未修 |

---

## 七、核心设计决策记录（别忘了为什么这么做）

**为什么用 Typst 不用 LaTeX？**
编译秒级、模板易写、PDF 质量稳、不需要 TeX 发行版。学生端零感知。

**为什么不让 Pandoc 接管整个 docx？**
Pandoc 直接 docx→typst 会把 `$E=mc^2$` 这种文本里的 `$` 转义成 `\$`，破坏透传逻辑。现在的做法是：只用 Pandoc 的 JSON AST 做外科手术式提取——只取 Math 节点，主流程还是 python-docx。

**为什么 `_BRACKET_TRANSFORM_ENABLED` 是全局开关？**
如果用户没提供 bib，`[1]` 在 Typst 里找不到对应的 `@ref1` 标签会编译报错。这个开关仅在有参考文献来源时启用，避免用户没传 bib 就崩掉。

**为什么 cqcst.yaml 用 `_status` 字段而不是注释？**
注释是给人看的，`_status` 字段是给程序读的。`run.py` 里会检查这个字段并在运行时打警告，防止用了 placeholder 配置的 PDF 被直接交付。

---

## 八、GitHub 仓库

```
仓库：https://github.com/haow56782-png/thesis-helper
可见性：Private
默认分支：main
提交历史：
  dbfae41  feat: initial commit（v0.5 完整工程）
  62b8b5e  docs: 新人接收文档 ONBOARDING.md
```

**下次开发完推代码：**
```bash
git add .
git commit -m "feat/fix: 描述你做了什么"
git push origin main
```

---

## 九、快速验证一切正常的命令序列

下次打开项目，运行这几条确认环境没问题：

```bash
cd thesis-helper

# 1. 确认 Python 依赖
pip install -r requirements.txt

# 2. 确认 typst 可用
typst --version   # 应该输出 typst 0.14.x

# 3. 确认 pandoc 可用
pandoc --version  # 应该输出 pandoc 3.x

# 4. 跑一次端到端（约 3 秒）
python run.py examples/accounting_thesis.docx examples/accounting_meta.yaml \
              --school cqcst --out output/smoke-test

# 5. 验证输出
ls output/smoke-test/
# 应该看到：final.pdf  lint.txt  main.typ  references.yml  ir.json

# 6. 打开原型
open prototype/index.html   # macOS
# xdg-open prototype/index.html  # Linux
```

全部通过 → 直接开干。

---

*最后一条：有什么不确定的，把这份文档和项目代码一起喂给 Claude，说"接着上次的论文排版项目继续"，它能无缝接上。*
