// ============================================================
//  通用本科论文 Typst 模板  v0.1 (MVP)
//  设计目标：参数化所有学校规范字段，方便复用到不同学校
//  默认值：通用本科规范（黑体三号标题 / 宋体小四正文 / 1.5倍行距 / GB/T 7714）
// ============================================================

#let thesis(
  // ---- 元信息 ----
  title-cn: "本科毕业论文",
  title-en: "Bachelor's Thesis",
  author: "张三",
  student-id: "20210001",
  school: "某某大学",
  department: "某某学院",
  major: "某某专业",
  advisor: "李四",
  advisor-title: "教授",
  date: "2026 年 5 月",
  abstract-cn: [],
  abstract-en: [],
  keywords-cn: ("关键词1", "关键词2", "关键词3"),
  keywords-en: ("keyword1", "keyword2", "keyword3"),
  // ---- 字体（可被学校规范覆盖） ----
  font-songti: ("Source Han Serif SC", "Noto Serif CJK SC", "SimSun"),
  font-heiti: ("Source Han Sans SC", "Noto Sans CJK SC", "SimHei"),
  font-kaiti: ("KaiTi", "STKaiti"),
  font-en: ("Times New Roman", "Liberation Serif"),
  // ---- 页面 ----
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 3cm, right: 2.5cm),
  // ---- 字号（pt 与中文字号对应：小四 = 12pt, 五号 = 10.5pt, 小三 = 15pt, 三号 = 16pt, 二号 = 22pt, 小二 = 18pt） ----
  size-body: 12pt,        // 正文：小四
  size-h1: 16pt,          // 一级标题：三号
  size-h2: 14pt,          // 二级标题：四号
  size-h3: 13pt,          // 三级标题：小四加粗
  size-title: 22pt,       // 论文标题：二号
  // ---- 行距 ----
  leading: 1em,           // ≈ 1.5 倍行距视觉效果（Typst 的 leading 是行间距，不是行高）
  par-spacing: 0.7em,
  // ---- 内容 ----
  body
) = {
  // ============= 全局文档设置 =============
  set document(title: title-cn, author: author)
  set page(
    paper: paper,
    margin: margin,
    numbering: "1",
    number-align: center,
  )
  set text(
    font: font-songti,
    size: size-body,
    lang: "zh",
    region: "cn",
  )
  set par(
    leading: leading,
    spacing: par-spacing,
    first-line-indent: (amount: 2em, all: true),
    justify: true,
  )

  // ============= 标题样式 =============
  show heading: it => {
    set text(font: font-heiti, weight: "bold")
    set par(first-line-indent: 0em)
    if it.level == 1 {
      pagebreak(weak: true)
      v(1em)
      set text(size: size-h1)
      block(below: 1em, align(center, it))
    } else if it.level == 2 {
      v(0.5em)
      set text(size: size-h2)
      block(below: 0.6em, it)
    } else {
      set text(size: size-h3)
      block(below: 0.4em, it)
    }
  }

  // 标题编号（一级带"第X章"，二三级用 1.1 / 1.1.1）
  set heading(numbering: (..nums) => {
    let n = nums.pos()
    if n.len() == 1 {
      "第 " + numbering("一", n.at(0)) + " 章  "
    } else {
      nums.pos().map(str).join(".") + "  "
    }
  })

  // ============= 图表 caption =============
  show figure.caption: it => {
    set text(font: font-heiti, size: 10.5pt)
    it
  }
  set figure(numbering: "1-1")

  // ============= 封面 =============
  page(numbering: none, margin: (top: 4cm, bottom: 3cm, x: 3cm))[
    #set align(center)
    #v(2cm)
    #text(font: font-heiti, size: 18pt, school)
    #v(0.5em)
    #text(font: font-heiti, size: 16pt, "本科毕业论文")
    #v(4cm)
    #text(font: font-heiti, size: size-title, weight: "bold", title-cn)
    #v(0.5em)
    #text(font: font-en, size: 14pt, style: "italic", title-en)
    #v(3cm)
    #set text(size: 14pt)
    #grid(
      columns: (auto, auto),
      column-gutter: 1em,
      row-gutter: 1em,
      align: (right, left),
      "学　　院：", department,
      "专　　业：", major,
      "学　　号：", student-id,
      "作　　者：", author,
      "指导教师：", advisor + "　" + advisor-title,
      "完成日期：", date,
    )
  ]

  // ============= 中文摘要 =============
  page(numbering: "I", number-align: center)[
    #set par(first-line-indent: (amount: 2em, all: true))
    #align(center, text(font: font-heiti, size: size-h1, "摘　要"))
    #v(1em)
    #abstract-cn
    #v(1em)
    #par(first-line-indent: 0em)[
      #text(font: font-heiti, "关键词：")#keywords-cn.join("；")
    ]
  ]

  // ============= 英文摘要 =============
  pagebreak()
  align(center, text(font: font-en, size: size-h1, weight: "bold", "Abstract"))
  v(1em)
  set text(font: font-en)
  abstract-en
  v(1em)
  par(first-line-indent: 0em)[
    #text(weight: "bold", "Keywords: ")#keywords-en.join("; ")
  ]
  set text(font: font-songti)

  // ============= 目录 =============
  pagebreak()
  align(center, text(font: font-heiti, size: size-h1, "目　录"))
  v(0.8em)
  outline(title: none, depth: 3, indent: auto)

  // ============= 正文 =============
  pagebreak()
  counter(page).update(1)
  set page(numbering: "1")
  body

  // ============= 参考文献 / 致谢 由用户在 body 中按章节写入 =============
}
