from __future__ import annotations
import re
from datetime import datetime
import requests
from connectors.common import HEADERS, soup, clean, abs_url, _image_info, normalize_event, dedupe_sessions

BASE="https://www.olotcultura.cat"
AGENDA=BASE+"/agenda/"
SOURCE="Olot Cultura"
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
    m=re.search(r"(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)\s+de\s+(\d{4})",low)
    if not m:
        m=re.search(r"(\d{1,2})\s+de\s+([a-zà-ü]+)\s+de\s+(\d{4})",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    tm=re.search(r"(\d{1,2})(?:[.:](\d{2}))?\s*h\b",low)
    time=f"{int(tm.group(1)):02d}:{int(tm.group(2) or 0):02d}" if tm else None
    return {"date":f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}","time":time}

def _links(doc):
    out=[]; seen=set()
    for a in doc.select('a[href*="/agenda/acte/"]'):
        u=abs_url(BASE,a.get("href"))
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out

def _detail(url):
    r=requests.get(url,headers=HEADERS,timeout=20); r.raise_for_status()
    d=soup(r.text)
    h=d.find("h1") or d.find("h2")
    title=clean(h.get_text(" ",strip=True)) if h else ""
    if not title: return None

    # Només llegim la capçalera per a data/espai; evitem Activitats Relacionades.
    top=[]
    for node in h.find_all_next():
        if node.name in ("h2","h3") and "activitats relacionades" in clean(node.get_text(" ",strip=True)).lower():
            break
        top.append(clean(node.get_text(" ",strip=True)))
        if len(" ".join(top)) > 3500: break
    top_text=clean(" ".join(top))
    s=_session(top_text)
    if not s: return None

    category=None
    prev=h.find_all_previous(["span","div","p","a"],limit=25)
    for el in prev:
        t=clean(el.get_text(" ",strip=True))
        if t.upper() in {"TEATRE","MÚSICA","DANSA","CINEMA","LLETRES","XERRADES","EXPOSICIONS","TRADICIONS","ALTRES"}:
            category=t.title(); break

    venue=None
    # A Olot l'espai és a la mateixa línia de data.
    for tag in d.find_all(["h4","p","div"]):
        t=clean(tag.get_text(" ",strip=True))
        if str(s["date"][:4]) in t and len(t)<220:
            parts=[clean(x) for x in t.split(",")]
            if len(parts)>=2:
                cand=parts[-1]
                if cand and " h" not in cand.lower():
                    venue=cand
            if venue: break

    desc=None
    for p in h.find_all_next("p"):
        t=clean(p.get_text(" ",strip=True))
        if len(t)>=80:
            desc=t; break

    image=_main_image(d,url,title)
    if not image: return None

    return normalize_event(source=SOURCE,title=title,url=url,municipality="Olot",
                           venue=venue,category=category,description=desc,image=image,
                           sessions=dedupe_sessions([s]),
                           date_start=s["date"],date_end=s["date"])

def run():
    urls=[]; seen=set()
    for page in range(1,9):
        u=AGENDA if page==1 else f"{AGENDA}page/{page}/"
        r=requests.get(u,headers=HEADERS,timeout=20)
        if r.status_code==404: break
        r.raise_for_status()
        links=_links(soup(r.text))
        if not links and page>1: break
        new=0
        for x in links:
            if x not in seen:
                seen.add(x); urls.append(x); new+=1
        if page>1 and new==0: break

    out=[]; today=datetime.now().date().isoformat()
    for u in urls:
        try:
            e=_detail(u)
            if e and e["sessions"] and e["sessions"][0]["date"]>=today:
                out.append(e)
        except Exception as ex:
            print("Olot:",u,repr(ex))
    return out
