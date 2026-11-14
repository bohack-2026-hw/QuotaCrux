# 演示文稿源文件

`build.py` 用 python-pptx 直接生成 23 页技术演示：所有文字、形状、连线、图表都是 PowerPoint 原生元素；页间为平滑（Morph）切换，每页元素按顺序自动入场，只需点击翻页，按 1920×1080 像素网格排版（`pptkit.py` 提供像素坐标、字体与转场辅助）；`assets/` 里只有 3D 仓库静帧（由 `video/` 页面的 `window.__still` 单独渲染）、控制台截图和二维码。每页讲稿与数据来源写在备注里。

```sh
./build.sh      # -> ../QuotaCrux.pptx 和 ../QuotaCrux.pdf（PDF 为 LibreOffice 对同一文件的渲染）
./preview.sh    # -> preview/m*.jpg，检查版式用
```

需要 uv、LibreOffice（`soffice`）和 Homebrew fontconfig（`/opt/homebrew/etc/fonts/fonts.conf`，让 LibreOffice 用上本机字体）。字体：中文 PingFang SC，英文与数字 Arial，代码 Menlo；在 Windows 上中文会替换为系统自带黑体。每页左上角是取自 bohack.top 的 BoHack 标志（`bohack-mark.png`、`bohack-text.png`，透明背景）。图片不加入场动画（WPS 放映时会丢掉带动画的图片）。控制台截图裁自 `frontend/docs/screenshots/`。
