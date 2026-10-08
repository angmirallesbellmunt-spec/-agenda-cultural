from __future__ import annotations
import re
from datetime import datetime
import requests
from connectors.common import HEADERS, soup, clean, abs_url, _image_info, normalize_event, dedupe_sessions

BASE="https://www.celracultura.cat"
AGENDA=BASE+"/ca/agenda-entrades.html"
SOURCE="Celrà Cultura"
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

def _session(text):
    low=clean(text).lower().replace("’","'")
    m=re.search(r"(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)",low)
    if not m: m=re.search(r"(\d{1,2})\s+de\s+([a-zà-ü]+)",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    ym=re.search(r"\b(20\d{2})\b",low)
    year=int(ym.group(1)) if ym else datetime.now().year
    tm=re.search(r"\|\s*(\d{1,2}:\d{2})\s*h|\b(\d{1,2}:\d{2})\s*h",low)
    time=(tm.group(1) or tm.group(2)) if tm else None
    return {"date":f"{year:04d}-{mon:02d}-{int(m.group(1)):02d}","time":time}

def _links(doc):
    out=[]; seen=set()
    for a in doc.select('a[href*="/ca/agenda-entrades/c/"]'):
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

    # Només la zona de la fitxa anterior a "Activitats relacionades".
    chunks=[]
    for node in h.find_all_next():
        txt=clean(node.get_text(" ",strip=True))
        if "activitats relacionades" in txt.lower() and len(txt)<80:
            break
        chunks.append(txt)
        if len(" ".join(chunks))>3500: break
    top_text=clean(" ".join(chunks))
    s=_session(top_text)
    if not s: return None

    venue=None
    for a in h.find_all_next("a"):
        t=clean(a.get_text(" ",strip=True))
        href=a.get("href","")
        if t and len(t)<80 and ("/equipaments/" in href or any(k in t.lower() for k in ("teatre l'ateneu","plaça","parc ","sala ","torre ","església","local jove","centre cultural"))):
            venue=t; break

    category=None
    cats=("Teatre","Música","Dansa","Cinema","Circ","Familiars","Fires","Festes","Exposicions","Tallers")
    for c in cats:
        if re.search(r"\b"+re.escape(c)+r"\b",top_text,re.I):
            category=c; break

    desc=None
    for p in h.find_all_next("p"):
        t=clean(p.get_text(" ",strip=True))
        if len(t)>=80 and "Ctra. de Juià" not in t:
            desc=t; break

    image=_main_image(d,url,title)
    if not image: return None

    return normalize_event(source=SOURCE,title=title,url=url,municipality="Celrà",
                           venue=venue,category=category,description=desc,image=image,
                           sessions=dedupe_sessions([s]),
                           date_start=s["date"],date_end=s["date"])

def run():
    r=requests.get(AGENDA,headers=HEADERS,timeout=20); r.raise_for_status()
    urls=_links(soup(r.text))
    out=[]; today=datetime.now().date().isoformat()
    for u in urls:
        try:
            e=_detail(u)
            if e and e["sessions"] and e["sessions"][0]["date"]>=today:
                out.append(e)
        except Exception as ex:
            print("Celrà:",u,repr(ex))
    return out
