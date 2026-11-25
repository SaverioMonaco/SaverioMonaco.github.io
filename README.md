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

Under the hood, `make` calls the builder directly (`python3 -m cv_builder`, so it works without `make install` too):

```
python3 -m cv_builder build --data-dir data --output-dir build
```

which regenerates everything under `build/`, then the Makefile copies the relevant files to the repo root.

## Tailoring a CV and motivation letter for an application

Each application lives in its own folder, `applications/<name>/`, and only stores what differs from the main CV:

```
make new NAME=lanl     # creates applications/lanl/application.yaml and letter.tex
make app NAME=lanl     # builds applications/lanl/cv.pdf and letter.pdf
```

* `application.yaml`, `cv:` block: tweaks to the PDF CV for this application only (the website is never affected):
  * `hide_sections`: e.g. `[writing, extracurricular]`; or `sections` for a full custom order.
  * `bold`: phrases bolded wherever they appear in skills and entry bullets (case-insensitive, whole words).
  * `hide_skills`: single skills or whole skill categories.
  * `hide_entries`: per section, a substring of an entry's title/organization (publications: bib key or title).
  * `position`: a different headline under your name.

  Any rule that matches nothing prints a warning, so typos don't go unnoticed.
* `application.yaml`, `letter:` block: title, opening, closing, logo (an image in the folder), optional recipient and date.
* `letter.tex`: the body of the letter, in LaTeX. Use `\begin{point}{Lead-in} ... \end{point}` for paragraphs with the accent side bar. `\cite{key}` works for your own papers (keys from `data/cv/publications.yaml`) and for anything in an optional `references.bib` in the folder; a References list is added only when the letter cites something.

The CV data stays in `data/`, so updating the main CV updates every application the next time you run `make app`. `applications/` is git-ignored so letters stay private. Generated LaTeX goes to `applications/<name>/build/`.
