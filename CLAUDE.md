# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`html2md` is a Python CLI tool that converts technical documentation from HTML format to structured Markdown files using pandoc. It restores chapter numbers from table of contents, splits documents by chapters, and organizes media files per chapter. Built with Poetry for dependency management and uses Typer for the CLI interface.

## Development Commands

### Setup and Installation
```bash
poetry install
```

### Running the Application
```bash
# Main conversion command
poetry run html2md from-html-pandoc input.html --out output_dir --split-level 1

# Available options:
# --out: Output directory (default: output)
# --split-level: Heading level to split chapters (default: 1)
# --media-dir: Media directory name (default: media)
# --remove-toc: Remove table of contents from output
# --keep-temp: Keep temporary files for debugging
```

### Testing and Code Quality
```bash
# Linting and formatting
ruff .
black --check .
mypy .

# Run tests
pytest
```

## Architecture

The application follows a pandoc-based pipeline architecture with distinct phases:

1. **Number Restoration** (`restore_numbers.lua`): Restores chapter numbers from TOC using pandoc Lua filter
2. **Splitting** (`splitter.py`): Breaks numbered HTML into chapters by heading level
3. **Pandoc Processing**: Converts each chapter to GitHub Flavored Markdown with media extraction
4. **Navigation** (`navigation.py`): Creates SUMMARY.md and manages inter-chapter links
5. **Validation** (`validators.py`): Runs quality checks on output (HTML-specific validations disabled)

### Key Components

- **CLI Entry Point**: `src/doc2md/cli.py` - Main Typer application with `from-html-pandoc` command
- **Configuration**: `src/doc2md/config.py` - Default settings (LLM configs maintained but not used)
- **Lua Filter**: `restore_numbers.lua` - Pandoc filter for restoring chapter numbers from TOC
- **Schema**: `src/doc2md/schema.py` - Data structure definitions

### Configuration Files

- **Lua Filter**: `restore_numbers.lua` - Pandoc filter for number restoration
- **Environment**: `.env` file (maintained for potential future LLM features)

The pipeline is designed to be modular, using pandoc for reliable HTML to Markdown conversion with proper media handling and chapter organization.