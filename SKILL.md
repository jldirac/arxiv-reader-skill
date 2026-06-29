---
name: arxiv-reader
description: "自动下载 arXiv 论文的 LaTeX 源文件，提取元信息、章节结构和图片，转换 PDF 图片为 PNG 以便 AI 读取分析。触发词：读arxiv、arxiv论文、读论文、下载arxiv、分析arxiv。"
---

## arXiv 论文自动读取 Skill

自动下载 arXiv 论文的 LaTeX 源文件，解压、解析、转换图片，生成结构化报告供 AI 读取和分析。

## 触发条件

当用户说以下关键词时触发：
- "读arxiv"、"arxiv论文"、"读论文"、"下载arxiv"、"分析arxiv"
- "帮我读一下 arXiv:XXXX"、"看看这篇论文"
- "arxiv 2401.12345" 等任何含 arXiv ID 的读论文请求

## 核心优势

相比直接读 PDF：
- **LaTeX 源码**：公式、结构清晰，可直接读取
- **图片分离**：PDF 嵌入图片独立提取并转为 PNG
- **表格数据**：直接从 `tabular` 环境读取原始数据
- **自动化**：一键完成下载→解析→转换→报告

## 依赖

- **PyMuPDF** (fitz): PDF 图片转 PNG
  ```bash
  uv pip install --python "<python_path>" PyMuPDF
  ```
- Python 内置库: `tarfile`, `urllib.request`, `re`, `json`, `pathlib`

## 使用流程

### 步骤 1：用户提供 arXiv ID

格式支持：`2401.12345`、`arXiv:2401.12345`、`arXiv:2401.12345v1`

### 步骤 2：运行脚本下载并解析

```bash
python3 "<skill_path>/scripts/arxiv_reader.py" <arxiv_id> [output_dir]
```

默认输出到当前工作目录的 `arxiv_<id>/` 子目录。

### 步骤 3：读取生成的报告

脚本输出 JSON 报告到 `arxiv_<id>/report.json`，包含：
- 元信息（标题、作者、摘要）
- 章节结构
- 图片文件列表（已转换的 PNG 路径）
- 关键公式引用

### 步骤 4：AI 读取分析

Agent 读取 `report.json` 获取论文结构，然后：
1. 用 `Read` 读取主 `.tex` 文件的关键章节
2. 用 `ReadMediaFile` 读取转换后的 PNG 图片
3. 输出综合分析

## 脚本输出格式

```json
{
  "status": "success",
  "arxiv_id": "2401.12345",
  "output_dir": "/path/to/arxiv_2401.12345",
  "metadata": {
    "title": "论文标题",
    "authors": ["作者1", "作者2"],
    "abstract": "摘要文本...",
    "keywords": ["关键词1", "关键词2"]
  },
  "structure": {
    "sections": [
      {"name": "Introduction", "label": "sec:intro", "line": 36},
      {"name": "Experiments", "label": "sec:experiment", "line": 1153}
    ]
  },
  "figures": {
    "tex_references": ["Figures/fig1.pdf", "Figures/fig2.png"],
    "converted_png": [
      "converted_figures/fig1_p1.png",
      "converted_figures/fig2_p1.png"
    ]
  },
  "main_tex": "main.tex",
  "files": {
    "tex_files": ["main.tex", "appendix.tex"],
    "bib_files": ["references.bib"],
    "figure_files": ["Figures/fig1.pdf", "Figures/fig2.png"]
  }
}
```

## 文件结构

下载后工作目录结构：

```
arxiv_<id>/
├── main.tex                  # 主论文文本
├── *.tex                     # 其他 tex 文件
├── Figures/
│   ├── fig1.pdf              # 原始 PDF 图片
│   ├── fig2.png              # 原始 PNG 图片
│   └── converted_figures/  # 转换后的 PNG（供 AI 读取）
│       ├── fig1_p1.png
│       └── fig2_p1.png
├── References.bib            # 参考文献
├── report.json               # 结构化报告
└── <id>.tar.gz               # 原始下载包（可选保留）
```

## 技术细节

### arXiv 源文件下载

```
https://arxiv.org/e-print/<arxiv_id>
```

返回 `tar.gz` 压缩包，包含完整的 LaTeX 源文件、图片、参考文献等。

### 主 tex 文件检测

脚本按以下优先级查找主 tex 文件：
1. 文件大小最大的 `.tex`（通常主文件最大）
2. 包含 `\documentclass` 的文件
3. 包含 `\begin{document}` 的文件

### 图片转换

- **PDF 图片**: 使用 PyMuPDF 以 200 DPI 渲染为 PNG
- **JPG/PNG 图片**: 直接复制（已是 AI 可读格式）
- 输出路径: `Figures/converted_figures/`

### tex 解析

使用正则表达式提取：
- `\title\{([^}]+)\}` → 标题
- `\author\{([^}]+)\}` → 作者（简化提取）
- `\begin\{abstract\}.*?\end\{abstract\}` → 摘要
- `\section\{([^}]+)\}` → 章节
- `\includegraphics\[.*?\]\{(.*?)\}` → 图片引用

**注意**: 正则解析对复杂 LaTeX 宏不完全精确，但足以提取论文结构。遇到解析失败时回退到手动读取。

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 下载失败 (404) | arXiv ID 不存在或论文无源文件 | 检查 ID 是否正确；尝试直接下载 PDF 作为备选 |
| 解压失败 | 非 tar.gz 格式或损坏 | 用 `file` 命令检查格式 |
| 无 tex 文件 | 源文件只有 PDF 无 LaTeX | 回退到 PDF 处理 route |
| 图片转换失败 | PyMuPDF 未安装 | 提示安装 `uv pip install PyMuPDF` |
| 复杂 LaTeX 宏 | 正则解析不完整 | 手动读取主 tex 文件补充 |

## 回退方案

如果 arXiv 论文**没有 LaTeX 源文件**（少数论文只提供 PDF）：

1. 尝试下载 PDF: `https://arxiv.org/pdf/<arxiv_id>.pdf`
2. 使用 `pdf` skill 的 `extract text` 和 `extract image` 命令
3. 或使用 `pdf2image` 将 PDF 页面转为图片

## 示例对话

**用户**: "帮我读一下 arXiv 2401.12345"

**Agent**:
1. 运行脚本下载并解析
2. 读取 `report.json` 获取结构
3. 读取 `main.tex` 的摘要和关键章节
4. 读取 `converted_figures/` 下的图片
5. 输出: "这篇论文标题是《Distributionally Robust Receive Combining》，作者是... 主要研究..."

## 扩展建议

- 批量处理：可修改脚本支持多个 arXiv ID
- 缓存机制：检测已下载的目录避免重复下载
- 深度解析：集成 LaTeX 解析库（如 `pylatexenc`）处理更复杂的宏
- 与 Zotero 集成：自动导入到文献管理库
