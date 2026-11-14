# 项目介绍与演示材料

先用项目介绍了解系统，再按脚本演示；功能和效果的依据分别查需求、验收记录与实验批次。

| 材料 | 源文件或演示文件 | 导出 |
| --- | --- | --- |
| 项目介绍 | [Markdown](project-overview.md) | [PDF](project-overview.pdf) |
| 现场演示脚本 | [Markdown](demo-script.md) | — |
| 技术演示文稿（23 页） | [源文件](slides/) · [PowerPoint](QuotaCrux.pptx) | [PDF](QuotaCrux.pdf) |
| 展示视频（2:43） | [手稿](../video/QuotaCrux-video-manuscript.md) | [MP4](../video/QuotaCrux-showcase.mp4) |
| 海报 | [生成脚本](../../backend/scripts/build_poster.py) | [PDF](../poster/QuotaCrux-poster.pdf) · [预览](../poster/倍漾量化-瀚海Vastsea-枢决QuotaCrux.jpg) · [场景预览](../poster/QuotaCrux-xbanner-mockup.jpg) |

演示文稿由 [slides/](slides/) 中的 `build.py` 生成，全部为 PowerPoint 原生形状与文字。旧版两份文稿及其 python-pptx 生成脚本的输出已移到 [archive/presentation-v1](../archive/presentation-v1/)。海报由 `backend/scripts/build_poster.py` 生成到 `docs/poster/`。

Markdown 导出 PDF 时，从 `backend/` 执行：

```sh
scripts/export_pdf.sh presentation/project-overview requirements/acceptance-record
```

核对材料中的功能与数字时，查看[验收记录](../requirements/acceptance-record.md)、[实验批次](../research/README.md)和[经验学习历史结果](../archive/memory-learning-results.md)。

[返回文档导航](../README.md)。
