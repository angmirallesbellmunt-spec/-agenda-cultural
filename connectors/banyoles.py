from __future__ import annotations

import re
import requests
from datetime import date

from .common import HEADERS, soup, clean, abs_url, best_image, normalize_event, dedupe_sessions

SOURCE = "Cultura Banyoles"
BASE = "https://www.cultura.banyoles.cat"
AGENDA = BASE + "/ca/programacio.html"
MUNICIPALITY = "Banyoles"


def _year_from_page(doc):
    text = clean(doc.get_text(" ", strip=True))
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
    future = [y for y in years if y >= date.today().year]
    return min(future) if future else date.today().year


def _parse_detail_date(text, default_year):
    """Llegeix dates tipus 'dissabte 10 d’octubre | 20:00 h'."""
    months = {
        "gener": 1, "febrer": 2, "març": 3, "abril": 4, "maig": 5, "juny": 6,
        "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
    }
    low = text.lower().replace("’", "'")
    m = re.search(r"\b(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)", low)
    if not m:
        m = re.search(r"\b(\d{1,2})\s+de\s+([a-zà-ü]+)", low)
    if not m:
        return None
    month = months.get(m.group(2).strip(". '"))
    if not month:
        return None
    tm = re.search(r"\b(\d{1,2}:\d{2})\s*h?\b", text)
    return {"date": f"{default_year:04d}-{month:02d}-{int(m.group(1)):02d}", "time": tm.group(1) if tm else None}


def _parse_short_dates(text):
    """Llegeix 10.10.26 i intervals 22.10.26 ... 01.11.26 del web."""
    found = []
    for d, m, y, tm in re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s*\|\s*(\d{1,2}:\d{2}))?", text):
        yy = int(y)
        if yy < 100:
            yy += 2000
        found.append({"date": f"{yy:04d}-{int(m):02d}-{int(d):02d}", "time": tm or None})
    return dedupe_sessions(found)


def _main_content(doc):
    for selector in ("main", "#main", ".main", ".content", ".contingut"):
        node = doc.select_one(selector)
        if node:
            return node
    return doc


def _description(doc):
    root = _main_content(doc)
    heading = None
    for h in root.find_all(["h2", "h3", "h4"]):
        if "descrip" in clean(h.get_text(" ", strip=True)).lower():
            heading = h
            break
    if not heading:
        return None
    parts = []
    for node in heading.find_all_next():
        if node.name in ("h2", "h3", "h4") and node is not heading:
            break
        if node.name == "p":
            txt = clean(node.get_text(" ", strip=True))
            if txt:
                parts.append(txt)
    return clean(" ".join(parts)) or None


def _venue_and_category(doc):
    root = _main_content(doc)
    text = clean(root.get_text(" ", strip=True))

    # Els equipaments del web apareixen com a enllaços a /equipaments/.
    venue = None
    for a in root.find_all("a", href=True):
        href = a.get("href", "")
        label = clean(a.get_text(" ", strip=True))
        if label and "/equipaments/" in href:
            venue = label
            break

    category = None
    known = (
        "Música", "Teatre i dansa", "Biblioteca", "Exposicions", "Patrimoni",
        "Activitats infantils i/o familiars", "Festes i Cultura Popular",
        "Jornades de portes obertes", "Altres activitats"
    )
    for name in known:
        if name.lower() in text.lower():
            category = name
            break
    return venue, category


def _detail(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    doc = soup(r.text)
    root = _main_content(doc)

    h1 = root.find("h1") or doc.find("h1")
    title = clean(h1.get_text(" ", strip=True)) if h1 else None
    if not title:
        return None

    year = _year_from_page(doc)
    root_text = clean(root.get_text(" ", strip=True))

    # Prioritzem les sessions curtes estructurades si existeixen.
    sessions = _parse_short_dates(root_text)
    if not sessions:
        # La primera línia de la fitxa sol contenir la data principal.
        for node in root.find_all(["p", "div", "span", "time"]):
            txt = clean(node.get_text(" ", strip=True))
            if not txt or len(txt) > 140:
                continue
            parsed = _parse_detail_date(txt, year)
            if parsed:
                sessions = [parsed]
                break

    if not sessions:
        return None

    venue, category = _venue_and_category(doc)
    image = best_image(root, url)
    if not image:
        # Regla editorial del projecte: sense fotografia apta, no publiquem l'activitat.
        return None

    return normalize_event(
        source=SOURCE,
        title=title,
        url=url,
        municipality=MUNICIPALITY,
        venue=venue,
        category=category,
        description=_description(doc),
        image=image,
        sessions=dedupe_sessions(sessions),
        date_start=sessions[0]["date"] if sessions else None,
        date_end=sessions[-1]["date"] if sessions else None,
    )


def run():
    r = requests.get(AGENDA, headers=HEADERS, timeout=20)
    r.raise_for_status()
    doc = soup(r.text)

    urls = []
    seen = set()
    for a in doc.find_all("a", href=True):
        href = a.get("href", "")
        # Fitxes reals: /ca/programacio/c/34114-per-fi-men-vaig.html
        if "/ca/programacio/c/" not in href:
            continue
        url = abs_url(BASE, href)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    events = []
    for url in urls:
        try:
            event = _detail(url)
            if event:
                events.append(event)
        except Exception as exc:
            print(f"Banyoles: error a {url}: {exc!r}")

    return events
