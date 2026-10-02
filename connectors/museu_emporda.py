
import re, requests
from urllib.parse import urljoin, urlparse, parse_qs
from .common import *

BASE="https://www.museuemporda.org/"
PAGES=[BASE+"?page_id=693", BASE]
SOURCE="Museu de l'Empordà"

def _activity_links(doc):
    links=[]
    # El web ha usat tant URLs amb ?activitat= com targetes/enllaços interns.
    for a in doc.select("a[href]"):
        href=a.get("href","")
        txt=clean(a.get_text(" ",strip=True))
        if "activitat=" in href or "activitats=" in href or ("museuemporda.org" in href and txt and len(txt)>8):
            u=urljoin(BASE,href)
            if u not in links: links.append(u)
    return links

def _sessions_from_text(text):
    out=[]
    # 7, 14, 21 i 28 d'octubre [de 2026] + hora comuna si n'hi ha.
    tm=re.search(r"(?:a les|,)\s*(\d{1,2})(?::(\d{2}))?\s*h",text,re.I)
    time=(f"{int(tm.group(1)):02d}:{tm.group(2) or '00'}") if tm else None
    low=text.lower().replace("’","'")
    for mon_name,mon in MONTHS.items():
        if len(mon_name)<4: continue
        m=re.search(r"((?:\d{1,2}\s*(?:,|i|y)?\s*)+)\s+d['e]?\s*"+re.escape(mon_name),low)
        if m:
            for day in re.findall(r"\d{1,2}",m.group(1)):
                out.append({"date":iso_date(int(day),mon,2026),"time":time})
            break
    # Dates simples.
    if not out:
        x=parse_long_date(text)
        if x: out=[x]
    return out

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    docs=[soup(s.get(u,timeout=30).text) for u in PAGES]
    links=[]
    for d in docs:
        for u in _activity_links(d):
            if u not in links: links.append(u)

    out=[]
    for u in links:
        try: p=soup(s.get(u,timeout=30).text)
        except Exception: continue
        h1=p.select_one("h1")
        if not h1: continue
        title=clean(h1.get_text(" ",strip=True))
        text=p.get_text("\n",strip=True)
        # Evita pàgines corporatives capturades per l'heurística.
        if not re.search(r"\b(2026|octubre|novembre|desembre|setembre)\b",text,re.I): continue
        venue=None
        for candidate in ("Museu de l'Empordà","Sala l’Escorxador","Sala L’Escorxador","L’Escorxador"):
            if candidate.lower() in text.lower(): venue=candidate; break
        if not venue: venue="Museu de l'Empordà"
        desc=None
        for q in p.select("main p, article p, .et_pb_text p, p"):
            z=clean(q.get_text(" ",strip=True))
            if len(z)>100 and "cookie" not in z.lower(): desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="Figueres",
            venue=venue,category="Museus · Art",description=desc,image=best_image(p,u),
            sessions=_sessions_from_text(text)))
    # Si el tema WordPress no exposa els href de les targetes, fem fallback amb la portada:
    # això conserva les activitats visibles i evita que el connector quedi buit.
    if not out:
        d=docs[-1]
        for h in d.select("h3"):
            title=clean(h.get_text(" ",strip=True))
            if not title: continue
            block=clean(h.parent.get_text(" ",strip=True))
            sessions=_sessions_from_text(block)
            out.append(normalize_event(source=SOURCE,title=title,url=BASE,municipality="Figueres",
                venue="Museu de l'Empordà",category="Museus · Art",description=None,
                image=best_image(h.parent,BASE),sessions=sessions))
    return out
