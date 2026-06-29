# arxiv-reader-skill

自动下载 arXiv 论文的 LaTeX 源文件，提取元信息、章节结构和图片，转换 PDF 图片为 PNG，便于 AI 读取和分析。

## 为什么用这个？

| 对比 | 直接读 PDF | 读 LaTeX 源（本工具） |
|------|-----------|-------------------|
| 文字 | 提取后排版混乱 | 原生源码，公式、结构清晰 |
| 图片 | 需整页截图或 OCR | 独立文件，单独转换读取 |
| 表格 | 需 OCR | 从 `tabular` 环境直接读取 |
| 公式 | 容易丢失符号 | LaTeX 源码完整保留 |
| 自动化 | 低 | 一键下载→解析→转换→报告 |

## 快速开始

### 安装依赖

```bash
pip install PyMuPDF
```

### 使用

```bash
python scripts/arxiv_reader.py <arxiv_id> [output_dir]
```

示例：

```bash
python scripts/arxiv_reader.py 2401.12345
python scripts/arxiv_reader.py 2401.12345 ./papers
```

支持多种 arXiv ID 格式：`2401.12345`、`arXiv:2401.12345`、`https://arxiv.org/abs/2401.12345`

### 输出

脚本会在 `output_dir/arxiv_<id>/` 下生成：

```
arxiv_2401.12345/
├── main.tex              # 主论文文本
├── Figures/
│   ├── fig1.pdf          # 原始 PDF 图片
│   └── converted_figures/  # 转换后的 PNG
│       └── fig1_p1.png
├── report.json           # 结构化报告（元信息、章节、图片列表）
└── 2401.12345.tar.gz     # 原始下载包
```

`report.json` 包含：
- 标题、作者、摘要、关键词
- 完整章节结构（含行号）
- 已转换的 PNG 图片路径

## 与 AI Agent 配合使用

本 Skill 专为 AI Agent（如 Kimi Work）设计。Agent 读取 `report.json` 后：

1. 用 `Read` 读取 `main.tex` 的关键章节
2. 用 `ReadMediaFile` 读取 `converted_figures/` 下的 PNG 图片
3. 综合分析并输出论文摘要

触发词：
- "读arxiv 2401.12345"
- "帮我读一下 arXiv:2401.12345"
- "分析arxiv 2401.12345"

## 文件说明

| 文件 | 说明 |
|------|------|
| `SKILL.md` | Skill 定义文档（触发条件、使用流程、技术细节） |
| `scripts/arxiv_reader.py` | 核心脚本：下载、解压、解析、转换 |

## 技术细节

- **下载**: `https://arxiv.org/e-print/<arxiv_id>` 获取 LaTeX 源文件（tar.gz）
- **主 tex 检测**: 按文件大小 + `\documentclass` + `\begin{document}` 综合评分
- **图片转换**: PyMuPDF 以 200 DPI 渲染 PDF → PNG
- **tex 解析**: 正则提取标题、作者、摘要、章节、图片引用

## 回退方案

如果论文没有 LaTeX 源文件（少数情况），脚本会报错。此时可：

1. 下载 PDF: `https://arxiv.org/pdf/<arxiv_id>.pdf`
2. 使用其他 PDF 处理工具（如 `pdfplumber`、`pikepdf`）

## License

MIT
