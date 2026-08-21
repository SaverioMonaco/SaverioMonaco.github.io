import base64
import csv
import mimetypes
import re
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
    (year, title, venue) — used for the Presentation/Talks section so it
    reads as compactly as the Publications bibliography."""
    entries = []
    for item in (data or []):
        dates = item.get("dates", "")
        years = re.findall(r"\d{4}", dates)
        venue = ", ".join(p for p in (item.get("organization", ""), item.get("location", "")) if p)
        entries.append({
            "year": years[-1] if years else dates,
            "title": item.get("title", ""),
            "venue": venue,
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

        self._render("entries.tex.j2", o / "extracurricular.tex",
                     section_title="Extracurricular Activity", section_top_skip="3.5mm",
                     entries=_normalize_entries(self._load("cv", "extracurricular.yaml")))

        self._render("compactentries.tex.j2", o / "presentation.tex",
                     section_title="Presentations", section_top_skip="3.5mm",
                     entries=_normalize_compact_entries(self._load("cv", "presentation.yaml")))

        self._render("entries.tex.j2", o / "writing.tex",
                     section_title="Writing",
                     entries=_normalize_entries(self._load("cv", "writing.yaml")))

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
                "kind": "publications", "title": "Publications",
                "publications": _normalize_publications(
                    self._load("cv", "publications.yaml"), personal["name"]["last"]),
            },
            "presentation": lambda: {
                "kind": "entries", "title": "Presentations",
                "entries": _normalize_entries(self._load("cv", "presentation.yaml")),
            },
            "extracurricular": lambda: {
                "kind": "entries", "title": "Extracurricular Activity",
                "entries": _normalize_entries(self._load("cv", "extracurricular.yaml")),
            },
            "writing": lambda: {
                "kind": "entries", "title": "Writing",
                "entries": _normalize_entries(self._load("cv", "writing.yaml")),
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

        self._render("cv.tex.j2", self.output_dir / "cv.tex",
                     personal=personal, config=config, highlight_color_hex=highlight_color_hex)

        self._render("resume.tex.j2", self.output_dir / "resume.tex",
                     personal=personal, config=config, highlight_color_hex=highlight_color_hex)

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
        print("Done!")
