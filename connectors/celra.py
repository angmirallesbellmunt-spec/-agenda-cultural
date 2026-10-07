from __future__ import annotations
import re
from datetime import datetime
import requests
from connectors.common import HEADERS, soup, clean, abs_url, best_image, normalize_event, dedupe_sessions

BASE="https://www.celracultura.cat"
AGENDA=BASE+"/ca/agenda-entrades.html"
SOURCE="Celrà Cultura"
MONTHS={"gener":1,"febrer":2,"març":3,"abril":4,"maig":5,"juny":6,"juliol":7,"agost":8,"setembre":9,"octubre":10,"novembre":11,"desembre":12}

def _session(text):
    low=clean(text).lower().replace("’","'")
    m=re.search(r"(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)",low)
    if not m:
        m=re.search(r"(\d{1,2})\s+de\s+([a-zà-ü]+)",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    year=datetime.now().year
    ym=re.search(r"\b(20\d{2})\b",low)
    if ym: year=int(ym.group(1))
    else:
        # Les fitxes sovint ometen l'any; l'agenda activa és de l'any actual.
        year=datetime.now().year
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
    text=clean(d.get_text(" ",strip=True))
    s=_session(text)
    if not s: return None

    venue=None
    # Espais habituals de Celrà: busquem etiquetes curtes pròximes a la informació de data.
    for tag in d.find_all(["p","div","span","li"]):
        t=clean(tag.get_text(" ",strip=True))
        if 2 < len(t) < 90 and any(k in t.lower() for k in ("teatre l'ateneu","plaça","parc ","sala ","torre ","església","local jove","centre cultural")):
            venue=t; break

    category=None
    cats=("Teatre","Música","Dansa","Cinema","Circ","Familiars","Fires","Festes","Exposicions","Tallers")
    for c in cats:
        if re.search(r"\b"+re.escape(c)+r"\b",text,re.I):
            category=c; break

    desc=None
    for p in d.find_all("p"):
        t=clean(p.get_text(" ",strip=True))
        if len(t)>=80 and "Ctra. de Juià" not in t:
            desc=t; break

    image=best_image(d,url)
    if not image: return None

    return normalize_event(source=SOURCE,title=title,url=url,municipality="Celrà",
                           venue=venue,category=category,description=desc,image=image,
                           sessions=dedupe_sessions([s]))

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
