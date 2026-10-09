# SaverioMonaco.github.io

Personal website: CV in PDF and HTML, published with GitHub Pages.

The CV (both the PDF and the HTML version) is generated from YAML data files using a small Python tool called `cv_builder`. You edit YAML, run one command, and it produces the LaTeX sources, the PDF, and the HTML page.

## How it works

* `data/` holds all the content as YAML: `personal.yaml` for name/contact/photo, `config.yaml` for layout and section order, and `data/cv/*.yaml` for each CV section (education, experience, publications, talks, posters, etc).
* `cv_builder/` is the Python package that reads that YAML and renders it into files using Jinja2 templates in `cv_builder/templates/`.
* `awesome-cv.cls` is the LaTeX class (from the Awesome-CV project, see `LICENCE-awesome-cv`) used to typeset `cv.pdf`.
* `cv_builder/templates/cv.html.j2` renders the web version of the CV, `cv.tex.j2` renders the LaTeX/PDF version.
* Running the builder writes intermediate `.tex` files into `build/`, then the Makefile copies the final outputs to the repo root: `index.html`, `gym.html`, `cv.pdf`.
* `gym.html` is generated separately from a workout diary CSV export in `data/gym/`.
* `projects/` and `talks/` / `posters/` hold static pages and PDFs (slides, posters) linked from the CV.

## Editing content

Most changes only require editing a YAML file under `data/`, for example:

* `data/personal.yaml`: name, contact info, social links, photo.
* `data/config.yaml`: colors, section order, which sections appear in the PDF vs the web page.
* `data/cv/*.yaml`: one file per CV section.
* `data/cv/upcoming.yaml`: goals shown only on the web CV, not the PDF.

No LaTeX or HTML editing is needed for normal content updates.

## How to compile

Requirements: Python 3.9+, and for the PDF, a LaTeX distribution with `lualatex` and `biber`.

Install the builder once:

```
make install
```

Generate everything (index.html, gym.html, cv.pdf):

```
make
```

Or generate a single output:

```
make index.html
make gym.html
make cv.pdf
```

Clean generated files:

```
make clean
```

Under the hood, `make` calls the `cv-builder` CLI directly:

```
cv-builder build --data-dir data --output-dir build
```

which regenerates everything under `build/`, then the Makefile copies the relevant files to the repo root.

## Tailoring a CV and motivational letter for an application

```
make export NAME=acme
```

This regenerates the sources and copies the current `cv.tex` (with its `cv/` sections and `bib.bib`), a motivational letter template `coverletter.tex`, `awesome-cv.cls` and a small Makefile into `applications/acme/`. Edit the `.tex` files there for that company, then run `make` inside the folder to get `cv.pdf` and `coverletter.pdf`. Exports never overwrite an existing folder, and `applications/` is git-ignored so letters stay private. The letter template itself lives in `cv_builder/templates/coverletter.tex.j2`.
