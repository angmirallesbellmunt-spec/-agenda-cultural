import re, requests
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
from .common import *

BASE = 'https://web2.girona.cat'
LIST = BASE + '/cultura/cat/agenda.php'
SOURCE = 'Girona Cultura'

MUNICIPALITIES = (
    'Girona', 'Bescanó', 'Celrà', 'Fornells de la Selva', 'Quart', 'Salt',
    'Sant Gregori', 'Sant Julià de Ramis', 'Sarrià de Ter', 'Vilablareix'
)


def canonical(u):
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def detail_links(doc):
    links = []
    for a in doc.select('a[href]'):
        href = a.get('href') or ''
        if 'agenda_fitxa.php' not in href:
            continue
        u = canonical(urljoin(BASE, href))
        if u not in links:
            links.append(u)
    return links


def lines(doc):
    return [clean(x) for x in doc.stripped_strings if clean(x)]


def parse_sessions(text):
    t = text.replace('’', "'")
    out = []

    # dd.mm.yyyy / dd.mm.yy + optional time
    for m in re.finditer(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s*(?:\||-|a les|,)\s*(\d{1,2}:\d{2}))?', t, re.I):
        y = int(m.group(3)); y = 2000 + y if y < 100 else y
        out.append({'date': iso_date(int(m.group(1)), int(m.group(2)), y), 'time': m.group(4)})

    # Catalan long dates, e.g. 17 d'octubre de 2026, 20:30
    for m in re.finditer(r'\b(\d{1,2})\s+(?:de\s+|d[\'’])([a-zà-ÿ]+)(?:\s+de\s+(20\d{2}))?(?:[^\d]{0,20}(\d{1,2}:\d{2}))?', t, re.I):
        mon = MONTHS.get(m.group(2).lower().strip('.'))
        if not mon:
            continue
        y = int(m.group(3) or date.today().year)
        out.append({'date': iso_date(int(m.group(1)), mon, y), 'time': m.group(4)})
    return dedupe_sessions(out)


def period(text):
    t = text.replace('’', "'")
    m = re.search(
        r'(?:del|des del)\s+(\d{1,2})\s+(?:de\s+|d[\'’])([a-zà-ÿ]+)(?:\s+de\s+(20\d{2}))?'
        r'.{0,30}?(?:al|fins al)\s+(\d{1,2})\s+(?:de\s+|d[\'’])([a-zà-ÿ]+)(?:\s+de\s+(20\d{2}))?',
        t, re.I)
    if not m:
        return None, None
    mo1 = MONTHS.get(m.group(2).lower().strip('.')); mo2 = MONTHS.get(m.group(5).lower().strip('.'))
    if not mo1 or not mo2:
        return None, None
    y1 = int(m.group(3) or date.today().year)
    y2 = int(m.group(6) or y1)
    return iso_date(int(m.group(1)), mo1, y1), iso_date(int(m.group(4)), mo2, y2)


def labeled_value(doc, labels):
    labels = tuple(x.lower() for x in labels)
    for node in doc.find_all(['dt', 'th', 'strong', 'b', 'span', 'div', 'p']):
        z = clean(node.get_text(' ', strip=True)).lower().rstrip(':')
        if z not in labels:
            continue
        # Definition-list/table/common sibling patterns.
        nxt = node.find_next_sibling()
        if nxt:
            val = clean(nxt.get_text(' ', strip=True))
            if val and val.lower().rstrip(':') not in labels:
                return val
    return None


def municipality_from(doc, text):
    val = labeled_value(doc, ('municipi', 'població', 'localitat'))
    if val:
        for m in MUNICIPALITIES:
            if m.lower() in val.lower():
                return m
    low = text.lower()
    for m in sorted(MUNICIPALITIES, key=len, reverse=True):
        if m.lower() in low:
            return m
    return 'Girona'


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
        ls = lines(p); text = ' '.join(ls)
        sessions = parse_sessions(text)
        date_start, date_end = period(text)

        last_date = date_end or max((x['date'] for x in sessions), default=None)
        if last_date and last_date < today:
            continue

        venue = labeled_value(p, ('lloc', 'espai', 'equipament'))
        category = labeled_value(p, ('tipologia', 'àmbit', 'categoria'))
        municipality = municipality_from(p, text)

        desc_node = p.select_one('.descripcio, .descripció, .description, .text, article')
        desc = clean(desc_node.get_text(' ', strip=True)) if desc_node else None
        if desc and title and desc.startswith(title):
            desc = clean(desc[len(title):]) or None

        out.append(normalize_event(
            source=SOURCE, title=title, url=u, municipality=municipality,
            venue=venue, category=category, description=desc,
            image=best_image(p, u), sessions=sessions,
            date_start=date_start, date_end=date_end
        ))
    return out
