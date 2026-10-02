import re, requests
from urllib.parse import urljoin, urlsplit, urlunsplit
from .common import *

BASE="https://agenda.labisbal.cat"
LIST=BASE+"/ca/agenda.html"
SOURCE="Agenda de la Bisbal"

def canonical(u):
    p=urlsplit(u)
    return urlunsplit((p.scheme,p.netloc,p.path,"",""))

def primary_text(p):
    root=p.select_one('main') or p.select_one('article') or p.body or p
    text=root.get_text('\n',strip=True)
    # Related activities are the source of the false extra sessions.
    m=re.search(r"\nActivitats relacionades\n",text,re.I)
    if m: text=text[:m.start()]
    return text

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    d=soup(s.get(LIST,timeout=30).text)
    links=[]
    for a in d.select('a[href*="/ca/agenda/c/"]'):
        u=canonical(urljoin(BASE,a.get("href")))
        if u not in links: links.append(u)
    out=[]
    for u in links:
        p=soup(s.get(u,timeout=30).text)
        h1=p.select_one("h1")
        if not h1: continue
        title=clean(h1.get_text(" ",strip=True))
        h2=p.select_one("h1 + h2")
        subtitle=clean(h2.get_text(" ",strip=True)) if h2 else None
        text=primary_text(p)
        sess=[]
        # Main header, e.g. divendres 2 d’octubre | 21:00 h
        for m in re.finditer(r"(\d{1,2})\s+d[’']?\s*([a-zà-ü]+)\s*\|\s*(\d{1,2}:\d{2})\s*h",text,re.I):
            mon=MONTHS.get(m.group(2).lower().strip("."))
            if mon: sess.append({"date":iso_date(int(m.group(1)),mon,2026),"time":m.group(3)})
        # Short format if present in the event's own block.
        for m in re.finditer(r"(?:dl|dt|dc|dj|dv|ds|dg)\.\s*(\d{1,2})\.(\d{1,2})\.(\d{2})\s*\|\s*(\d{1,2}:\d{2})",text,re.I):
            sess.append({"date":f"20{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}","time":m.group(4)})
        sess=dedupe_sessions(sess)
        venue=None
        # The actual venue appears immediately after the header date; never accept nav label 'Espais'.
        lines=[clean(x) for x in text.split('\n') if clean(x)]
        for i,line in enumerate(lines):
            if re.search(r"\d{1,2}\s+d[’']?[a-zà-ü]+\s*\|\s*\d{1,2}:\d{2}",line,re.I):
                for cand in lines[i+1:i+5]:
                    if cand.lower() not in ('espais','agenda','comprar','afegir al calendari') and not re.search(r'^\d',cand):
                        venue=cand; break
                if venue: break
        if not venue:
            for candidate in ("Teatre Mundial","Terracotta Museu","Biblioteca Lluïsa Duran","Castell Palau","Ermita del Remei"):
                if candidate.lower() in text.lower(): venue=candidate; break
        cats=[]
        for a in p.select('a[href]'):
            z=clean(a.get_text(" ",strip=True))
            if z in ("Música","Teatre","Dansa","Circ","Familiar","Cinema","Exposicions","Xerrades i conferències","Tallers"):
                cats.append(z)
        desc=None
        for q in p.select("main p, article p, .content p"):
            z=clean(q.get_text(" ",strip=True))
            if len(z)>80: desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="La Bisbal d'Empordà",
            venue=venue,category=" · ".join(dict.fromkeys(cats)) or None,
            description=desc or subtitle,image=best_image(p,u),sessions=sess))
    return out
