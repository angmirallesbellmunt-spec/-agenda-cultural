import re, requests
from urllib.parse import urljoin, urlsplit, urlunsplit
from .common import *

BASE='https://www.figueresaescena.cat'
LIST=BASE+'/ca/programacio.html'
SOURCE='Figueres a Escena'

def canonical(u):
    p=urlsplit(u)
    return urlunsplit((p.scheme,p.netloc,p.path,'',''))

def own_text(p):
    # stripped_strings is deliberately used instead of a CSS container: on this site
    # the event metadata and the related carousel may live in the same broad wrapper.
    lines=[clean(x) for x in p.stripped_strings if clean(x)]
    out=[]
    for x in lines:
        if x.lower()=='activitats relacionades': break
        out.append(x)
    return '\n'.join(out)

def sessions_from(text):
    t=text.replace('’',"'")
    out=[]
    # Header: divendres, 9 d'octubre | 20:00 h
    for m in re.finditer(r"\b(\d{1,2})\s+d\s*'?\s*([a-zà-ÿ]+)\s*\|\s*(\d{1,2}:\d{2})\s*h",t,re.I):
        mon=MONTHS.get(m.group(2).lower().strip('.'))
        if mon: out.append({'date':iso_date(int(m.group(1)),mon,2026),'time':m.group(3)})
    # Functions block: Divendres / 09 / oct / 20:00 h
    if not out:
        flat=' '.join(t.split())
        for m in re.finditer(r"(?:dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)\s+(\d{1,2})\s+([a-zà-ÿ]{3,})\s+(\d{1,2}:\d{2})\s*h",flat,re.I):
            mon=MONTHS.get(m.group(2).lower().strip('.'))
            if mon: out.append({'date':iso_date(int(m.group(1)),mon,2026),'time':m.group(3)})
    return dedupe_sessions(out)

def period_from(text):
    m=re.search(r"Del\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s+al\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})",text,re.I)
    if not m: return (None,None)
    vals=[int(x) for x in m.groups()]
    y1=2000+vals[2] if vals[2]<100 else vals[2]; y2=2000+vals[5] if vals[5]<100 else vals[5]
    return (iso_date(vals[0],vals[1],y1), iso_date(vals[3],vals[4],y2))

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    d=soup(s.get(LIST,timeout=30).text)
    links=[]
    for a in d.select('a[href*="/ca/programacio/c/"]'):
        u=canonical(urljoin(BASE,a.get('href')))
        if u not in links: links.append(u)
    out=[]
    for u in links:
        p=soup(s.get(u,timeout=30).text)
        h1=p.select_one('h1')
        if not h1: continue
        title=clean(h1.get_text(' ',strip=True)); text=own_text(p)
        sessions=sessions_from(text); date_start,date_end=period_from(text)
        venue=None
        for a in p.select('a[href]'):
            z=clean(a.get_text(' ',strip=True))
            if z in ('Teatre Municipal el Jardí','Auditori Caputxins','Sala La Cate','La Cate','Bar de la Cate','Cercle Sport Figuerenc'):
                venue=z; break
        if not venue:
            m=re.search(r'Espai:\s*([^\n]+)',text,re.I)
            if m: venue=clean(m.group(1))
        cats=[]
        for a in p.select('a[href]'):
            z=clean(a.get_text(' ',strip=True))
            if z in ('Teatre','Música','Dansa','Circ','Humor','Òpera','Familiar','Projeccions') and z not in cats: cats.append(z)
        subtitle=p.select_one('h1 + h2')
        desc=clean(subtitle.get_text(' ',strip=True)) if subtitle else None
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality='Figueres',venue=venue,
            category=' · '.join(cats) or None,description=desc,image=best_image(p,u),sessions=sessions,date_start=date_start,date_end=date_end))
    return out
