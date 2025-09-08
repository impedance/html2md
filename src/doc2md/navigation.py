"""Navigation utilities for generated Markdown files."""

from __future__ import annotations

import json
import os
import re
from typing import List, Dict
from pathlib import Path

import frontmatter


def inject_navigation_and_create_toc(output_dir: str) -> None:
    """Inject readPrev/readNext into Markdown files and create toc.json."""
    files = sorted(f for f in os.listdir(output_dir) if f.endswith(".md"))
    titles: Dict[str, str] = {}
    for name in files:
        path = os.path.join(output_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)
        titles[name] = post.get("title", "")

    toc: List[Dict[str, str]] = []
    for idx, name in enumerate(files):
        path = os.path.join(output_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)
        if idx > 0:
            prev = files[idx - 1]
            post["readPrev"] = {
                "to": f"/{os.path.splitext(prev)[0]}",
                "label": titles[prev],
            }
        if idx < len(files) - 1:
            nxt = files[idx + 1]
            post["readNext"] = {
                "to": f"/{os.path.splitext(nxt)[0]}",
                "label": titles[nxt],
            }
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        toc.append({"title": titles[name], "to": f"/{os.path.splitext(name)[0]}"})

    with open(os.path.join(output_dir, "toc.json"), "w", encoding="utf-8") as f:
        json.dump(toc, f, ensure_ascii=False, indent=2)


def create_summary_from_chapters(output_dir: str) -> None:
    """Create SUMMARY.md from generated markdown chapters."""
    output_path = Path(output_dir)
    
    # Find all markdown files (excluding SUMMARY.md itself)
    md_files = sorted([
        f for f in output_path.glob("*.md") 
        if f.name not in ("SUMMARY.md", "README.md")
    ])
    
    if not md_files:
        return
    
    # Extract titles from first line of each file
    summary_lines = ["# Summary\n\n"]
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Extract the first heading as title
            title = extract_first_heading(content)
            if not title:
                # Fallback to filename
                title = md_file.stem.replace('_', ' ').replace('-', ' ').title()
            
            # Create markdown link
            summary_lines.append(f"- [{title}]({md_file.name})\n")
            
        except Exception as e:
            print(f"Warning: Could not process {md_file}: {e}")
            continue
    
    # Write SUMMARY.md
    summary_path = output_path / "SUMMARY.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.writelines(summary_lines)


def extract_first_heading(content: str) -> str:
    """Extract the first heading from markdown content."""
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            # Remove leading # symbols and clean up
            title = re.sub(r'^#+\s*', '', line)
            title = title.strip()
            return title
    
    return ""


__all__ = [
    "inject_navigation_and_create_toc", 
    "create_summary_from_chapters",
    "extract_first_heading"
]
