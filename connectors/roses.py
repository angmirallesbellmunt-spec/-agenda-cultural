import re, requests
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit
from .common import *

BASE = 'https://www.rosescultura.cat'
LIST = BASE + '/ca/programacio.html'
SOURCE = 'Roses Cultura'


def canonical(u):
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def _year(text):
    m = re.search(r'\b(20\d{2})\b', text or '')
    return int(m.group(1)) if m else date.today().year


def _dmy(day, month, year):
    return iso_date(int(day), int(month), int(year))


def parse_dates(text):
    """Returns (sessions, date_start, date_end)."""
    t = clean(text).replace('’', "'")
    year = _year(t)

    # 04.10.26 | 12:00 h
    m = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*\|\s*(\d{1,2}:\d{2})', t)
    if m:
        y = int(m.group(3)); y = 2000 + y if y < 100 else y
        d = _dmy(m.group(1), m.group(2), y)
        return ([{'date': d, 'time': m.group(4)}], None, None)

    # Del dg. 05.07.26 al dg. 09.08.26 | 20:30 h
    m = re.search(
        r'Del\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s+'
        r'al\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})'
        r'(?:\s*\|\s*(\d{1,2}:\d{2}))?', t, re.I)
    if m:
        y1 = int(m.group(3)); y1 = 2000 + y1 if y1 < 100 else y1
        y2 = int(m.group(6)); y2 = 2000 + y2 if y2 < 100 else y2
        return ([], _dmy(m.group(1), m.group(2), y1), _dmy(m.group(4), m.group(5), y2))

    # Long Catalan date as fallback.
    one = parse_long_date(t, year=year)
    return ([one] if one else [], None, None)


def detail_links(doc):
    links = []
    for a in doc.select('a[href]'):
        href = a.get('href') or ''
        # Roses detail URLs normally live below /ca/programacio/c/ or /ca/programacio/<slug>.
        if '/ca/programacio/' not in href:
            continue
        u = canonical(urljoin(BASE, href))
        if u.rstrip('/') in (LIST.rstrip('/'),):
            continue
        if re.search(r'/programacio/\d{4}-\d{1,2}-\d{1,2}\.html$', u):
            continue
        if u not in links:
            links.append(u)
    return links


def text_before_related(doc):
    lines = []
    for x in doc.stripped_strings:
        z = clean(x)
        if not z:
            continue
        if z.lower() == 'activitats relacionades':
            break
        lines.append(z)
    return lines


def venue_and_category(doc, lines):
    text = '\n'.join(lines)
    venue = None
    category = None

    # Prefer linked venue/category values when the site exposes them.
    for a in doc.select('a[href]'):
        z = clean(a.get_text(' ', strip=True))
        href = (a.get('href') or '').lower()
        if not z or z not in text:
            continue
        if not venue and any(k in href for k in ('/espais/', '/espai/')):
            venue = z
        if not category and any(k in href for k in ('categoria', 'categories', 'programacio')):
            if z.lower() not in ('programació', 'avui', 'demà', 'agenda mensual'):
                category = z
    return venue, category


def run():
    s = requests.Session(); s.headers.update(HEADERS)
    r = s.get(LIST, timeout=30); r.raise_for_status()
    listing = soup(r.text)
    links = detail_links(listing)

    out = []
    today = date.today().isoformat()
    for u in links:
        r = s.get(u, timeout=30); r.raise_for_status()
        p = soup(r.text)
        h1 = p.select_one('h1')
        if not h1:
            continue
        title = clean(h1.get_text(' ', strip=True))
        lines = text_before_related(p)
        all_text = ' '.join(lines)
        sessions, date_start, date_end = parse_dates(all_text)

        # Skip clearly historical entries, but keep ongoing periods.
        last_date = date_end or (max((x['date'] for x in sessions), default=None))
        if last_date and last_date < today:
            continue

        subtitle = p.select_one('h1 + h2, h1 + .subtitle, .subtitol, .subtitle')
        desc = clean(subtitle.get_text(' ', strip=True)) if subtitle else None
        venue, category = venue_and_category(p, lines)

        out.append(normalize_event(
            source=SOURCE, title=title, url=u, municipality='Roses',
            venue=venue, category=category, description=desc,
            image=best_image(p, u), sessions=dedupe_sessions(sessions),
            date_start=date_start, date_end=date_end
        ))
    return out
