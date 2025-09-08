import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress
from slugify import slugify

from . import navigation, postprocess, preprocess, prompt_builder, splitter, validators
from .config import DEFAULT_MODEL, DEFAULT_PROVIDER, OPENROUTER_DEFAULT_MODEL, MISTRAL_DEFAULT_MODEL
from .llm_client import ClientFactory

logging.basicConfig(level=logging.INFO)

app = typer.Typer(help="Convert DOCX documentation to Markdown.")
console = Console()


def get_default_model_for_provider(provider: str) -> str:
    """Get the default model for a given provider."""
    if provider.lower() == "mistral":
        return MISTRAL_DEFAULT_MODEL
    else:  # openrouter or default
        return OPENROUTER_DEFAULT_MODEL


@app.callback()
def main() -> None:
    """Main entry point for the CLI."""
    pass


@app.command()
def from_html_pandoc(
    html_path: str = typer.Argument(..., help="Путь к входному HTML файлу."),
    output_dir: str = typer.Option(
        "output", "--out", "-o", help="Директория для сохранения Markdown файлов."
    ),
    split_level: int = typer.Option(
        1, "--split-level", help="Уровень заголовка для разделения на главы (1 для h1, 2 для h2, etc.)."
    ),
    media_dir: str = typer.Option(
        "media", "--media-dir", help="Название директории для медиа файлов."
    ),
    remove_toc: bool = typer.Option(
        True, "--remove-toc/--keep-toc", help="Удалить оглавление из финального вывода."
    ),
    keep_temp: bool = typer.Option(
        False, "--keep-temp", help="Сохранить временные файлы для отладки."
    ),
) -> None:
    """Run the pandoc-based HTML to Markdown conversion pipeline."""
    import subprocess
    import tempfile
    import shutil
    from pathlib import Path as P
    
    logging.getLogger(__name__).info("Running the pandoc pipeline")
    console.print(f"[bold green]Запуск конвертации для файла:[/] {html_path}")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Restore numbers in headings using pandoc + Lua filter
    console.print("[yellow]Шаг 1: Восстановление номеров в заголовках[/]")
    lua_filter_path = Path(__file__).parent / "restore_numbers.lua"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_numbered:
        numbered_html_path = temp_numbered.name
    
    try:
        subprocess.run([
            "pandoc", html_path,
            "--from=html", "--to=html",
            "--standalone",
            f"--lua-filter={lua_filter_path}",
            "-o", numbered_html_path
        ], check=True)
        
        # Step 2: Split HTML into chapters
        console.print("[yellow]Шаг 2: Разделение на главы[/]")
        chapters_dir = output_path / "_chapters" 
        chapters_dir.mkdir(exist_ok=True)
        
        # Read numbered HTML and split by heading level
        with open(numbered_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        chapters = splitter.split_html_by_heading_level(html_content, split_level)
        
        # Step 3: Convert each chapter to markdown with pandoc
        console.print(f"[yellow]Шаг 3: Конвертация {len(chapters)} глав в Markdown[/]")
        
        with Progress() as progress:
            task = progress.add_task("Converting chapters", total=len(chapters))
            
            for idx, (title, chapter_html) in enumerate(chapters, start=1):
                # Save chapter HTML
                chapter_slug = slugify(title) if title else f"chapter_{idx:02d}"
                chapter_filename = f"{idx:02d}.{chapter_slug}"
                chapter_html_path = chapters_dir / f"{chapter_filename}.html"
                
                with open(chapter_html_path, 'w', encoding='utf-8') as f:
                    f.write(f"<html><body>{chapter_html}</body></html>")
                
                # Create media directory for this chapter
                chapter_media_dir = output_path / media_dir / f"ch{idx:02d}"
                chapter_media_dir.mkdir(parents=True, exist_ok=True)
                
                # Convert to markdown with pandoc
                chapter_md_path = output_path / f"{chapter_filename}.md"
                
                subprocess.run([
                    "pandoc", str(chapter_html_path),
                    "--from=html", "--to=gfm",
                    f"--extract-media={chapter_media_dir}",
                    "--wrap=none",
                    "-o", str(chapter_md_path)
                ], check=True)
                
                progress.advance(task)
        
        # Step 4: Generate navigation
        console.print("[yellow]Шаг 4: Создание навигации[/]")
        navigation.create_summary_from_chapters(str(output_path))
        
        # Cleanup temporary files if not keeping them
        if not keep_temp:
            shutil.rmtree(chapters_dir, ignore_errors=True)
            Path(numbered_html_path).unlink(missing_ok=True)
        
        console.print(f"[bold green]Конвертация завершена. Результаты в:[/] {output_dir}")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Ошибка pandoc: {e}[/]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
