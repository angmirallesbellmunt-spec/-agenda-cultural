from __future__ import annotations
import re
import requests
from datetime import date
from connectors.common import HEADERS, soup, clean, abs_url, _image_info, normalize_event, dedupe_sessions

SOURCE="Cultura Banyoles"
BASE="https://cultura.banyoles.cat"
AGENDA=BASE+"/ca/programacio.html"
MUNICIPALITY="Banyoles"
MONTHS={"gener":1,"febrer":2,"març":3,"abril":4,"maig":5,"juny":6,"juliol":7,"agost":8,"setembre":9,"octubre":10,"novembre":11,"desembre":12}

def _main_image(doc, page_url, title):
    """Només accepta la imatge pròpia de la fitxa. Mai busca imatges relacionades."""
    candidates = []

    # 1. Imatge social declarada per la mateixa fitxa (normalment és la principal).
    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:secure_url"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
    ):
        meta = doc.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            candidates.append(abs_url(page_url, meta.get("content")))

    # 2. Alternativa: una imatge el text alternatiu de la qual coincideix amb el títol.
    wanted = clean(title).lower()
    for img in doc.find_all("img"):
        alt = clean(img.get("alt")).lower()
        if alt and (alt == wanted or wanted in alt or alt in wanted):
            u = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
            if u:
                candidates.append(abs_url(page_url, u))

    seen = set()
    for u in candidates:
        if not u or u in seen:
            continue
        seen.add(u)
        info = _image_info(u)
        if not info:
            continue
        w, h, nbytes = info
        ratio = w / h
        # Comprovació de qualitat, però sense substituir mai la foto per una altra.
        if w >= 900 and h >= 500 and 0.90 <= ratio <= 2.10 and nbytes >= 60000:
            return u
    return None

def _session(text, year):
    low=clean(text).lower().replace("’","'")
    m=re.search(r"(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)",low)
    if not m: m=re.search(r"(\d{1,2})\s+de\s+([a-zà-ü]+)",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    tm=re.search(r"(\d{1,2}:\d{2})\s*h",low)
    return {"date":f"{year:04d}-{mon:02d}-{int(m.group(1)):02d}","time":tm.group(1) if tm else None}

def _links(doc):
    out=[]; seen=set()
    for a in doc.select('a[href*="/ca/programacio/c/"]'):
        u=abs_url(BASE,a.get("href"))
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out

def _detail(url):
    r=requests.get(url,headers=HEADERS,timeout=20); r.raise_for_status()
    d=soup(r.text)
    h=d.find("h1")
    title=clean(h.get_text(" ",strip=True)) if h else ""
    if not title: return None

    chunks=[]
    for node in h.find_all_next():
        txt=clean(node.get_text(" ",strip=True))
        if "activitats relacionades" in txt.lower() and len(txt)<80:
            break
        chunks.append(txt)
        if len(" ".join(chunks))>4500: break
    top_text=clean(" ".join(chunks))
    years=[int(x) for x in re.findall(r"\b20\d{2}\b",top_text)]
    year=years[0] if years else date.today().year
    s=_session(top_text,year)
    if not s: return None

    venue=None
    for a in h.find_all_next("a"):
        href=a.get("href","")
        t=clean(a.get_text(" ",strip=True))
        if t and "/equipaments/" in href:
            venue=t; break

    category=None
    for a in h.find_all_next("a"):
        href=a.get("href","")
        t=clean(a.get_text(" ",strip=True))
        if t and ("/categories/" in href or "/categoria/" in href):
            category=t; break
    if not category:
        known=("Música","Teatre i dansa","Biblioteca","Exposicions","Patrimoni",
               "Activitats infantils i/o familiars","Festes i Cultura Popular",
               "Jornades de portes obertes","Altres activitats")
        for c in known:
            if c.lower() in top_text.lower():
                category=c; break

    desc=None
    marker=None
    for hd in h.find_all_next(["h2","h3","h4"]):
        if "descrip" in clean(hd.get_text(" ",strip=True)).lower():
            marker=hd; break
    if marker:
        parts=[]
        for node in marker.find_all_next():
            if node.name in ("h2","h3","h4") and node is not marker: break
            if node.name=="p":
                t=clean(node.get_text(" ",strip=True))
                if t: parts.append(t)
        desc=clean(" ".join(parts)) or None

    image=_main_image(d,url,title)
    if not image: return None

    return normalize_event(source=SOURCE,title=title,url=url,municipality=MUNICIPALITY,
                           venue=venue,category=category,description=desc,image=image,
                           sessions=dedupe_sessions([s]),
                           date_start=s["date"],date_end=s["date"])

def run():
    r=requests.get(AGENDA,headers=HEADERS,timeout=20); r.raise_for_status()
    urls=_links(soup(r.text))
    out=[]; today=date.today().isoformat()
    for u in urls:
        try:
            e=_detail(u)
            if e and e["sessions"] and e["sessions"][0]["date"]>=today:
                out.append(e)
        except Exception as ex:
            print("Banyoles:",u,repr(ex))
    return out
