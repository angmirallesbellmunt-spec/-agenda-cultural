import re, requests
from urllib.parse import urljoin
from .common import *

BASE='https://www.museuemporda.org/'
PAGES=[BASE+'?page_id=693',BASE]
SOURCE="Museu de l'Empordà"

def activity_links(doc):
    out=[]
    for a in doc.select('a[href]'):
        href=a.get('href','')
        if 'activitat=' in href or 'exposicions=' in href:
            u=urljoin(BASE,href)
            if u not in out: out.append(u)
    return out

def own_lines(p):
    lines=[clean(x) for x in p.stripped_strings if clean(x)]
    out=[]
    for x in lines:
        if x.lower()=='activitats relacionades': break
        out.append(x)
    return out

def event_time(lines):
    # Museum displays e.g. 19 h as a standalone metadata value.
    for x in lines:
        m=re.fullmatch(r'([01]?\d|2[0-3])(?::([0-5]\d))?\s*h',x,re.I)
        if m: return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return None

def sessions_from(lines):
    t=' '.join(lines).lower().replace('’',"'"); tm=event_time(lines); out=[]
    # 7, 14, 21 i 28 d'octubre
    for name,mon in MONTHS.items():
        if len(name)<4: continue
        m=re.search(r"((?:\d{1,2}\s*(?:,|i|y)?\s*)+)\s+d\s*'?\s*"+re.escape(name)+r'\b',t,re.I)
        if m:
            for d in re.findall(r'\d{1,2}',m.group(1)): out.append({'date':iso_date(int(d),mon,2026),'time':tm})
            return dedupe_sessions(out)
    # Single explicit date.
    for name,mon in MONTHS.items():
        if len(name)<4: continue
        m=re.search(r"\b(\d{1,2})\s+(?:de\s+|d\s*'?\s*)?"+re.escape(name)+r'\b',t,re.I)
        if m: return [{'date':iso_date(int(m.group(1)),mon,2026),'time':tm}]
    return []

def venue_from(lines):
    for i,x in enumerate(lines[:-1]):
        if x.upper()=='ESPAI': return lines[i+1]
    return "Museu de l'Empordà"

def content_image(p,u):
    bad=('m_actuals','icones_','filet','logo','icon','sprite','avatar')
    candidates=[]
    for n in p.select('img'):
        src=n.get('data-src') or n.get('data-lazy-src') or n.get('src')
        if not src: continue
        src=abs_url(u,src); low=src.lower()
        if any(x in low for x in bad): continue
        alt=clean(n.get('alt'))
        score=0
        try: score=int(n.get('width') or 0)*int(n.get('height') or 0)
        except: pass
        if alt: score+=10000
        candidates.append((score,src))
    return max(candidates,key=lambda x:x[0])[1] if candidates else None

def run():
    s=requests.Session(); s.headers.update(HEADERS)
    links=[]
    for page in PAGES:
        d=soup(s.get(page,timeout=30).text)
        for u in activity_links(d):
            if u not in links: links.append(u)
    out=[]
    for u in links:
        p=soup(s.get(u,timeout=30).text); h1=p.select_one('h1')
        if not h1: continue
        lines=own_lines(p); sessions=sessions_from(lines)
        if not sessions: continue
        title=clean(h1.get_text(' ',strip=True)); desc=None
        for q in p.select('p'):
            z=clean(q.get_text(' ',strip=True))
            if len(z)>100 and 'alguns drets reservats' not in z.lower(): desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality='Figueres',venue=venue_from(lines),
            category='Museus · Art',description=desc,image=content_image(p,u),sessions=sessions))
    return out
