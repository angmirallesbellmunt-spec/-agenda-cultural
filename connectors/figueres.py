import re, requests
from urllib.parse import urljoin, urlsplit, urlunsplit
from .common import *

BASE="https://www.figueresaescena.cat"
LIST=BASE+"/ca/programacio.html"
SOURCE="Figueres a Escena"

def canonical(u):
    p=urlsplit(u)
    return urlunsplit((p.scheme,p.netloc,p.path,"",""))

def primary_text(p):
    # Only the event header/body before related activities.
    marker=p.find(lambda tag: getattr(tag,'name',None) in ('h2','h3') and 'activitats relacionades' in clean(tag.get_text(' ',strip=True)).lower())
    root=p.select_one('main') or p.select_one('article') or p.body or p
    text=root.get_text('\n',strip=True)
    if marker:
        rel=clean(marker.get_text(' ',strip=True))
        pos=text.lower().find(rel.lower())
        if pos>=0: text=text[:pos]
    return text

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    d=soup(s.get(LIST,timeout=30).text)
    links=[]
    for a in d.select('a[href*="/ca/programacio/c/"]'):
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
        # Header format: divendres, 9 d’octubre | 20:00 h
        for m in re.finditer(r"(\d{1,2})\s+d[’']?\s*([a-zà-ü]+)\s*\|\s*(\d{1,2}:\d{2})\s*h",text,re.I):
            mon=MONTHS.get(m.group(2).lower().strip("."))
            if mon: sess.append({"date":iso_date(int(m.group(1)),mon,2026),"time":m.group(3)})
        # Function block fallback: 09 / oct / 20:00 h
        if not sess:
            for m in re.finditer(r"(?:dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)\s+(\d{1,2})\s+([a-zà-ü]{3,})\s+(\d{1,2}:\d{2})\s*h",text,re.I):
                mon=MONTHS.get(m.group(2).lower().strip("."))
                if mon: sess.append({"date":iso_date(int(m.group(1)),mon,2026),"time":m.group(3)})
        sess=dedupe_sessions(sess)
        venue=None
        # Prefer known venue links/text in the primary event area.
        for candidate in ("Teatre Municipal el Jardí","Auditori Caputxins","Sala La Cate","La Cate","Bar de la Cate"):
            if candidate.lower() in text.lower(): venue=candidate; break
        cats=[]
        for a in p.select('a[href]'):
            z=clean(a.get_text(" ",strip=True))
            if z in ("Teatre","Música","Dansa","Circ","Humor","Òpera","Familiar","Projeccions"): cats.append(z)
        desc=None
        for q in p.select("main p, article p, .content p"):
            z=clean(q.get_text(" ",strip=True))
            if len(z)>80: desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="Figueres",
            venue=venue,category=" · ".join(dict.fromkeys(cats)) or None,
            description=desc or subtitle,image=best_image(p,u),sessions=sess))
    return out
