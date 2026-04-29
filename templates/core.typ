// ============================================================
//  通用本科论文 Typst 模板  core.typ  v0.2
//  设计目标：
//    - 所有学校规范从 config 字典注入，零代码切换学校
//    - "致谢/参考文献"等不参与章节编号，在 body 中用专用函数声明
//    - 摘要 / 目录 / 正文 三段式结构由模板控制，用户只关心内容
// ============================================================

// ---------- 工具函数 ----------

#let _get(c, key, default) = if key in c { c.at(key) } else { default }

// 中文字号 → pt 映射（教育部 GB 9851.3-1990）
#let cn-size(s) = (
  "初号": 42pt, "小初": 36pt,
  "一号": 26pt, "小一": 24pt,
  "二号": 22pt, "小二": 18pt,
  "三号": 16pt, "小三": 15pt,
  "四号": 14pt, "小四": 12pt,
  "五号": 10.5pt, "小五": 9pt,
).at(s, default: 12pt)

// 把 yaml 传来的字符串字号统一成 pt。可传 "小四"、"12pt"、12 等
#let resolve-size(v) = {
  if type(v) == length { v }
  else if type(v) == int or type(v) == float { v * 1pt }
  else if type(v) == str {
    if v.ends-with("pt") { float(v.slice(0, -2)) * 1pt }
    else { cn-size(v) }
  } else { 12pt }
}

// ---------- 无编号大标题（致谢、参考文献等） ----------

#let unnumbered-heading(title) = {
  pagebreak(weak: true)
  set par(first-line-indent: 0em)
  v(1em)
  align(center, text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "SimHei"),
                     size: 16pt, weight: "bold", title))
  v(0.8em)
}

// ---------- 参考文献块（直接接 .bib 或 .yaml，套 GB/T 7714） ----------

#let cn-bibliography(path, style: "gb-7714-2015-numeric", title: "参考文献") = {
  pagebreak(weak: true)
  set par(first-line-indent: 0em)
  bibliography(path, style: style, title: text(
    font: ("Source Han Sans SC", "Noto Sans CJK SC", "SimHei"),
    size: 16pt, weight: "bold", title
  ))
}

// ---------- 主入口 ----------

#let thesis(
  config: (:),       // 学校规范配置（yaml 注入）
  meta: (:),         // 论文元信息（标题、作者、摘要等）
  body
) = {
  // ===== 解析 config =====
  let fonts = _get(config, "fonts", (:))
  let f-songti = _get(fonts, "songti", ("Source Han Serif SC", "Noto Serif CJK SC", "SimSun"))
  let f-heiti  = _get(fonts, "heiti",  ("Source Han Sans SC", "Noto Sans CJK SC", "SimHei"))
  let f-kaiti  = _get(fonts, "kaiti",  ("KaiTi", "STKaiti"))
  let f-en     = _get(fonts, "en",     ("Times New Roman", "Liberation Serif"))

  let sizes = _get(config, "sizes", (:))
  let s-body  = resolve-size(_get(sizes, "body",  "小四"))
  let s-h1    = resolve-size(_get(sizes, "h1",    "三号"))
  let s-h2    = resolve-size(_get(sizes, "h2",    "四号"))
  let s-h3    = resolve-size(_get(sizes, "h3",    "小四"))
  let s-title = resolve-size(_get(sizes, "title", "二号"))
  let s-fig-cap = resolve-size(_get(sizes, "fig_caption", "五号"))

  let page-cfg = _get(config, "page", (:))
  let m = _get(page-cfg, "margin", (:))
  let margin = (
    top:    eval(_get(m, "top",    "2.5cm")),
    bottom: eval(_get(m, "bottom", "2.5cm")),
    left:   eval(_get(m, "left",   "3cm")),
    right:  eval(_get(m, "right",  "2.5cm")),
  )
  let paper = _get(page-cfg, "paper", "a4")

  let par-cfg = _get(config, "paragraph", (:))
  let leading = eval(_get(par-cfg, "leading", "1em"))
  let par-spacing = eval(_get(par-cfg, "spacing", "0.7em"))
  let first-indent = eval(_get(par-cfg, "first_indent", "2em"))

  let chapter-prefix = _get(config, "chapter_prefix", "chinese")  // "chinese" | "arabic" | "none"

  // ===== 全局样式 =====
  set document(
    title: _get(meta, "title_cn", "本科毕业论文"),
    author: _get(meta, "author", ""),
  )
  set page(paper: paper, margin: margin, numbering: "1", number-align: center)
  set text(font: f-songti, size: s-body, lang: "zh", region: "cn")
  set par(
    leading: leading,
    spacing: par-spacing,
    first-line-indent: (amount: first-indent, all: true),
    justify: true,
  )

  // ===== 标题 =====
  show heading: it => {
    set text(font: f-heiti, weight: "bold")
    set par(first-line-indent: 0em)
    if it.level == 1 {
      pagebreak(weak: true)
      v(1em)
      set text(size: s-h1)
      block(below: 1em, align(center, it))
    } else if it.level == 2 {
      v(0.5em)
      set text(size: s-h2)
      block(below: 0.6em, it)
    } else {
      set text(size: s-h3)
      block(below: 0.4em, it)
    }
  }

  set heading(numbering: (..nums) => {
    let n = nums.pos()
    if n.len() == 1 {
      if chapter-prefix == "chinese" {
        "第 " + numbering("一", n.at(0)) + " 章  "
      } else if chapter-prefix == "arabic" {
        str(n.at(0)) + "  "
      } else { "" }
    } else {
      n.map(str).join(".") + "  "
    }
  })

  // 图表
  show figure.caption: it => {
    set text(font: f-heiti, size: s-fig-cap)
    it
  }
  set figure(numbering: "1-1")

  // ===== 封面 =====
  let school = _get(meta, "school", "")
  let title-cn = _get(meta, "title_cn", "")
  let title-en = _get(meta, "title_en", "")
  page(numbering: none, margin: (top: 4cm, bottom: 3cm, x: 3cm))[
    #set align(center)
    #v(2cm)
    #text(font: f-heiti, size: 18pt, school)
    #v(0.5em)
    #text(font: f-heiti, size: 16pt, _get(config, "cover_subtitle", "本科毕业论文"))
    #v(4cm)
    #text(font: f-heiti, size: s-title, weight: "bold", title-cn)
    #if title-en != "" [
      #v(0.5em)
      #text(font: f-en, size: 14pt, style: "italic", title-en)
    ]
    #v(3cm)
    #set text(size: 14pt)
    #grid(
      columns: (auto, auto),
      column-gutter: 1em,
      row-gutter: 1em,
      align: (right, left),
      "学　　院：", _get(meta, "department", ""),
      "专　　业：", _get(meta, "major", ""),
      "学　　号：", _get(meta, "student_id", ""),
      "作　　者：", _get(meta, "author", ""),
      "指导教师：", _get(meta, "advisor", "") + "　" + _get(meta, "advisor_title", ""),
      "完成日期：", _get(meta, "date", ""),
    )
  ]

  // ===== 中文摘要 =====
  let abs-cn = _get(meta, "abstract_cn", [])
  let kw-cn = _get(meta, "keywords_cn", ())
  page(numbering: "I", number-align: center)[
    #set par(first-line-indent: (amount: first-indent, all: true))
    #align(center, text(font: f-heiti, size: s-h1, "摘　要"))
    #v(1em)
    #abs-cn
    #v(1em)
    #par(first-line-indent: 0em)[
      #text(font: f-heiti, "关键词：")#kw-cn.join("；")
    ]
  ]

  // ===== 英文摘要 =====
  let abs-en = _get(meta, "abstract_en", [])
  let kw-en = _get(meta, "keywords_en", ())
  pagebreak()
  align(center, text(font: f-en, size: s-h1, weight: "bold", "Abstract"))
  v(1em)
  set text(font: f-en)
  abs-en
  v(1em)
  par(first-line-indent: 0em)[
    #text(weight: "bold", "Keywords: ")#kw-en.join("; ")
  ]
  set text(font: f-songti)

  // ===== 目录 =====
  pagebreak()
  align(center, text(font: f-heiti, size: s-h1, "目　录"))
  v(0.8em)
  outline(title: none, depth: 3, indent: auto)

  // ===== 正文 =====
  pagebreak()
  counter(page).update(1)
  set page(numbering: "1")
  body
}
