import re, requests
from urllib.parse import urljoin
from .common import *

BASE="https://www.museuemporda.org/"
PAGES=[BASE+"?page_id=693", BASE]
SOURCE="Museu de l'Empordà"

def _activity_links(doc):
    links=[]
    # Keep actual activity/exhibition records only; avoid arbitrary corporate pages.
    for a in doc.select('a[href]'):
        href=a.get('href','')
        if 'activitat=' in href or 'exposicions=' in href:
            u=urljoin(BASE,href)
            if u not in links: links.append(u)
    return links

def _time_from_text(text):
    # Museum metadata often displays simply "19 h" on its own line.
    m=re.search(r"(?:^|\n|\s)([01]?\d|2[0-3])(?::([0-5]\d))?\s*h(?:\b|\n)",text,re.I)
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m else None

def _sessions_from_text(text):
    out=[]; time=_time_from_text(text)
    low=text.lower().replace('’',"'")
    # 7, 14, 21 i 28 d’octubre
    for mon_name,mon in MONTHS.items():
        if len(mon_name)<4: continue
        pat=r"((?:\d{1,2}\s*(?:,|i|y)?\s*)+)\s+d[’']?"+re.escape(mon_name)
        m=re.search(pat,low,re.I)
        if m:
            for day in re.findall(r"\d{1,2}",m.group(1)):
                out.append({"date":iso_date(int(day),mon,2026),"time":time})
            break
    if not out:
        # Single date, optionally with de/d' before month.
        for mon_name,mon in MONTHS.items():
            if len(mon_name)<4: continue
            m=re.search(r"\b(\d{1,2})\s+(?:de\s+|d[’']?)?"+re.escape(mon_name)+r"\b",low,re.I)
            if m:
                out=[{"date":iso_date(int(m.group(1)),mon,2026),"time":time}]; break
    return dedupe_sessions(out)

def _museum_image(p,u):
    # Ignore the site's generic current-exhibitions tile and decorative/icon assets.
    bad=('m_actuals','icones_','filet-negre','logo','icon','sprite','avatar')
    candidates=[]
    for n in p.select('main img, article img, .et_pb_post_content img, .et_pb_text img, img'):
        src=n.get('data-src') or n.get('data-lazy-src') or n.get('src')
        if not src: continue
        src=abs_url(u,src)
        low=src.lower()
        if any(x in low for x in bad): continue
        try:
            w=int(n.get('width') or 0); h=int(n.get('height') or 0)
        except: w=h=0
        candidates.append((w*h,src))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None

def _venue(text):
    # Explicit ESPAI field first.
    m=re.search(r"(?:^|\n)ESPAI\s*\n([^\n]+)",text,re.I)
    if m: return clean(m.group(1))
    for candidate in ("Auditori del Museu de l'Empordà","Museu de l'Empordà","Sala l’Escorxador","Sala L’Escorxador","L’Escorxador"):
        if candidate.lower() in text.lower(): return candidate
    return "Museu de l'Empordà"

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
        h1=p.select_one('h1')
        if not h1: continue
        title=clean(h1.get_text(' ',strip=True))
        text=p.get_text('\n',strip=True)
        sessions=_sessions_from_text(text)
        # Agenda output should contain dated records; this also rejects corporate pages.
        if not sessions: continue
        desc=None
        for q in p.select('main p, article p, .et_pb_text p, p'):
            z=clean(q.get_text(' ',strip=True))
            if len(z)>100 and not any(x in z.lower() for x in ('cookie','alguns drets reservats','política de privacitat')):
                desc=z; break
        out.append(normalize_event(source=SOURCE,title=title,url=u,municipality='Figueres',
            venue=_venue(text),category='Museus · Art',description=desc,
            image=_museum_image(p,u),sessions=sessions))
    return out
