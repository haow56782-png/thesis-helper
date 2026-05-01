# 论文格式助手 · 新人接收文档

> 面向三类角色：前端 / 后端 / 产品
> 版本：v0.5 | 最后更新：2026-05

---

## 一、产品目标与用户价值

### 是什么

本科毕业论文格式体检与一键排版工具。用户上传自己写的 `.docx`，工具做两件事：

1. **体检**：检测格式问题（标题没用 Heading 样式、首行没缩进、参考文献格式不对等），给出可读性报告和综合评分
2. **排版**：丢弃 docx 里的所有格式，按学校规范重新排，导出符合 GB/T 7714-2015 的高质量 PDF

### 目标用户

重庆城市科技学院（及同类高校）**写本科毕业论文的学生**。核心痛点：毕业论文格式要求复杂，手动调整费时费力，还容易漏。

### 价值主张

```
学生只管写内容，格式全交给工具。
输入：普通 Word 文档（.docx）
输出：符合规范的 PDF + 格式问题清单
```

---

## 二、需求全景（业务逻辑层）

### 完整用户流程

```
1. 学生写论文（docx）
   ↓
2. 上传 docx + 配置（学校、参考文献来源）
   ↓
3. 格式体检 → lint 报告（评分 + 问题清单）
   ↓
4. 自动排版 → 编译 PDF
   ↓
5. 预览 + 下载（PDF / lint.txt / main.typ）
```

### 论文结构要求（通用本科规范）

```
封面
  学校名 / 副标题 / 论文标题（中英双语）/ 学院 / 专业 / 学号 / 作者 / 指导教师 / 日期
中文摘要 + 关键词
英文摘要（Abstract）+ Keywords
目录（自动生成，三级，点引线+页码）
正文
  第一章 绪论
    1.1 研究背景与意义
    1.2 国内外研究现状
    1.3 研究内容与方法
  第二章 … 第N章
  （参考文献  ← 无章节编号）
  （致谢      ← 无章节编号）
```

### 参考文献规范（GB/T 7714-2015）

```
支持的文献类型：
  [J] 期刊    [M] 专著    [D] 学位论文
  [R] 报告    [C] 会议    [N] 报纸
  [P] 专利    [EB/OL] 网络文献

文中引用格式：[1]、[2,3]、[1-3]（中括号上标）
文末列表格式：[1] 作者. 标题[J]. 期刊名, 年份, 卷(期): 页码.
              外文作者姓全大写，格式：FAMILY I.
```

---

## 三、技术架构总览

### 整体流水线

```
用户上传 docx
    │
    ▼
┌─────────────────┐
│  lint.py        │  格式体检（不修改文件）
│  6类规则检测    │  → lint.txt + lint.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ docx_to_ir.py   │  结构提取
│ Word文档 → IR   │  → ir.json（纯结构JSON）
│ (丢弃所有格式)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ gbt7714_parser  │ ─── │ 知网txt参考文献   │
│ .py             │      │ → references.yml  │
│ 参考文献转换    │      └──────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ir_to_typst.py  │  IR + 学校配置 + 论文元信息
│ → main.typ      │  → Typst 源码
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ typst compile   │  Typst 编译器（系统依赖）
│ → final.pdf     │  耗时 < 1s
└─────────────────┘
```

### 文件目录结构

```
thesis-helper/
│
├── run.py                        CLI 主入口（串联完整流水线）
│
├── parser/                       核心解析引擎（纯 Python）
│   ├── docx_to_ir.py             docx → 语义 IR JSON
│   ├── ir_to_typst.py            IR + 配置 → Typst 源码
│   ├── gbt7714_parser.py         知网参考文献文本 → hayagriva YAML
│   └── lint.py                   格式体检（6 类规则）
│
├── templates/                    排版模板层
│   ├── core.typ                  Typst 核心模板（参数化）
│   └── schools/
│       ├── generic.yaml          通用范本（基线参数）
│       ├── nju.yaml              南京大学配置
│       └── cqcst.yaml            重庆城市科技学院（⚠ placeholder）
│
├── prototype/                    产品原型
│   ├── index.template.html       SPA 前端模板（Vanilla JS + CSS）
│   ├── build.py                  构建脚本，注入 base64 → index.html
│   ├── server.py                 Flask 后端（6个API）
│   └── assets/                   demo.pdf + 预览PNG
│
└── examples/                     示例数据
    ├── accounting_thesis.docx    会计学论文（完整演示样本）
    ├── accounting_meta.yaml      元信息配置
    └── cnki_refs_accounting.txt  知网格式参考文献（12条）
```

### 关键依赖

| 依赖 | 用途 | 类型 |
|---|---|---|
| python-docx | 解析 Word 文档 | Python库 |
| pyyaml | 读取学校配置 | Python库 |
| lxml | XML 解析（OMML公式） | Python库 |
| pandoc | OMML → Typst 数学语法转换 | 系统程序 |
| typst | 编译 .typ → .pdf | 系统程序 |
| flask | Web 后端 | Python库 |
| pillow | 原型图片压缩 | Python库 |
| fonts-noto-cjk | 中文字体 | 系统字体 |

---

## 四、后端新人：核心模块详解

### 4.1 格式体检（lint.py）

**6 类规则：**

| 规则 | 级别 | 检测逻辑 |
|---|---|---|
| L1 | error | 未用 Heading 样式的"伪标题"：短文本(<30字) + (居中或加粗) + 字号≥14pt |
| L2 | warn | 标题层级跳跃：如 H1 → H3（跳过 H2）|
| L3 | warn | 正文段首行缩进缺失：检查 `w:ind` 标签里的 `w:firstLine` 属性 |
| L4 | info | 段内字体/字号混用：同段超过 2 种字体或字号 |
| L5 | error | 缺少必备章节：扫描全文，找不到"摘要"/"关键词"/"参考文献" |
| L6 | warn | 图表无 caption（⚠ 已定义未完全实现）|

**评分公式：**
```
score = max(0, 100 - error×8 - warn×3 - info×1)
```

**输出：** `lint.txt`（人读）+ `lint.json`（机读）

---

### 4.2 docx → IR（docx_to_ir.py）

**IR（中间表示）设计原则：** 只记录"是什么"，不记录"长什么样"

**Block 类型：**

| kind | 说明 | 关键字段 |
|---|---|---|
| `heading` | 标题 | `level`(1/2/3), `text` |
| `para` | 普通段落 | `text` |
| `list_item` | 列表项 | `text`, `ordered`(bool) |
| `table` | 表格 | `rows`(二维字符串数组) |
| `figure` | 图片 | `image_path`, `caption` |
| `equation` | 块级公式 | `text`(Typst 数学体) |

**公式处理流程（OMML）：**
```
docx 里的 Word 公式编辑器(OMML)
  ↓ pandoc -t json          → 提取 Math 节点，得到 LaTeX 字符串
  ↓ pandoc -f markdown -t typst  → LaTeX → Typst 数学语法
  ↓ 按文档顺序回填到段落
```

**已知限制：**
- python-docx 的 `.text` 属性不包含 `m:oMath` 内容，所以需要单独重建带公式的段落
- pandoc 不可用时降级：公式位置显示 `[公式提取失败]`，不中断流程

---

### 4.3 知网参考文献解析（gbt7714_parser.py）

**输入格式（知网导出文本）：**
```
[1] 陈虎, 孙彦丛. 财务共享服务[M]. 北京: 中国财政经济出版社, 2014.
[2] ULBRICH F. The adoption of IT-enabled...[J]. Journal of IT, 2010, 25(2): 168-184.
[3] 国务院.国务院关于印发"十四五"数字经济发展规划的通知[R]. 北京: 国务院, 2022.
```

**解析策略（按顺序尝试）：**
1. 去掉行号 `[1]`
2. 用 `[X]` 或 `[XX/OL]` 定位类型代码
3. 类型代码之前 → 分离作者 + 标题（先找 `. `，找不到找 `.`）
4. 类型代码之后 → 分离期刊/出版社、年份、卷期、页码

**输出格式（hayagriva YAML，Typst 原生）：**
```yaml
ref1:
  type: article
  author:
    - name: {family: 陈虎}
    - name: {family: 孙彦丛}
  title: 财务共享服务
  ...
```

**已知 bug / 限制：**
- `[C]` 会议论文类型代码被 hayagriva 当 article 渲染（无会议 entry type）
- 报纸 `[N]`、网页 `[EB/OL]` 的解析有边界情况
- 中文作者姓名含点分隔（`国务院.国务院关于...`）已修复，回退逻辑是找第一个 `.`

---

### 4.4 IR → Typst 渲染（ir_to_typst.py）

**主要处理步骤：**

1. **特殊段切分**：从 blocks 里识别并剥离"摘要""Abstract""关键词"段，剩余进 body
2. **中括号引用转换**：`[1]` → `@ref1`，`[1-3]` → `@ref1@ref2@ref3`（仅在有参考文献来源时启用）
3. **Typst 转义**：`#` → `\#`，`<` → `\<`，`>` → `\>`，但公式段 `$...$` 原样透传
4. **无编号章节识别**：标题文字匹配"参考文献/致谢/附录"→ 用 `#unnumbered-heading()` 渲染
5. **参考文献替换**：遇到"参考文献"章节时，插入 `#cn-bibliography("references.yml", ...)` 调用，跳过后续手写的文献条目
6. **输出 main.typ**：调用 `thesis(config: ..., meta: ...) { body }` 的 Typst 源码

**关键设计决策：**
- `_BRACKET_TRANSFORM_ENABLED` 全局开关：只有用户提供了参考文献源，才把 `[1]` 转 `@ref1`；否则 Typst 会报 "label does not exist" 编译失败

---

### 4.5 Typst 模板（core.typ）

**模板 API：**
```
thesis(
  config: 学校规范字典,   ← 来自 schools/*.yaml
  meta:   论文元信息字典, ← 来自 paper_meta.yaml
  body:   正文内容       ← 由 ir_to_typst 生成
)
```

**渲染顺序：** 封面 → 中文摘要 → 英文摘要 → 目录 → 正文（页码从 1 重置）

**学校配置参数（generic.yaml）：**
```yaml
fonts: {songti, heiti, kaiti, en}  # 字体族
sizes: {body, h1, h2, h3, title, fig_caption}  # 字号（支持"小四"/pt/数字）
page: {paper, margin}              # 纸张和页边距
paragraph: {leading, spacing, first_indent}  # 段落排版
chapter_prefix: chinese/arabic/none  # 章节前缀样式
bibliography: {style}             # 参考文献样式
```

**添加新学校的工作量：** 复制 generic.yaml → 修改参数 → 约 2-4 小时

---

### 4.6 Web API（prototype/server.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 返回 index.html（注入 `window.WIRED=true`） |
| POST | `/api/process` | 主流水线：上传 docx → 体检 + 编译 → 返回 JSON |
| GET | `/api/pdf/<run_id>` | 返回对应运行产生的 PDF |
| GET | `/api/lint-text/<run_id>` | 返回 lint.json（供下载）|
| GET | `/api/schools` | 返回已配置的学校列表（含 placeholder 标记）|

**POST /api/process 参数：**
```
docx:         文件（multipart）
school:       学校 ID（generic/nju/cqcst）
bib_text:     知网参考文献文本（可选）
title_cn:     论文标题
author:       作者
...（其他元信息字段）
```

**返回结构：**
```json
{
  "ok": true,
  "run_id": "abc123",
  "score": 81,
  "lint": {
    "counts": {"error": 2, "warn": 1, "info": 0},
    "items": [{"severity": "error", "code": "L1", "message": "...", ...}]
  },
  "pdf_url": "/api/pdf/abc123",
  "n_blocks": 81,
  "n_formulas": 2,
  "school_warning": true,
  "school_warning_note": "等待《重庆城市科技学院本科毕业论文撰写规范》原文确认"
}
```

**运行产物暂存：** `/tmp/thesis-helper-runs/<run_id>/`（重启后清空）

---

## 五、前端新人：原型架构

### 5.1 前端技术栈

- **Vanilla JS + CSS**（无框架，无构建工具）
- 单 HTML 文件，所有 CSS/JS 内联
- 依赖零个 npm 包
- 支持两种运行模式：
  - **prototype 模式**：双击 `index.html` 打开，演示内置样本数据
  - **live 模式**：通过 `server.py` 访问，接入真实流水线

### 5.2 页面结构（SPA 单页，纵向分 4 段）

```
┌─── 顶栏（sticky）────────────────────────────┐
│  Logo · 模式徽标  │  步骤进度 1─2─3─4        │
└────────────────────────────────────────────────┘

┌─── 第 1 步：上传 ─────────────────────────────┐
│  Dropzone（拖拽/点击）  │  配置面板            │
│  ▸ 用示例论文演示        │  学校规范下拉        │
│  [pipeline console]      │  参考文献来源        │
│                          │  运行选项 checkbox   │
└────────────────────────────────────────────────┘

┌─── 第 2 步：体检（初始灰显/锁定）────────────┐
│  评分(72) │ 错误(2) │ 警告(4) │ 提示(0)       │
│  问题列表：[×L1] [!L3] [!L3] ...             │
└────────────────────────────────────────────────┘

┌─── 第 3 步：预览（初始锁定）─────────────────┐
│  [封面][目录][正文][参考文献]  │  大图预览      │
│  (缩略图点击切换)              │  [在浏览器打开]│
│                                │  ‹ 1/4 ›      │
└────────────────────────────────────────────────┘

┌─── 第 4 步：下载（初始锁定）─────────────────┐
│  [final.pdf]  [lint.txt]  [main.typ]           │
└────────────────────────────────────────────────┘
```

### 5.3 核心状态机

```javascript
// 4 个阶段，每个有 idle / run / done 三态
pills[0..3]  // 状态徽章（idle/run/done）
dots[0..3]   // 顶栏进度点
sections[0..3].classList.locked  // 段落锁定/解锁

// 演示流水线（prototype 模式）
async function run() {
  // 1. 上传阶段
  setDot(0); setPill(0,'run','处理中…');
  await logLine('→ 读取 docx…', 400);
  setPill(0,'done'); setDot(1);

  // 2. 体检阶段
  unlock(s1); renderLint(LINT_DATA);
  setPill(1,'done');

  // 3. 预览阶段
  unlock(s2); 
  await logLine('→ typst compile…', 750);
  setPill(2,'done');

  // 4. 下载阶段
  unlock(s3); setPill(3,'done');
}
```

### 5.4 两种模式切换机制

```javascript
// server.py 在 </head> 前注入：
// <script>window.WIRED = true;</script>

if (window.WIRED) {
  // live 模式：真实上传
  // 拖入文件 → FormData → POST /api/process
  // 体检数据来自后端 JSON
  // PDF 预览用 iframe + /api/pdf/<run_id>
} else {
  // prototype 模式：用内置 LINT 和 IMGS 数据
  // 触发模拟动画，不发任何网络请求
}
```

### 5.5 关键 DOM 元素 ID

```javascript
// 核心交互元素
'drop'       // Dropzone 区域
'demo-btn'   // 演示按钮
'school-sel' // 学校选择下拉
'school-warn'// placeholder 警告框
'con'        // pipeline console
'ltable'     // 体检问题列表
'pimg'       // 预览大图
'th0'...'th3'// 4张缩略图
'nav-p','nav-n' // 翻页按钮
'dl-lint','dl-typ' // 下载链接

// 状态控件
's0'..'s3'   // 4个 section 元素
'p0'..'p3'   // 4个 pill 状态徽章
.sdot        // 4个顶栏进度点
```

### 5.6 原型构建流程

```bash
# 先生成预览图（需要有编译好的论文）
cp output/accounting/pa-01.png prototype/assets/preview-cover.png
cp output/accounting/pa-04.png prototype/assets/preview-toc.png
cp output/accounting/pa-09.png prototype/assets/preview-body.png
cp output/accounting/pa-12.png prototype/assets/preview-bib.png

# 构建 index.html（注入 base64）
cd prototype/
python build.py
# 输出：index.html（约 1.5 MB，单文件，双击即跑）
```

---

## 六、产品新人：当前状态与路线图

### 6.1 已实现能力地图

```
输入端（docx 解析）
  ✅ 章节标题（Heading 1/2/3 + 中文"标题 N"样式）
  ✅ 普通段落（首行缩进、字体由模板决定）
  ✅ 有序/无序列表（numPr 检测 + 样式名兜底）
  ✅ 表格（自动提取，自动"表 N"编号）
  ✅ 内嵌图片（提取 + 自动"图 N"编号）
  ✅ Word 公式编辑器 OMML（行内 + 块级，pandoc 驱动）
  ✅ 文本数学 $...$ / $$...$$（透传）
  ✅ 中括号引用 [1] / [2,3] / [1-3]（有参考文献时自动转换）
  ✅ 中英文摘要自动识别并提取
  ✅ 致谢/参考文献/附录 无编号章节自动识别

参考文献端
  ✅ 知网 GB/T 7714 文本自动解析（11 种类型代码）
  ✅ BibTeX 直接接入
  ✅ Hayagriva YAML 直接接入
  ✅ 文中上标自动对齐（hayagriva + GB/T 7714-2015 CSS）
  ✅ 参考文献条目 lint（缺标题/年份/期刊名）
  ⚠️ [C] 会议论文类型代码未正确渲染（兜底为 article）
  ⚠️ 报纸[N]/网页[EB/OL] 边界情况解析较弱

模板端
  ✅ 多校 yaml 配置架构（core.typ + schools/*.yaml）
  ✅ 字号支持中文字号/pt/数字 三种写法
  ✅ 封面/摘要/目录/正文/页码 完整结构
  ✅ 章节自动编号（支持中文"第一章"/阿拉伯数字/无前缀）
  ✅ generic 完整实现，nju 已实现
  ⚠️ cqcst（重庆城市科技学院）为 placeholder，参数沿用 generic

格式体检端
  ✅ L1 伪标题检测
  ✅ L2 标题层级跳跃
  ✅ L3 首行缩进缺失
  ✅ L4 字体/字号混用
  ✅ L5 必备章节缺失
  ❌ L6 图表无 caption（代码已有注释但未完全实现）

产品原型端
  ✅ SPA 单页原型（双击 index.html 即跑）
  ✅ Flask 后端（接入真实流水线）
  ✅ prototype / live 双模式切换（顶栏徽标区分）
  ✅ 上传→体检→预览→下载 完整交互流程
```

### 6.2 已知 Bug 清单

| # | 位置 | 描述 | 严重性 |
|---|---|---|---|
| B1 | gbt7714_parser | `[C]` 会议论文渲染为期刊格式 | 中 |
| B2 | lint.py | L6 图表无 caption 规则未完全实现 | 低 |
| B3 | prototype/server.py | 运行结果暂存在 /tmp/，重启丢失，无清理机制 | 低 |
| B4 | ir_to_typst.py | `_BRACKET_TRANSFORM_ENABLED` 是全局变量，多线程调用有竞态风险 | 中 |

### 6.3 路线图（按优先级）

**P0 — 必须做（阻塞用户使用）**

- [ ] **cqcst.yaml 真实化**：目标学校的规范 yaml 仍是 placeholder，PDF 不能直接交给老师  
  → 需要：该校《本科毕业论文撰写规范》文档 / 同学样本 / 关键参数清单

**P1 — 高价值功能**

- [ ] **通电模式元信息表单**：目前只用文件名当 title，需要让用户在页面上填 author/advisor/date 等
- [ ] **公式编号 + 交叉引用**：如 "如式(2-1)所示"，需要在 Typst 里用 `<eq:label>` 打标签
- [ ] **图/表 caption 自动提取**：识别 docx 里"图 1.1：..."模式 + Word 题注样式
- [ ] **L6 规则完整实现**：检测图表是否有 caption
- [ ] **bib_text textarea 入口**：后端 `/api/process` 已支持 `bib_text` 字段，前端没暴露输入框

**P2 — 体验优化**

- [ ] **运行历史**：当前每次上传产生新 run_id，没有历史列表
- [ ] **移动端响应式精修**：< 920px 有降级但没在真机上测过
- [ ] **多校配置补全**：扩展到更多高校
- [ ] **LaTeX → Typst 转换层**：让 docx 里写 `$\frac{a}{b}$` 也能渲染

---

## 七、环境搭建（从零到跑起来）

### 7.1 安装依赖

```bash
# macOS
brew install pandoc typst
# 中文字体（macOS 通常已有宋体黑体）

# Ubuntu / Debian
apt install pandoc fonts-noto-cjk
# typst 需要从 GitHub Releases 手动下载：
# https://github.com/typst/typst/releases → 下 typst-x86_64-unknown-linux-musl.tar.xz
# 解压后把 typst 二进制丢到 /usr/local/bin/

# Python
pip install python-docx pyyaml lxml flask pillow
```

### 7.2 跑 CLI（最快验证）

```bash
git clone https://github.com/haow56782-png/thesis-helper
cd thesis-helper

python run.py examples/accounting_thesis.docx examples/accounting_meta.yaml \
              --school cqcst --out output/test

# 产物：
# output/test/final.pdf    ← 排版后 PDF
# output/test/lint.txt     ← 格式体检报告
# output/test/ir.json      ← 中间 IR（调试用）
# output/test/references.yml ← 参考文献转换结果
```

### 7.3 跑 Web 原型

```bash
# 方式 A：纯演示（无需后端）
cd prototype/
python build.py          # 生成 index.html
open index.html          # macOS
# Windows: start index.html
# Linux: xdg-open index.html

# 方式 B：通电（接真流水线）
python prototype/server.py
# 浏览器打开 http://127.0.0.1:5000/
```

### 7.4 重新生成预览图

```bash
# 先跑出会计学论文 PDF
python run.py examples/accounting_thesis.docx examples/accounting_meta.yaml --school cqcst --out output/accounting

# 用 typst 导出 PNG（需要 typst 0.14+）
typst compile --root output/accounting output/accounting/main.typ \
    "output/accounting/pa-{n}.png" --format png --ppi 130

# 复制到 prototype/assets/
cp output/accounting/pa-01.png prototype/assets/preview-cover.png
cp output/accounting/pa-04.png prototype/assets/preview-toc.png
cp output/accounting/pa-09.png prototype/assets/preview-body.png
cp output/accounting/pa-12.png prototype/assets/preview-bib.png

# 重新构建 index.html
cd prototype/
python build.py
```

---

## 八、数据流详解（给任意角色做深入了解用）

### meta.yaml 格式（论文元信息）

```yaml
title_cn: 数字经济背景下中小企业财务共享服务中心建设研究——以 X 公司为例
title_en: Research on the Construction of Financial Shared Service Center...
author: 王好
student_id: "20210042"
school: 重庆城市科技学院
department: 数智经济管理学院
major: 会计学
advisor: 张教授
advisor_title: 教授
date: 2026 年 5 月
keywords_cn: [数字经济, 财务共享服务中心, 中小企业]
keywords_en: [Digital Economy, Financial Shared Service Center, SMEs]

# 参考文献来源（三选一）
bibliography_text_path: cnki_refs_accounting.txt  # 知网文本
# bibliography_path: references.bib               # BibTeX
# bibliography_path: references.yml               # hayagriva
```

### IR JSON 格式（中间表示样例）

```json
{
  "source": "accounting_thesis.docx",
  "meta": {
    "title_guess": "数字经济背景下...",
    "author_guess": "",
    "n_formulas": 2
  },
  "blocks": [
    {"kind": "heading", "level": 1, "text": "绪论", ...},
    {"kind": "para", "text": "进入 21 世纪以来...", ...},
    {"kind": "equation", "text": "\"CSR\" = ...", "meta": {"display": true}},
    {"kind": "table", "rows": [["环节","再造前","再造后","效率提升"], [...]]},
    {"kind": "figure", "image_path": "images/img_rId5.png", "caption": "图 1.1 系统架构"}
  ]
}
```

---

## 九、常见问题 Q&A

**Q: Typst 编译失败，报 "label does not exist"**
A: 用户 docx 里有 `[1]` 这样的中括号，但没提供参考文献来源。解决：在 meta.yaml 里加 `bibliography_text_path`，或确认 `_BRACKET_TRANSFORM_ENABLED` 正确设为 `False`。

**Q: 公式显示为 `[公式提取失败]`**
A: pandoc 没有安装，或版本过低。安装 pandoc >= 3.0 后重跑。

**Q: 中文字体乱码/显示为方块**
A: Typst 找不到中文字体。Linux 上 `apt install fonts-noto-cjk`；macOS 需要手动安装 Noto Serif CJK SC。

**Q: 学校切换到 cqcst，编译成功但格式和 generic 一样**
A: 正常。cqcst.yaml 目前是 placeholder，参数和 generic 完全一致。需要该校真实规范文档才能填写正确参数。

**Q: 参考文献第 [N] 条没有显示在 PDF 里**
A: 检查知网文本的 `bibliography_text_path` 文件路径是否相对于 meta.yaml 文件位置正确，以及条目数量是否超过 hayagriva 的解析上限（概率极低）。

**Q: index.html 双击打开是空白**
A: 需要先运行 `python prototype/build.py` 生成 index.html（仓库里只有 template，不含 base64 图片）。另外需要先有 `prototype/assets/preview-*.png` 四张图。

---

> 文档维护人：谁修了 bug 谁更新这一段
> 仓库：https://github.com/haow56782-png/thesis-helper
