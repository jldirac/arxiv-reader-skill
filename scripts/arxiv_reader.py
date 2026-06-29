#!/usr/bin/env python3
"""
arxiv_reader.py - Download, extract, and parse arXiv LaTeX source files.

Usage:
    python arxiv_reader.py <arxiv_id> [output_dir]

Example:
    python arxiv_reader.py 2401.12345
    python arxiv_reader.py 2401.12345 ./papers

Output: JSON report to stdout + structured files in output_dir/arxiv_<id>/
"""

import sys
import re
import json
import tarfile
import urllib.request
from pathlib import Path


def clean_arxiv_id(arxiv_id: str) -> str:
    """Normalize arXiv ID."""
    arxiv_id = arxiv_id.strip().lower()
    arxiv_id = arxiv_id.replace("arxiv:", "").replace("arxiv", "")
    arxiv_id = arxiv_id.replace("https://arxiv.org/abs/", "")
    arxiv_id = arxiv_id.replace("https://arxiv.org/pdf/", "").replace(".pdf", "")
    arxiv_id = arxiv_id.strip()
    # Remove version suffix if present (e.g., v1, v2)
    arxiv_id = re.sub(r'v\d+$', '', arxiv_id)
    return arxiv_id


def download_arxiv_source(arxiv_id: str, output_dir: Path) -> Path:
    """Download arXiv source tar.gz."""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    tar_path = output_dir / f"{arxiv_id}.tar.gz"
    
    print(f"[arxiv-reader] Downloading {url} ...", file=sys.stderr)
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (arxiv-reader/1.0)'
    })
    
    with urllib.request.urlopen(req, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"Download failed: HTTP {response.status}")
        tar_path.write_bytes(response.read())
    
    size_mb = tar_path.stat().st_size / (1024 * 1024)
    print(f"[arxiv-reader] Downloaded: {tar_path} ({size_mb:.2f} MB)", file=sys.stderr)
    return tar_path


def extract_tar(tar_path: Path, extract_dir: Path) -> None:
    """Extract tar.gz to directory."""
    print(f"[arxiv-reader] Extracting to {extract_dir} ...", file=sys.stderr)
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(extract_dir, filter='fully_trusted')
    
    print(f"[arxiv-reader] Extraction complete", file=sys.stderr)


def find_main_tex(root_dir: Path) -> Path:
    """Find the main .tex file in the source directory."""
    tex_files = list(root_dir.rglob("*.tex"))
    
    if not tex_files:
        raise FileNotFoundError("No .tex files found in the extracted source")
    
    # Priority: 1) largest file, 2) contains \documentclass, 3) contains \begin{document}
    candidates = []
    for tex in tex_files:
        content = tex.read_text(encoding='utf-8', errors='ignore')
        score = 0
        if r"\documentclass" in content:
            score += 100
        if r"\begin{document}" in content:
            score += 50
        score += len(content) / 1000  # larger files get higher score
        candidates.append((score, tex, content))
    
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]
    print(f"[arxiv-reader] Main tex file: {best[1].relative_to(root_dir)}", file=sys.stderr)
    return best[1], best[2]


def extract_metadata(content: str) -> dict:
    """Extract title, authors, abstract from tex content."""
    metadata = {
        "title": None,
        "authors": [],
        "abstract": None,
        "keywords": []
    }
    
    # Title: \title{...}
    title_match = re.search(r'\\title\{(.+?)\}(?=[\n\r\\])', content, re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        # Remove line breaks and extra spaces
        title = re.sub(r'\s+', ' ', title.replace('\n', ' '))
        metadata["title"] = title
    
    # Authors: \author{...} - robust extraction
    author_match = re.search(r'\\author\{(.+?)\}(?=[\n\r\\])', content, re.DOTALL)
    if author_match:
        author_text = author_match.group(1)
        # Step 1: Remove common LaTeX commands and environments
        author_text = re.sub(r'\\thanks\{[^}]*\}', '', author_text)
        author_text = re.sub(r'\\IEEEmembership\{[^}]*\}', '', author_text)
        author_text = re.sub(r'\\[a-zA-Z]+\*?(?:\{[^}]*\})?(?:\[[^\]]*\])?', '', author_text)
        author_text = re.sub(r'\\[%&~]', '', author_text)  # Remove \%, \&, \~
        author_text = re.sub(r'\\,', ' ', author_text)
        author_text = re.sub(r'\n+', ' ', author_text)
        # Step 2: Remove trailing comments/artifacts
        author_text = re.sub(r'\s*<-this.*?\)', '', author_text)
        author_text = re.sub(r'\s*\(\s*Corresponding.*?\)', '', author_text, flags=re.IGNORECASE)
        author_text = re.sub(r'\s*\*\s*', '', author_text)
        # Step 3: Split by common delimiters
        authors = re.split(r'[,;]|\band\b', author_text)
        authors = [re.sub(r'\s+', ' ', a).strip() for a in authors if a.strip()]
        # Step 4: Filter out non-name entries (too short, starts with %, etc.)
        authors = [a for a in authors if len(a) > 2 and not a.startswith('%')]
        metadata["authors"] = authors
    
    # Abstract
    abs_match = re.search(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', content, re.DOTALL | re.IGNORECASE)
    if abs_match:
        abstract = abs_match.group(1).strip()
        abstract = re.sub(r'\s+', ' ', abstract.replace('\n', ' '))
        metadata["abstract"] = abstract
    
    # Keywords
    kw_match = re.search(r'\\begin\{keywords\}(.+?)\\end\{keywords\}', content, re.DOTALL | re.IGNORECASE)
    if kw_match:
        keywords_text = kw_match.group(1).strip()
        keywords = [k.strip() for k in re.split(r'[,;]', keywords_text) if k.strip()]
        metadata["keywords"] = keywords
    
    return metadata


def extract_structure(content: str) -> list:
    """Extract section structure from tex."""
    sections = []
    
    # Match \section{Name}\label{label} or just \section{Name}
    for match in re.finditer(r'\\section\{([^}]+)\}(?:\\label\{([^}]+)\})?', content):
        name = match.group(1).strip()
        label = match.group(2) if match.group(2) else None
        line_num = content[:match.start()].count('\n') + 1
        sections.append({
            "name": name,
            "label": label,
            "line": line_num
        })
    
    # Also match subsections
    subsections = []
    for match in re.finditer(r'\\subsection\{([^}]+)\}(?:\\label\{([^}]+)\})?', content):
        name = match.group(1).strip()
        label = match.group(2) if match.group(2) else None
        line_num = content[:match.start()].count('\n') + 1
        subsections.append({
            "name": name,
            "label": label,
            "line": line_num,
            "type": "subsection"
        })
    
    return {"sections": sections, "subsections": subsections}


def extract_figure_references(content: str) -> list:
    """Extract \\includegraphics references from tex."""
    figures = set()
    
    # Match \includegraphics[...]{path}
    for match in re.finditer(r'\\includegraphics\[.*?\]\{([^}]+)\}', content):
        fig_path = match.group(1).strip()
        figures.add(fig_path)
    
    # Also match \includegraphics{path} (without options)
    for match in re.finditer(r'\\includegraphics\{([^}]+)\}', content):
        fig_path = match.group(1).strip()
        figures.add(fig_path)
    
    return sorted(list(figures))


def convert_figures(root_dir: Path, figure_refs: list) -> dict:
    """Convert PDF figures to PNG and list all figures."""
    converted = []
    original = []
    
    # Find actual figure files
    figure_files = []
    for ref in figure_refs:
        # ref might be relative path like "Figures/fig1.pdf"
        possible_paths = [
            root_dir / ref,
            root_dir / (ref + ".pdf"),
            root_dir / (ref + ".png"),
            root_dir / (ref + ".jpg"),
            root_dir / (ref + ".eps"),
        ]
        for p in possible_paths:
            if p.exists():
                figure_files.append(p)
                break
    
    # Also find all files in Figures/ directory
    for fig_dir in root_dir.rglob("Figures"):
        if fig_dir.is_dir():
            for f in fig_dir.iterdir():
                if f.is_file() and f.suffix.lower() in {'.pdf', '.png', '.jpg', '.jpeg', '.eps'}:
                    if f not in figure_files:
                        figure_files.append(f)
    
    if not figure_files:
        return {"original": [], "converted": [], "converted_dir": None}
    
    # Create converted figures directory
    converted_dir = root_dir / "Figures" / "converted_figures"
    converted_dir.mkdir(exist_ok=True)
    
    # Convert PDF files
    try:
        import fitz  # PyMuPDF
        for fig_file in figure_files:
            if fig_file.suffix.lower() == '.pdf':
                try:
                    doc = fitz.open(fig_file)
                    for i, page in enumerate(doc):
                        pix = page.get_pixmap(dpi=200)
                        out_name = converted_dir / f"{fig_file.stem}_p{i+1}.png"
                        pix.save(out_name)
                        converted.append(str(out_name.relative_to(root_dir)))
                    doc.close()
                except Exception as e:
                    print(f"[arxiv-reader] Warning: Failed to convert {fig_file}: {e}", file=sys.stderr)
            elif fig_file.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
                # Already readable, just copy or reference
                from PIL import Image
                try:
                    img = Image.open(fig_file)
                    out_name = converted_dir / f"{fig_file.stem}.png"
                    img.save(out_name)
                    converted.append(str(out_name.relative_to(root_dir)))
                except Exception:
                    # If PIL fails, just reference original
                    converted.append(str(fig_file.relative_to(root_dir)))
            else:
                # EPS or other, just reference original
                converted.append(str(fig_file.relative_to(root_dir)))
    except ImportError:
        print("[arxiv-reader] Warning: PyMuPDF not installed. PDF figures not converted. "
              "Install with: uv pip install PyMuPDF", file=sys.stderr)
    
    original = [str(f.relative_to(root_dir)) for f in figure_files]
    
    return {
        "original": original,
        "converted": converted,
        "converted_dir": str(converted_dir.relative_to(root_dir))
    }


def list_all_files(root_dir: Path) -> dict:
    """List all relevant files in the source directory."""
    tex_files = [str(f.relative_to(root_dir)) for f in root_dir.rglob("*.tex")]
    bib_files = [str(f.relative_to(root_dir)) for f in root_dir.rglob("*.bib")]
    
    # Find all image files
    image_exts = {'.pdf', '.png', '.jpg', '.jpeg', '.eps', '.gif'}
    figure_files = []
    for f in root_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in image_exts:
            figure_files.append(str(f.relative_to(root_dir)))
    
    return {
        "tex_files": sorted(tex_files),
        "bib_files": sorted(bib_files),
        "figure_files": sorted(figure_files)
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python arxiv_reader.py <arxiv_id> [output_dir]", file=sys.stderr)
        sys.exit(1)
    
    arxiv_id = clean_arxiv_id(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    
    try:
        # Step 1: Download
        tar_path = download_arxiv_source(arxiv_id, output_dir)
        
        # Step 2: Extract
        extract_dir = output_dir / f"arxiv_{arxiv_id}"
        extract_tar(tar_path, extract_dir)
        
        # Step 3: Find main tex
        main_tex, tex_content = find_main_tex(extract_dir)
        
        # Step 4: Parse metadata and structure
        metadata = extract_metadata(tex_content)
        structure = extract_structure(tex_content)
        figure_refs = extract_figure_references(tex_content)
        
        # Step 5: Convert figures
        figures = convert_figures(extract_dir, figure_refs)
        
        # Step 6: List all files
        files = list_all_files(extract_dir)
        
        # Step 7: Build report
        report = {
            "status": "success",
            "arxiv_id": arxiv_id,
            "output_dir": str(extract_dir.absolute()),
            "metadata": metadata,
            "structure": structure,
            "figures": figures,
            "main_tex": str(main_tex.relative_to(extract_dir)),
            "files": files
        }
        
        # Save report
        report_path = extract_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # Print report to stdout
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
        print(f"\n[arxiv-reader] Report saved to: {report_path}", file=sys.stderr)
        print(f"[arxiv-reader] Done. Read the main tex file at: {main_tex}", file=sys.stderr)
        
    except Exception as e:
        error_report = {
            "status": "error",
            "arxiv_id": arxiv_id,
            "error": str(type(e).__name__),
            "message": str(e)
        }
        print(json.dumps(error_report, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
