from __future__ import annotations
import re, hashlib, io
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

def _real_image_size(url):
    """Retorna (amplada, alçada) llegint la imatge real. Si no es pot, retorna (0, 0)."""
    try:
        import requests
        from PIL import Image

        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()

        ctype = (r.headers.get("content-type") or "").lower()
        if ctype and not ctype.startswith("image/"):
            return (0, 0)

        with Image.open(io.BytesIO(r.content)) as im:
            return im.size
    except Exception:
        return (0, 0)

def best_image(doc, base):
    """
    Criteri editorial:
    - fotografia de contingut abans que cartell o creativitat;
    - comprova la mida REAL de l'arxiu quan és possible;
    - descarta imatges petites o amb proporcions típiques de cartell/banner;
    - prova diverses candidates;
    - si cap imatge és prou bona, retorna None.
    """
    bad = (
        "cartell","poster","flyer","banner","programa","agenda-","agenda_",
        "xxss","xarxes","instagram","facebook","story","stories","newsletter",
        "logo","icon","icona","icones_","sprite","avatar","capcalera","capçalera",
        "capturadepantalla","captura-de-pantalla","miniatura","thumbnail","thumb"
    )
    good = (
        "foto","photo","fotografia","retrat","portrait","imatge","image",
        "galeria","gallery","espectacle","artista","companyia"
    )

    candidates=[]
    seen=set()

    # Només recorrem la zona principal de la fitxa i parem abans de relacionades.
    for n in doc.find_all(["h2","h3","h4","img"]):
        if n.name != "img":
            heading = clean(n.get_text(" ",strip=True)).lower()
            if heading in ("activitats relacionades","actividades relacionadas","related events"):
                break
            continue

        u = (
            n.get("data-src")
            or n.get("data-lazy-src")
            or n.get("data-original")
            or n.get("src")
        )
        if not u:
            srcset = n.get("data-srcset") or n.get("srcset")
            if srcset:
                # Triem l'última variant del srcset, habitualment la més gran.
                u = srcset.split(",")[-1].strip().split(" ")[0]

        if not u:
            continue

        u=abs_url(base,u)
        if not u or u in seen:
            continue
        seen.add(u)

        alt=clean(n.get("alt"))
        title=clean(n.get("title"))
        classes=" ".join(n.get("class") or [])
        hay=(u+" "+alt+" "+title+" "+classes).lower()

        if any(x in hay for x in bad):
            continue

        score=0
        if any(x in hay for x in good):
            score += 500000

        # Primer intentem dimensions declarades a l'HTML.
        try:
            w=int(re.sub(r"\D","",str(n.get("width") or "0")) or 0)
            h=int(re.sub(r"\D","",str(n.get("height") or "0")) or 0)
        except Exception:
            w=h=0

        # Si no són fiables, llegim la imatge real.
        if w < 300 or h < 200:
            rw,rh=_real_image_size(u)
            if rw and rh:
                w,h=rw,rh

        # Sense mida verificable no la descartem automàticament,
        # però queda per sota de les fotografies verificades.
        if w and h:
            # Massa petita: risc clar de pixelació.
            if w < 700 or h < 400:
                continue

            ratio=w/h

            # Molt vertical: sovint cartell/flyer.
            if ratio < 0.72:
                continue

            # Molt panoràmica: sovint banner/capçalera.
            if ratio > 2.4:
                continue

            # Afavorim formats fotogràfics horitzontals o gairebé quadrats.
            if 1.15 <= ratio <= 1.9:
                score += 300000
            elif 0.85 <= ratio < 1.15:
                score += 180000
            else:
                score += 80000

            score += min(w*h, 4000000)
        else:
            score += 1000

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
