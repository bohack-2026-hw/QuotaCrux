# 演示文稿源文件

`index.html`（版式与内容）、`deck.css`、`deck.js`（页眉页脚与全部 SVG 图表）共同组成 29 页技术演示，1920×1080。每页页脚写明数据来源。

```sh
./build.sh      # 需要 Chrome、node（playwright-core）、uv
```

输出到上一级目录：

- `QuotaCrux.pdf`：浏览器直接打印的矢量 PDF，任何电脑上显示一致；
- `QuotaCrux.pptx`：每页底图是渲染好的图表、截图与背景，所有文字是 PowerPoint 原生文本框，可直接修改；讲稿写在备注里。

字体为 PingFang SC、Avenir Next、Menlo（macOS 自带）；在没有这些字体的电脑上，PPTX 文字会由软件替换字体，展示时以 PDF 为准。`assets/` 中的仓库截图由 `video/` 的回放页面导出，控制台截图直接引用 `frontend/docs/screenshots/`。
