from __future__ import annotations
import re
from datetime import datetime
import requests
from connectors.common import HEADERS, soup, clean, abs_url, best_image, normalize_event, dedupe_sessions

BASE="https://www.olotcultura.cat"
AGENDA=BASE+"/agenda/"
SOURCE="Olot Cultura"

MONTHS={"gener":1,"febrer":2,"març":3,"abril":4,"maig":5,"juny":6,"juliol":7,"agost":8,"setembre":9,"octubre":10,"novembre":11,"desembre":12}

def _session(text):
    low=clean(text).lower().replace("’","'")
    m=re.search(r"(\d{1,2})\s+d['e]?\s*([a-zà-ü]+)\s+de\s+(\d{4})",low)
    if not m:
        m=re.search(r"(\d{1,2})\s+de\s+([a-zà-ü]+)\s+de\s+(\d{4})",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    tm=re.search(r"(\d{1,2})(?:[.:](\d{2}))?\s*h\b",low)
    time=None
    if tm:
        time=f"{int(tm.group(1)):02d}:{int(tm.group(2) or 0):02d}"
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
    text=clean(d.get_text(" ",strip=True))
    s=_session(text)
    if not s: return None

    category=None
    # Olot Cultura mostra la categoria prop de la capçalera; evitem menús genèrics.
    for el in d.find_all(["span","div","p","a"]):
        t=clean(el.get_text(" ",strip=True))
        if t.upper() in {"TEATRE","MÚSICA","DANSA","CINEMA","LLETRES","XERRADES","EXPOSICIONS","TRADICIONS","ALTRES"}:
            category=t.title(); break

    venue=None
    # La línia de data acostuma a acabar amb l'espai després de l'hora.
    for tag in d.find_all(["h3","h4","p","div"]):
        t=clean(tag.get_text(" ",strip=True))
        if str(s["date"][:4]) in t and (" h" in t or "horari" in t.lower()):
            parts=[clean(x) for x in t.split(",")]
            if len(parts)>=2:
                cand=parts[-1]
                if len(cand)<120 and not re.search(r"\b\d{1,2}(?:[.:]\d{2})?\s*h\b",cand.lower()):
                    venue=cand
            break

    desc=None
    # Primer paràgraf substancial posterior a la capçalera.
    for p in d.find_all("p"):
        t=clean(p.get_text(" ",strip=True))
        if len(t)>=80 and title.lower() not in t.lower():
            desc=t; break

    image=best_image(d,url)
    if not image: return None

    return normalize_event(source=SOURCE,title=title,url=url,municipality="Olot",
                           venue=venue,category=category,description=desc,image=image,
                           sessions=dedupe_sessions([s]))

def run():
    urls=[]; seen=set()
    # Paginació limitada però suficient per cobrir l'agenda futura visible.
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

    out=[]
    today=datetime.now().date().isoformat()
    for u in urls:
        try:
            e=_detail(u)
            if e and e["sessions"] and e["sessions"][0]["date"]>=today:
                out.append(e)
        except Exception as ex:
            print("Olot:",u,repr(ex))
    return out
