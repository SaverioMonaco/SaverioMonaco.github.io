import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml

from .generator import Generator, Tailoring


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


APP_TEMPLATE_DIR = Path(__file__).parent / "templates" / "application"


@cli.command()
@click.argument("name")
@click.option("--dest-dir", default="applications", show_default=True,
              help="Parent directory for applications.")
def new(name, dest_dir):
    """Start a tailored CV + motivation letter in DEST_DIR/NAME."""
    dest_path = Path(dest_dir) / name
    dest_path.mkdir(parents=True, exist_ok=True)
    # Works on a folder you already made (e.g. with a logo in it): only the
    # missing starter files are added, existing ones are never overwritten.
    for src in sorted(APP_TEMPLATE_DIR.iterdir()):
        dst = dest_path / src.name
        if dst.exists():
            click.echo(f"  kept existing {dst}")
        else:
            shutil.copy2(src, dst)
            click.echo(f"  created {dst}")
    click.echo(f"Edit application.yaml and letter.tex in {dest_path}, "
               f"then run `make app NAME={name}`.")


def _run(cmd, cwd):
    """Run a LaTeX tool quietly; on failure show the end of its log."""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        click.echo(f"Error: `{' '.join(cmd)}` failed in {cwd}:", err=True)
        click.echo("\n".join(proc.stdout.splitlines()[-30:]), err=True)
        sys.exit(1)


@cli.command()
@click.argument("name")
@click.option("--data-dir", default="data", show_default=True,
              help="Directory containing YAML data files.")
@click.option("--dest-dir", default="applications", show_default=True,
              help="Parent directory for applications.")
@click.option("--cls", "cls_file", default="awesome-cv.cls", show_default=True,
              help="Awesome-CV class file.")
@click.option("--no-pdf", is_flag=True, help="Only write the .tex files, don't compile.")
def app(name, data_dir, dest_dir, cls_file, no_pdf):
    """Build DEST_DIR/NAME/cv.pdf and letter.pdf from its application.yaml."""
    app_dir = Path(dest_dir) / name
    cfg_path = app_dir / "application.yaml"
    if not cfg_path.is_file():
        click.echo(f"Error: {cfg_path} not found (create it with `make new NAME={name}`).", err=True)
        sys.exit(1)
    app_cfg = yaml.safe_load(cfg_path.read_text()) or {}

    build_dir = app_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    tailoring = Tailoring(app_cfg.get("cv"))
    generator = Generator(Path(data_dir), build_dir, tailoring)
    try:
        has_refs = generator.generate_application(app_dir, app_cfg)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    shutil.copy2(cls_file, build_dir / Path(cls_file).name)

    for rule in tailoring.unused_rules():
        click.echo(f"Warning: {rule} matched nothing in the CV data", err=True)

    if no_pdf:
        return
    tex = ["lualatex", "-interaction=nonstopmode", "-halt-on-error"]
    for doc, bib in (("cv", True), ("letter", has_refs)):
        _run(tex + [f"{doc}.tex"], build_dir)
        if bib:
            _run(["biber", doc], build_dir)
            _run(tex + [f"{doc}.tex"], build_dir)
            _run(tex + [f"{doc}.tex"], build_dir)
        shutil.copy2(build_dir / f"{doc}.pdf", app_dir / f"{doc}.pdf")
    click.echo(f"Built {app_dir / 'cv.pdf'} and {app_dir / 'letter.pdf'}")
