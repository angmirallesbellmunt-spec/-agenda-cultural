import re, requests
from urllib.parse import urljoin, urlsplit, urlunsplit
from .common import *

BASE='https://agenda.labisbal.cat'
LIST=BASE+'/ca/agenda.html'
SOURCE='Agenda de la Bisbal'

def canonical(u):
    p=urlsplit(u)
    return urlunsplit((p.scheme,p.netloc,p.path,'',''))

def own_lines(p):
    lines=[clean(x) for x in p.stripped_strings if clean(x)]
    out=[]
    for x in lines:
        if x.lower()=='activitats relacionades': break
        out.append(x)
    return out

def sessions_from(lines):
    t='\n'.join(lines).replace('’',"'")
    out=[]
    for m in re.finditer(r"\b(\d{1,2})\s+d\s*'?\s*([a-zà-ÿ]+)\s*\|\s*(\d{1,2}:\d{2})\s*h",t,re.I):
        mon=MONTHS.get(m.group(2).lower().strip('.'))
        if mon: out.append({'date':iso_date(int(m.group(1)),mon,2026),'time':m.group(3)})
    if not out:
        flat=' '.join(lines)
        for m in re.finditer(r"(?:dl|dt|dc|dj|dv|ds|dg)\.\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*\|\s*(\d{1,2}:\d{2})",flat,re.I):
            y=int(m.group(3)); y=2000+y if y<100 else y
            out.append({'date':iso_date(int(m.group(1)),int(m.group(2)),y),'time':m.group(4)})
    return dedupe_sessions(out)

def period_from(lines):
    t=' '.join(lines)
    m=re.search(r"Del\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s+al\s+(?:dl|dt|dc|dj|dv|ds|dg)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})",t,re.I)
    if not m: return (None,None)
    vals=[int(x) for x in m.groups()]
    y1=2000+vals[2] if vals[2]<100 else vals[2]; y2=2000+vals[5] if vals[5]<100 else vals[5]
    return (iso_date(vals[0],vals[1],y1), iso_date(vals[3],vals[4],y2))

def venue_from(p, lines):
    # On the detail page the venue is a linked value immediately after the date.
    own='\n'.join(lines)
    for a in p.select('a[href]'):
        z=clean(a.get_text(' ',strip=True))
        if z and z in own and z.lower() not in ('agenda','espais','afegeix activitat','comprar','google','apple','outlook web','música','teatre','dansa','circ','familiar','cinema'):
            href=(a.get('href') or '').lower()
            if '/espais/' in href or '/espai/' in href: return z
    known=('Teatre Mundial','Terracotta Museu','Biblioteca Lluïsa Duran','Castell Palau','Ermita del Remei','Brava Performing Arts','Espai Brava Arts','Claustre del Convent dels Franciscans')
    for z in known:
        if z.lower() in own.lower(): return z
    return None

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    d=soup(s.get(LIST,timeout=30).text)
    links=[]
    for a in d.select('a[href*="/ca/agenda/c/"]'):
        u=canonical(urljoin(BASE,a.get('href')))
        if u not in links: links.append(u)
    out=[]
    for u in links:
        p=soup(s.get(u,timeout=30).text); h1=p.select_one('h1')
        if not h1: continue
        title=clean(h1.get_text(' ',strip=True)); lines=own_lines(p); sessions=sessions_from(lines); date_start,date_end=period_from(lines)
        subtitle=p.select_one('h1 + h2'); desc=clean(subtitle.get_text(' ',strip=True)) if subtitle else None
        cats=[]
        for a in p.select('a[href]'):
            z=clean(a.get_text(' ',strip=True))
            if z in ('Música','Teatre','Dansa','Circ','Familiar','Cinema','Exposicions','Xerrades i conferències','Tallers') and z not in cats: cats.append(z)
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality="La Bisbal d'Empordà",
            venue=venue_from(p,lines),category=' · '.join(cats) or None,description=desc,
            image=best_image(p,u),sessions=sessions,date_start=date_start,date_end=date_end))
    return out
