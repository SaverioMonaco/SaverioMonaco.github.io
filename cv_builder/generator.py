import base64
import csv
import mimetypes
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def latex_escape(text: str) -> str:
    """Escape special LaTeX characters so plain text is safe to use."""
    if text is None:
        return ""
    text = str(text)
    # Backslash must be first to avoid double-escaping
    replacements = [
        ("\\", "\\textbackslash{}"),
        ("&",  "\\&"),
        ("%",  "\\%"),
        ("$",  "\\$"),
        ("#",  "\\#"),
        ("_",  "\\_"),
        ("{",  "\\{"),
        ("}",  "\\}"),
        ("~",  "\\textasciitilde{}"),
        ("^",  "\\textasciicircum{}"),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text


def latex_escape_bold(text: str) -> str:
    """Like latex_escape, but turns **word** into a bolded \\textbf{word}."""
    if text is None:
        return ""
    text = str(text)
    parts = []
    last = 0
    for m in _BOLD_RE.finditer(text):
        parts.append(latex_escape(text[last:m.start()]))
        parts.append("\\textbf{" + latex_escape(m.group(1)) + "}")
        last = m.end()
    parts.append(latex_escape(text[last:]))
    return "".join(parts)


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["le"] = latex_escape
    env.filters["leb"] = latex_escape_bold
    return env


def _load(path: Path):
    with open(path) as f:
        return yaml.safe_load(f)


def _normalize_entries(data: list) -> list:
    """Normalize any entries-type YAML list to the generic template format."""
    return [
        {
            "title": item.get("title", ""),
            "organization": item.get("organization", ""),
            "location": item.get("location", ""),
            "dates": item.get("dates", ""),
            "bullets": item.get("highlights", item.get("items", [])) or [],
            "pdf": item.get("pdf", ""),
            "tbd": bool(item.get("tbd", False)),
        }
        for item in (data or [])
    ]


def _section_is_empty(section: dict) -> bool:
    """True if a built HTML section has no content to show."""
    kind = section["kind"]
    if kind == "entries":
        return not section["entries"]
    if kind == "skills":
        return not section["skills"]
    if kind == "publications":
        return not section["publications"]
    if kind == "honors":
        return not any(g["awards"] for g in section["groups"])
    return False


def _normalize_compact_entries(data: list) -> list:
    """Normalize entries-type YAML into bibliography-style compact entries
    (year, title, venue) — used for the Talks/Posters sections so they
    read as compactly as the Publications bibliography."""
    entries = []
    for item in (data or []):
        dates = item.get("dates", "")
        years = re.findall(r"\d{4}", dates)
        venue = ", ".join(p for p in (item.get("organization", ""), item.get("location", "")) if p)
        entries.append({
            "year": years[-1] if years else dates,
            "title": item.get("title", ""),
            "venue": venue,
            "pdf": item.get("pdf", ""),
        })
    return entries


def _normalize_grouped_honors(data: list) -> list:
    """Normalize honors YAML (with subsection groups) to template format."""
    groups = []
    for group in (data or []):
        awards = [
            {
                "col1": a.get("award", a.get("title", "")),
                "col2": a.get("event", a.get("organization", "")),
                "col3": a.get("location", ""),
                "col4": str(a.get("year", a.get("date", ""))),
            }
            for a in group.get("awards", [])
        ]
        groups.append({"subsection": group.get("group"), "awards": awards})
    return groups


def _normalize_certificates(data: list) -> list:
    """Normalize flat certificates list to template format."""
    return [{"subsection": None, "awards": [
        {
            "col1": c["name"],
            "col2": c["issuer"],
            "col3": "",
            "col4": str(c["year"]),
        }
        for c in (data or [])
    ]}]


_HIGHLIGHT_COLORS = {
    "awesome-emerald": "00A388",
    "awesome-skyblue": "0395DE",
    "awesome-red": "DC3522",
    "awesome-pink": "EF4089",
    "awesome-orange": "FF6138",
    "awesome-nephritis": "27AE60",
    "awesome-concrete": "95A5A6",
    "awesome-darknight": "131A28",
}

_DEFAULT_TEXT_COLOR = "333333"
_DEFAULT_SECONDARY_TEXT_COLOR = "5D5D5D"


def _resolve_color(name_or_hex: str) -> str:
    """Resolve a config color (awesome-cv color name or bare hex) to a CSS hex color."""
    return "#" + _HIGHLIGHT_COLORS.get(name_or_hex, name_or_hex)


def _normalize_publications(data: list, last_name: str) -> list:
    """Normalize publications YAML into display-ready fields for the HTML CV."""
    pubs = []
    for p in (data or []):
        authors = []
        for author in (p.get("author") or "").split(" and "):
            author = author.strip()
            if not author:
                continue
            family = author.split(",")[0].strip()
            authors.append({"text": author, "is_self": family == last_name})

        venue_parts = []
        if p.get("journal"):
            venue = p["journal"]
            if p.get("volume"):
                venue += f" {p['volume']}"
                if p.get("issue"):
                    venue += f"({p['issue']})"
            venue_parts.append(venue)
        if p.get("pages"):
            venue_parts.append(f"p. {p['pages']}")
        if p.get("publisher"):
            venue_parts.append(p["publisher"])

        pubs.append({
            "year": p.get("year", ""),
            "title": p.get("title", ""),
            "authors": authors,
            "venue": ", ".join(venue_parts),
            "doi": p.get("doi", ""),
            "url": p.get("url", ""),
        })
    pubs.sort(key=lambda x: x["year"], reverse=True)
    return pubs


def _normalize_upcoming(data: list) -> list:
    """Normalize upcoming-goals YAML (HTML-only) to template format."""
    return [
        {
            "title": item.get("title", ""),
            "note": item.get("note", ""),
            "target": str(item.get("target", "") or ""),
        }
        for item in (data or [])
    ]


def _normalize_figures(data: list) -> list:
    """Normalize a thesis-page figures list (top-level or per-chapter)."""
    return [
        {"path": f["path"], "caption": f.get("caption", "") or ""}
        for f in (data or [])
        if f.get("path")
    ]


def _embed_image(path: str):
    """Read an image file and return a data-URI dict for it, or None if missing."""
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    mime, _ = mimetypes.guess_type(file_path.name)
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return {"data_uri": f"data:{mime or 'application/octet-stream'};base64,{encoded}"}


# Workout-diary CSV export: (exercise name in the CSV, chart title to show)
_GYM_LIFTS = [
    ("Bench Press · Barbell", "Bench Press (Barbell)"),
    ("Squat · Barbell", "Squat"),
    ("Overhead Press · Barbell", "Overhead Press (Barbell)"),
    ("Deadlift · Barbell", "Deadlift"),
]


def _parse_gym_date(value: str):
    return datetime.strptime(value.strip(), "%d/%m/%Y").date()


def _load_gym_rows(gym_dir: Path) -> list:
    rows = []
    for csv_path in sorted(gym_dir.glob("*.csv")):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def _build_gym_charts(gym_dir: Path) -> list:
    """Parse workout-diary CSV export(s) into body-weight + per-lift max-weight series."""
    rows = _load_gym_rows(gym_dir)

    body_weight = {}
    lift_max = {name: {} for name, _ in _GYM_LIFTS}

    for r in rows:
        val1 = (r.get("Val_1") or "").strip()
        if not val1:
            continue
        try:
            day = _parse_gym_date(r.get("Date", ""))
            weight = float(val1)
        except ValueError:
            continue

        if r.get("Type") == "📏" and r.get("Name") == "Weight":
            body_weight[day] = weight
        elif r.get("Type") == "🔹" and r.get("Name") in lift_max:
            series = lift_max[r["Name"]]
            if day not in series or weight > series[day]:
                series[day] = weight

    def _series(points: dict) -> list:
        return [[day.isoformat(), val] for day, val in sorted(points.items())]

    charts = [{"title": "Body Weight", "data": _series(body_weight)}]
    for raw_name, label in _GYM_LIFTS:
        charts.append({"title": label, "data": _series(lift_max[raw_name])})
    return [c for c in charts if c["data"]]


def _format_display_date(iso: str) -> str:
    """Format an ISO date string ('2026-08-01') as 'Aug 1, 2026'."""
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _normalize_committees(data: list) -> list:
    """Normalize flat committees list to template format."""
    return [{"subsection": None, "awards": [
        {
            "col1": c["role"],
            "col2": c["committee"],
            "col3": c.get("location", ""),
            "col4": str(c["year"]),
        }
        for c in (data or [])
    ]}]


class Generator:
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.env = _make_env()

    def _load(self, *parts):
        return _load(self.data_dir.joinpath(*parts))

    def _render(self, template: str, out: Path, **ctx):
        out.parent.mkdir(parents=True, exist_ok=True)
        rendered = self.env.get_template(template).render(**ctx)
        out.write_text(rendered)
        print(f"  Generated {out}")

    def generate_cv(self):
        o = self.output_dir / "cv"

        self._render("entries.tex.j2", o / "experience.tex",
                     section_title="Experience", section_top_skip="0mm", swap_title_org=True,
                     entries=_normalize_entries(self._load("cv", "experience.yaml")))

        self._render("entries.tex.j2", o / "education.tex",
                     section_title="Education",
                     entries=_normalize_entries(self._load("cv", "education.yaml")))

        self._render("skills.tex.j2", o / "skills.tex",
                     skills=self._load("cv", "skills.yaml"))

        self._render("honors.tex.j2", o / "honors.tex",
                     section_title="Honors \\& Awards",
                     groups=_normalize_grouped_honors(self._load("cv", "honors.yaml")))

        self._render("honors.tex.j2", o / "certificates.tex",
                     section_title="Certificates",
                     groups=_normalize_certificates(self._load("cv", "certificates.yaml")))

        self._render("compactentries.tex.j2", o / "talks.tex",
                     section_title="Talks", section_top_skip="3.5mm",
                     entries=_normalize_compact_entries(self._load("cv", "talks.yaml")))

        self._render("compactentries.tex.j2", o / "posters.tex",
                     section_title="Posters", section_top_skip="3.5mm",
                     entries=_normalize_compact_entries(self._load("cv", "posters.yaml")))

        self._render("entries.tex.j2", o / "extracurricular.tex",
                     section_title="Extracurricular Activity", section_top_skip="3.5mm",
                     entries=_normalize_entries(self._load("cv", "extracurricular.yaml")))

        self._render("entries.tex.j2", o / "writing.tex",
                     section_title="Writing",
                     entries=_normalize_entries(self._load("cv", "writing.yaml")))

        self._render("entries.tex.j2", o / "schools.tex",
                     section_title="Schools", section_top_skip="3.5mm",
                     entries=_normalize_entries(self._load("cv", "schools.yaml")))

        self._render("honors.tex.j2", o / "committees.tex",
                     section_title="Program Committees",
                     groups=_normalize_committees(self._load("cv", "committees.yaml")))

        self._render("publications.tex.j2", o / "publications.tex")

        self._render("bib.bib.j2", o / "bib.bib",
                     publications=self._load("cv", "publications.yaml"))

    def generate_resume(self):
        o = self.output_dir / "resume"

        self._render("paragraph.tex.j2", o / "summary.tex",
                     section_title="Summary",
                     text=self._load("resume", "summary.yaml")["text"])

        self._render("entries.tex.j2", o / "experience.tex",
                     section_title="Work Experience", swap_title_org=True,
                     entries=_normalize_entries(self._load("resume", "experience.yaml")))

        self._render("honors.tex.j2", o / "honors.tex",
                     section_title="Honors \\& Awards",
                     groups=_normalize_grouped_honors(self._load("resume", "honors.yaml")))

        self._render("honors.tex.j2", o / "certificates.tex",
                     section_title="Certificates",
                     groups=_normalize_certificates(self._load("resume", "certificates.yaml")))

        self._render("entries.tex.j2", o / "education.tex",
                     section_title="Education",
                     entries=_normalize_entries(self._load("resume", "education.yaml")))

    def generate_cv_html(self):
        personal = self._load("personal.yaml")
        config = self._load("config.yaml")

        section_builders = {
            "education": lambda: {
                "kind": "entries", "title": "Education",
                "entries": _normalize_entries(self._load("cv", "education.yaml")),
            },
            "experience": lambda: {
                "kind": "entries", "title": "Experience",
                "entries": _normalize_entries(self._load("cv", "experience.yaml")),
            },
            "skills": lambda: {
                "kind": "skills", "title": "Skills",
                "skills": self._load("cv", "skills.yaml"),
            },
            "publications": lambda: {
                "kind": "publications", "title": "Publications", "collapsible": True,
                "publications": _normalize_publications(
                    self._load("cv", "publications.yaml"), personal["name"]["last"]),
            },
            "talks": lambda: {
                "kind": "entries", "title": "Talks", "collapsible": True,
                "entries": _normalize_entries(self._load("cv", "talks.yaml")),
            },
            "posters": lambda: {
                "kind": "entries", "title": "Posters", "collapsible": True,
                "entries": _normalize_entries(self._load("cv", "posters.yaml")),
            },
            "extracurricular": lambda: {
                "kind": "entries", "title": "Extracurricular Activity", "collapsible": True,
                "entries": _normalize_entries(self._load("cv", "extracurricular.yaml")),
            },
            "writing": lambda: {
                "kind": "entries", "title": "Writing", "collapsible": True,
                "entries": _normalize_entries(self._load("cv", "writing.yaml")),
            },
            "schools": lambda: {
                "kind": "entries", "title": "Schools",
                "entries": _normalize_entries(self._load("cv", "schools.yaml")),
            },
            "honors": lambda: {
                "kind": "honors", "title": "Honors & Awards",
                "groups": _normalize_grouped_honors(self._load("cv", "honors.yaml")),
            },
            "certificates": lambda: {
                "kind": "honors", "title": "Certificates",
                "groups": _normalize_certificates(self._load("cv", "certificates.yaml")),
            },
            "committees": lambda: {
                "kind": "honors", "title": "Program Committees",
                "groups": _normalize_committees(self._load("cv", "committees.yaml")),
            },
        }

        sections = []
        for path in config["cv"]["sections"]:
            builder = section_builders.get(Path(path).stem)
            if builder:
                section = builder()
                if not _section_is_empty(section):
                    sections.append(section)

        photo_cfg = personal.get("photo_web") or {}
        photo = _embed_image(photo_cfg.get("path", ""))
        if photo:
            photo["shape"] = photo_cfg.get("shape", "circle")

        upcoming_path = self.data_dir / "cv" / "upcoming.yaml"
        upcoming = _normalize_upcoming(_load(upcoming_path) if upcoming_path.exists() else [])

        self._render(
            "cv.html.j2", self.output_dir / "cv.html",
            personal=personal,
            photo=photo,
            sections=sections,
            upcoming=upcoming,
            section_color_highlight=config.get("section_color_highlight", True),
            highlight_color=_resolve_color(config["highlight_color"]),
            text_color=_resolve_color(config.get("text_color") or _DEFAULT_TEXT_COLOR),
            secondary_color=_resolve_color(config.get("secondary_text_color") or _DEFAULT_SECONDARY_TEXT_COLOR),
        )

    def generate_main_files(self):
        personal = self._load("personal.yaml")
        config = self._load("config.yaml")
        highlight_color_hex = _resolve_color(config["highlight_color"])[1:]

        hide_from_pdf = set(config["cv"].get("hide_from_pdf") or [])
        pdf_sections = [s for s in config["cv"]["sections"] if s not in hide_from_pdf]

        self._render("cv.tex.j2", self.output_dir / "cv.tex",
                     personal=personal, config=config, highlight_color_hex=highlight_color_hex,
                     pdf_sections=pdf_sections)

        self._render("resume.tex.j2", self.output_dir / "resume.tex",
                     personal=personal, config=config, highlight_color_hex=highlight_color_hex)

        self._render("coverletter.tex.j2", self.output_dir / "coverletter.tex",
                     personal=personal, config=config, highlight_color_hex=highlight_color_hex)

    def export(self, dest_dir: Path, cls_path: Path):
        """Copy the generated CV and motivational letter LaTeX sources into
        dest_dir as a standalone project to customize for one application."""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True)
        shutil.copy2(self.output_dir / "cv.tex", dest_dir / "cv.tex")
        shutil.copytree(self.output_dir / "cv", dest_dir / "cv")
        shutil.copy2(self.output_dir / "coverletter.tex", dest_dir / "coverletter.tex")
        shutil.copy2(cls_path, dest_dir / cls_path.name)
        self._render("export.Makefile.j2", dest_dir / "Makefile")

    def generate_gym_html(self):
        """Generate examples/gym.html — only if data/gym/*.csv exists."""
        gym_dir = self.data_dir / "gym"
        if not gym_dir.is_dir() or not any(gym_dir.glob("*.csv")):
            return

        personal = self._load("personal.yaml")
        config = self._load("config.yaml")
        charts = _build_gym_charts(gym_dir)
        if not charts:
            return

        all_dates = [day for chart in charts for day, _ in chart["data"]]

        self._render(
            "gym.html.j2", self.output_dir / "gym.html",
            personal=personal,
            charts=charts,
            x_min=min(all_dates),
            x_max=max(all_dates),
            last_updated=_format_display_date(max(all_dates)),
            highlight_color=_resolve_color(config["highlight_color"]),
            text_color=_resolve_color(config.get("text_color") or _DEFAULT_TEXT_COLOR),
            secondary_color=_resolve_color(config.get("secondary_text_color") or _DEFAULT_SECONDARY_TEXT_COLOR),
        )

    def generate_thesis_html(self):
        """Generate thesis.html — only if data/thesis.yaml exists."""
        thesis_path = self.data_dir / "thesis.yaml"
        if not thesis_path.is_file():
            return

        personal = self._load("personal.yaml")
        config = self._load("config.yaml")
        thesis = _load(thesis_path)

        if thesis.get("disputation_date"):
            thesis["disputation_date_display"] = _format_display_date(thesis["disputation_date"])

        thesis["figures"] = _normalize_figures(thesis.get("figures"))
        for chapter in thesis.get("chapters") or []:
            chapter["figures"] = _normalize_figures(chapter.get("figures"))

        self._render(
            "thesis.html.j2", self.output_dir / "thesis.html",
            personal=personal,
            thesis=thesis,
            section_color_highlight=config.get("section_color_highlight", True),
            highlight_color=_resolve_color(config["highlight_color"]),
            text_color=_resolve_color(config.get("text_color") or _DEFAULT_TEXT_COLOR),
            secondary_color=_resolve_color(config.get("secondary_text_color") or _DEFAULT_SECONDARY_TEXT_COLOR),
        )

    def generate(self):
        print("Generating CV sections...")
        self.generate_cv()
        print("Generating resume sections...")
        self.generate_resume()
        print("Generating main LaTeX files...")
        self.generate_main_files()
        print("Generating CV web version...")
        self.generate_cv_html()
        print("Generating gym progress page...")
        self.generate_gym_html()
        print("Generating thesis page...")
        self.generate_thesis_html()
        print("Done!")
