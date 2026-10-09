import sys
from pathlib import Path

import click

from .generator import Generator


@click.group()
def cli():
    """cv-builder: Generate Awesome-CV LaTeX files from YAML data."""


@cli.command()
@click.option("--data-dir", default="data", show_default=True,
              help="Directory containing YAML data files.")
@click.option("--output-dir", default="examples", show_default=True,
              help="Directory to write generated LaTeX files.")
def build(data_dir, output_dir):
    """Generate LaTeX section files from YAML data."""
    data_path = Path(data_dir)
    output_path = Path(output_dir)

    if not data_path.exists():
        click.echo(f"Error: data directory '{data_dir}' not found.", err=True)
        sys.exit(1)

    Generator(data_path, output_path).generate()


@cli.command()
@click.argument("name")
@click.option("--data-dir", default="data", show_default=True,
              help="Directory containing YAML data files.")
@click.option("--output-dir", default="build", show_default=True,
              help="Directory to write generated LaTeX files.")
@click.option("--dest-dir", default="applications", show_default=True,
              help="Parent directory for exported applications.")
@click.option("--cls", "cls_file", default="awesome-cv.cls", show_default=True,
              help="Awesome-CV class file to copy alongside the sources.")
def export(name, data_dir, output_dir, dest_dir, cls_file):
    """Copy the current cv.tex and motivational letter into DEST_DIR/NAME
    so they can be customized for one application."""
    data_path = Path(data_dir)
    dest_path = Path(dest_dir) / name
    cls_path = Path(cls_file)

    if not data_path.exists():
        click.echo(f"Error: data directory '{data_dir}' not found.", err=True)
        sys.exit(1)
    if not cls_path.is_file():
        click.echo(f"Error: class file '{cls_file}' not found.", err=True)
        sys.exit(1)
    if dest_path.exists():
        click.echo(f"Error: '{dest_path}' already exists; not overwriting it.", err=True)
        sys.exit(1)

    generator = Generator(data_path, Path(output_dir))
    generator.generate()
    generator.export(dest_path, cls_path)
    click.echo(f"Exported to {dest_path} — edit the .tex files, then run `make` there.")
