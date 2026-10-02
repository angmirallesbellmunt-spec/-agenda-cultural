
import re, requests
from urllib.parse import urljoin
from .common import *

BASE="https://www.figueresaescena.cat"
LIST=BASE+"/ca/programacio.html"
SOURCE="Figueres a Escena"

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    d=soup(s.get(LIST,timeout=30).text)
    links=[]
    for a in d.select('a[href*="/ca/programacio/c/"]'):
        u=urljoin(BASE,a.get("href"))
        if u not in links: links.append(u)
    out=[]
    for u in links:
        p=soup(s.get(u,timeout=30).text)
        h1=p.select_one("h1")
        if not h1: continue
        title=clean(h1.get_text(" ",strip=True))
        h2=p.select_one("h1 + h2")
        subtitle=clean(h2.get_text(" ",strip=True)) if h2 else None
        text=p.get_text("\n",strip=True)
        sess=[]
        # La fitxa repeteix la funció a l'encapçalament i a "Funcions"; dedupliquem.
        for m in re.finditer(r"(\d{1,2})\s+d['’e]?\s*([a-zà-ü]+).*?\|\s*(\d{1,2}:\d{2})\s*h",text,re.I):
            mon=MONTHS.get(m.group(2).lower().strip("."))
            if mon: sess.append({"date":iso_date(int(m.group(1)),mon,2026),"time":m.group(3)})
        if not sess:
            x=parse_long_date(text)
            if x: sess=[x]
        sess=[dict(t) for t in {tuple(sorted(x.items())) for x in sess}]
        venue=None
        va=p.select_one('a[href*="/espais/"], a[href*="/espai/"]')
        if va: venue=clean(va.get_text(" ",strip=True))
        if not venue:
            for candidate in ("Teatre Municipal el Jardí","Sala La Cate","La Cate","Auditori Caputxins","Bar de la Cate"):
                if candidate.lower() in text.lower(): venue=candidate; break
        cats=[]
        for a in p.select('a[href*="cPath"], a[href*="/programacio/"]'):
            z=clean(a.get_text(" ",strip=True))
            if z in ("Teatre","Música","Dansa","Circ","Humor","Òpera","Familiar","Projeccions"): cats.append(z)
        desc=None
        for q in p.select("main p, article p, .content p"):
            z=clean(q.get_text(" ",strip=True))
            if len(z)>80: desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="Figueres",
            venue=venue,category=" · ".join(dict.fromkeys(cats)) or None,
            description=desc or subtitle,image=best_image(p,u),sessions=sorted(sess,key=lambda x:(x["date"],x.get("time") or ""))))
    return out
