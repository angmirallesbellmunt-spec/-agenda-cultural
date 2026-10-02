
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
    # Prioritat: og:image -> twitter:image -> imatge principal de contingut.
    for sel, attr in [('meta[property="og:image"]',"content"),('meta[name="twitter:image"]',"content")]:
        n=doc.select_one(sel)
        if n and n.get(attr): return abs_url(base,n.get(attr))
    for n in doc.select("main img, article img, .content img, .fitxa img, img"):
        u=n.get("data-src") or n.get("data-lazy-src") or n.get("src")
        if u and not any(x in u.lower() for x in ("logo","icon","sprite","avatar")):
            return abs_url(base,u)
    return None

def stable_id(source, url, title):
    return source+"-"+hashlib.sha1((url+"|"+title).encode()).hexdigest()[:12]

def iso_date(day, month, year=2026):
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_cat_short_date(text, default_year=2026):
    # dg. 04.10.26 | 18:00 h
    m=re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s*\|\s*(\d{1,2}:\d{2}))?", text)
    if not m: return None
    d,mo,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
    y = 2000+y if y<100 else y
    return {"date":iso_date(d,mo,y),"time":m.group(4)}

def parse_long_date(text, year=2026):
    # divendres 2 d’octubre | 21:00 h
    low=text.lower().replace("’","'").replace("d'","")
    m=re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zà-ü]+)",low)
    if not m: return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon: return None
    tm=re.search(r"(\d{1,2}:\d{2})",text)
    return {"date":iso_date(int(m.group(1)),mon,year),"time":tm.group(1) if tm else None}

def normalize_event(*, source, title, url, municipality, venue=None, category=None,
                    description=None, image=None, sessions=None):
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
      "sessions": sessions or []
    }
