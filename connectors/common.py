from __future__ import annotations
import re, hashlib
from urllib.parse import urljoin
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS={"User-Agent":"AgendaCulturalBot/1.0 (+cultural agenda prototype)"}
MONTHS={"gener":1,"febrer":2,"març":3,"abril":4,"maig":5,"juny":6,"juliol":7,"agost":8,"setembre":9,"octubre":10,"novembre":11,"desembre":12,
        "gen":1,"feb":2,"mar":3,"abr":4,"mai":5,"jun":6,"jul":7,"ago":8,"set":9,"oct":10,"nov":11,"des":12}

def clean(s):
    return re.sub(r"\s+"," ",s or "").strip()

def abs_url(base, u):
    return urljoin(base, u) if u else None

def soup(html):
    return BeautifulSoup(html, "html.parser")

def best_image(doc, base):
    # Criteri editorial: fotografia de contingut abans que cartell o creativitat.
    # Si totes les candidates semblen peces gràfiques, no publiquem imatge.
    bad = (
        "cartell","poster","flyer","banner","programa","agenda-","agenda_",
        "xxss","xarxes","instagram","facebook","story","stories","newsletter",
        "logo","icon","icona","icones_","sprite","avatar","capcalera","capçalera","capturadepantalla","captura-de-pantalla"
    )
    good = ("foto","photo","retrat","portrait","imatge","image","galeria","gallery")
    candidates=[]; seen=set()

    # Recorrem la fitxa en ordre i parem abans de les activitats relacionades,
    # per no acabar agafant la foto d'un altre esdeveniment.
    for n in doc.find_all(["h2","h3","h4","img"]):
        if n.name != "img":
            if clean(n.get_text(" ",strip=True)).lower() == "activitats relacionades":
                break
            continue
        u=n.get("data-src") or n.get("data-lazy-src") or n.get("src")
        if not u: continue
        u=abs_url(base,u)
        if not u or u in seen: continue
        seen.add(u)
        alt=clean(n.get("alt")); title=clean(n.get("title"))
        hay=(u+" "+alt+" "+title).lower()
        if any(x in hay for x in bad): continue

        score=0
        if any(x in hay for x in good): score+=50000
        try:
            w=int(re.sub(r"\D","",str(n.get("width") or "0")) or 0)
            h=int(re.sub(r"\D","",str(n.get("height") or "0")) or 0)
            if w>=600 and h>=400: score+=w*h
        except Exception:
            pass
        candidates.append((score,u))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]

def stable_id(source, url, title):
    return source+"-"+hashlib.sha1((url+"|"+title).encode()).hexdigest()[:12]

def iso_date(day, month, year=2026):
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_cat_short_date(text, default_year=2026):
    m=re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s*\|\s*(\d{1,2}:\d{2}))?", text)
    if not m: return None
    d,mo,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
    y = 2000+y if y<100 else y
    return {"date":iso_date(d,mo,y),"time":m.group(4)}

def parse_long_date(text, year=2026):
    low=text.lower().replace("’","'").replace("d'","")
    m=re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zà-ü]+)",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    tm=re.search(r"(\d{1,2}:\d{2})",text)
    return {"date":iso_date(int(m.group(1)),mon,year),"time":tm.group(1) if tm else None}

def normalize_event(*, source, title, url, municipality, venue=None, category=None,
                    description=None, image=None, sessions=None, date_start=None, date_end=None):
    return {
      "id": stable_id(source,url,title),
      "title": clean(title),
      "image": image,
      "municipality": municipality,
      "venue": clean(venue) or None,
      "category": clean(category) or None,
      "description": clean(description) or None,
      "url": url,
      "source": source,
      "date_start": date_start,
      "date_end": date_end,
      "sessions": sessions or []
    }

def dedupe_sessions(items):
    seen=set(); out=[]
    for x in items or []:
        key=(x.get("date"),x.get("time"))
        if key[0] and key not in seen:
            seen.add(key); out.append({"date":key[0],"time":key[1]})
    return sorted(out,key=lambda x:(x["date"],x.get("time") or ""))
