
import re, requests
from urllib.parse import urljoin
from .common import *

BASE="https://agenda.labisbal.cat"
LIST=BASE+"/ca/agenda.html"
SOURCE="Agenda de la Bisbal"

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    html=s.get(LIST,timeout=30).text
    d=soup(html)
    links=[]
    for a in d.select('a[href*="/ca/agenda/c/"]'):
        u=urljoin(BASE,a.get("href"))
        if u not in links: links.append(u)
    out=[]
    for u in links:
        r=s.get(u,timeout=30); p=soup(r.text)
        h1=p.select_one("h1")
        if not h1: continue
        title=clean(h1.get_text(" ",strip=True))
        h2=p.select_one("h1 + h2")
        subtitle=clean(h2.get_text(" ",strip=True)) if h2 else None
        text=p.get_text("\n",strip=True)
        sess=[]
        # Dates curtes i llargues; deduplicació posterior.
        for m in re.finditer(r"(?:dl|dt|dc|dj|dv|ds|dg)\.\s*(\d{2})\.(\d{2})\.(\d{2})\s*\|\s*(\d{2}:\d{2})",text,re.I):
            sess.append({"date":f"20{m.group(3)}-{m.group(2)}-{m.group(1)}","time":m.group(4)})
        if not sess:
            x=parse_long_date(text)
            if x: sess=[x]
        sess=[dict(t) for t in {tuple(sorted(x.items())) for x in sess}]
        # Espai: primer enllaç cap a /espais/ o, si no, heurística sobre Teatre/Museu/Biblioteca.
        venue=None
        va=p.select_one('a[href*="/espais/"], a[href*="/espai/"]')
        if va: venue=clean(va.get_text(" ",strip=True))
        if not venue:
            mm=re.search(r"\n((?:Teatre|Terracotta|Biblioteca|Ermita|Brava)[^\n]+)",text)
            venue=clean(mm.group(1)) if mm else None
        cats=[clean(a.get_text(" ",strip=True)) for a in p.select('a[href*="categoria"], a[href*="/agenda/t/"]')]
        desc=None
        # Primer paràgraf substancial després de la imatge/metadata.
        for q in p.select("main p, article p, .content p"):
            z=clean(q.get_text(" ",strip=True))
            if len(z)>80: desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="La Bisbal d'Empordà",
            venue=venue,category=" · ".join(dict.fromkeys(cats)) or None,
            description=desc or subtitle,image=best_image(p,u),sessions=sorted(sess,key=lambda x:(x["date"],x.get("time") or ""))))
    return out
