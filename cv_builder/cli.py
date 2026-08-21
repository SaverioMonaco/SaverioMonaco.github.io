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
