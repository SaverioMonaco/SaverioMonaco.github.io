#!/usr/bin/env python3
"""Render thesis TikZ figures and plots to SVG for thesis.html, with a dark-theme variant.

For every figure in FIGURES it compiles the TikZ file with the thesis class
(so fonts and colors match the dissertation), crops it, converts it to SVG
(text as outlines), scales it by SCALE, and writes:

    thesis/figures/<name>.svg       light theme (transparent background)
    thesis/figures/<name>.dark.svg  dark theme (colors remapped, see below)

Dark remapping, per color:
  * grays: black -> page text color, white -> dark sub-box background
  * tints (a saturated color mixed with white, e.g. maincolor!30): the same
    saturated color mixed with the dark background instead of with white
  * saturated colors (no white in them) stay as they are

Usage (from the repo root):
    python3 tools/thesis_figures.py            # render everything
    python3 tools/thesis_figures.py mua comb   # only some figures
    python3 tools/thesis_figures.py --dark-only  # just redo the dark variants
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

THESIS = Path.home() / "PhD" / "tex"
OUT = Path(__file__).resolve().parent.parent / "thesis" / "figures"
SCALE = 1.3

# name on the website -> TikZ file (.tex) or plot (.pdf) inside the thesis
FIGURES = {
    "bloch": ("chapters/qc/tikz/bloch.tex", 2.4),  # (path, scale) overrides SCALE
    "simregions": ("chapters/qc/tikz/simregions.tex", 1.0),
    "qml_model": "chapters/qml/tikz/qml_model.tex",
    "bp_landscape": "chapters/qml/plots/bp_landscape.pdf",
    "mua": "chapters/othergen/tikz/mua.tex",
    "comb": "chapters/othergen/tikz/comb.tex",
    "qfan": "chapters/othergen/tikz/qfan.tex",
    "qpce": "chapters/othergen/tikz/qpce.tex",
    "ciqp": "chapters/othergen/tikz/ciqp.tex",
    "ppplargescheme": "chapters/pauliprop/tikz/ppplargescheme.tex",
    "qag_model": "chapters/qag/tikz/qag_model.tex",
}

# Dark theme colors (keep in sync with thesis.html.j2): text and sub-box bg.
DARK_FG = (0xE8, 0xE8, 0xE8)
DARK_BG = (0x22, 0x25, 0x2B)
# How strongly tints fade into the dark background (1 = as much as into white).
TINT_DEPTH = 0.8

TEX = r"""\documentclass{myDissTemplate}
\usepackage{tikz-3dplot}
\input{common/tikzhelpers}
\usepackage{geometry}\geometry{paperwidth=60cm,paperheight=40cm,margin=1cm}
\pagestyle{empty}
\begin{document}
\thispagestyle{empty}
\noindent\input{%s}
\end{document}
"""


def render(name: str, entry, tmp: Path) -> None:
    tikz, factor = entry if isinstance(entry, tuple) else (entry, SCALE)
    if tikz.endswith(".pdf"):  # already a PDF plot: just crop and convert
        shutil.copy(THESIS / tikz, tmp / f"{name}.pdf")
    else:
        compile_tikz(name, tikz, tmp)
    convert(name, tmp, factor)


def compile_tikz(name: str, tikz: str, tmp: Path) -> None:
    src = tmp / f"{name}.tex"
    src.write_text(TEX % tikz.removesuffix(".tex"))
    run = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", f"-output-directory={tmp}", str(src)],
        cwd=THESIS, capture_output=True, text=True,
    )
    if run.returncode != 0:
        errors = [l for l in run.stdout.splitlines() if l.startswith("!")]
        sys.exit(f"{name}: pdflatex failed: {errors[:3]}")


def convert(name: str, tmp: Path, factor: float = SCALE) -> None:
    subprocess.run(["pdfcrop", "--margins", "8", f"{name}.pdf", f"{name}_crop.pdf"],
                   cwd=tmp, check=True, capture_output=True)
    subprocess.run(["pdftocairo", "-svg", f"{name}_crop.pdf", f"{name}.svg"],
                   cwd=tmp, check=True)
    svg = (tmp / f"{name}.svg").read_text()

    def scale(m):
        return re.sub(r'\b(width|height)="([\d.]+)"',
                      lambda a: f'{a.group(1)}="{float(a.group(2)) * factor:.2f}"', m.group(0))
    svg = re.sub(r"<svg [^>]*>", scale, svg, count=1)
    (OUT / f"{name}.svg").write_text(svg)


def dark_color(rgb):
    r, g, b = rgb
    if max(rgb) - min(rgb) < 0.04:  # gray: invert between fg and bg
        l = (r + g + b) / 3
        return tuple(f + (bg - f) * l for f, bg in zip((c / 255 for c in DARK_FG), (c / 255 for c in DARK_BG)))
    t = min(rgb)  # amount of white mixed in
    base = [(c - t) / (1 - t) for c in rgb]
    t *= TINT_DEPTH  # mix in a bit less background than white, so pale shapes stay visible
    return tuple(bc * (1 - t) + (bg / 255) * t for bc, bg in zip(base, DARK_BG))


def make_dark(name: str) -> None:
    svg = (OUT / f"{name}.svg").read_text()

    def repl(m):
        rgb = tuple(float(x) / 100 for x in m.groups())
        r, g, b = (min(max(c, 0), 1) * 100 for c in dark_color(rgb))
        return f"rgb({r:.4f}%, {g:.4f}%, {b:.4f}%)"
    svg = re.sub(r"rgb\(([\d.]+)%, ([\d.]+)%, ([\d.]+)%\)", repl, svg)
    (OUT / f"{name}.dark.svg").write_text(svg)


def main(argv):
    dark_only = "--dark-only" in argv
    names = [a for a in argv if not a.startswith("--")] or list(FIGURES)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            if not dark_only:
                render(name, FIGURES[name], Path(tmp))
            make_dark(name)
            print(f"  {name}.svg + {name}.dark.svg")


if __name__ == "__main__":
    main(sys.argv[1:])
