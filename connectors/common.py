from __future__ import annotations
import re, hashlib, io
from urllib.parse import urljoin
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

def _image_info(url):
    """Mida real i pes de l'arxiu. Si no es pot verificar, la imatge no és apta."""
    try:
        import requests
        from PIL import Image
        r=requests.get(url,headers=HEADERS,timeout=12)
        r.raise_for_status()
        if not (r.headers.get("content-type") or "").lower().startswith("image/"):
            return None
        raw=r.content
        with Image.open(io.BytesIO(raw)) as im:
            w,h=im.size
        return w,h,len(raw)
    except Exception:
        return None

def best_image(doc, base):
    """
    Filtre editorial conservador.
    Només retorna una imatge si podem verificar que és prou gran i no presenta
    indicis HTML/URL de cartell, banner, flyer o creativitat de xarxes.
    Davant del dubte retorna None.
    """
    bad=(
        "cartell","poster","flyer","banner","programa","agenda-","agenda_",
        "xxss","xarxes","instagram","facebook","story","stories","newsletter",
        "logo","icon","icona","icones_","sprite","avatar","capcalera","capçalera",
        "capturadepantalla","captura-de-pantalla","miniatura","thumbnail","thumb",
        "creativitat","creativa","grafisme","graphic","cover","portada"
    )
    good=("foto","photo","fotografia","retrat","portrait","galeria","gallery")
    candidates=[]; seen=set()

    for n in doc.find_all(["h2","h3","h4","img"]):
        if n.name!="img":
            if clean(n.get_text(" ",strip=True)).lower() in (
                "activitats relacionades","actividades relacionadas","related events"
            ):
                break
            continue

        u=n.get("data-src") or n.get("data-lazy-src") or n.get("data-original") or n.get("src")
        srcset=n.get("data-srcset") or n.get("srcset")
        if srcset:
            # prova la versió més gran anunciada pel web
            choices=[]
            for item in srcset.split(","):
                parts=item.strip().split()
                if parts:
                    width=0
                    if len(parts)>1 and parts[1].endswith("w"):
                        try: width=int(parts[1][:-1])
                        except: pass
                    choices.append((width,parts[0]))
            if choices:
                choices.sort()
                u=choices[-1][1]
        if not u: continue
        u=abs_url(base,u)
        if not u or u in seen: continue
        seen.add(u)

        hay=" ".join([
            u, clean(n.get("alt")), clean(n.get("title")),
            " ".join(n.get("class") or [])
        ]).lower()
        if any(x in hay for x in bad):
            continue

        info=_image_info(u)
        if not info:
            continue
        w,h,nbytes=info

        # Resolució real mínima exigent: evita miniatures i imatges que es veuran pixelades.
        if w < 1200 or h < 650:
            continue
        ratio=w/h
        # Molts cartells són molt verticals i molts banners massa panoràmics.
        if ratio < 0.90 or ratio > 2.05:
            continue
        # Arxius extraordinàriament petits per la seva superfície solen ser miniatures
        # molt comprimides o ampliades.
        if nbytes < 90000:
            continue

        score=w*h
        if any(x in hay for x in good):
            score += 5_000_000
        if 1.20 <= ratio <= 1.85:
            score += 1_000_000
        candidates.append((score,u))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]

def stable_id(source,url,title):
    return source+"-"+hashlib.sha1((url+"|"+title).encode()).hexdigest()[:12]

def iso_date(day,month,year=2026):
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_cat_short_date(text,default_year=2026):
    m=re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s*\|\s*(\d{1,2}:\d{2}))?",text)
    if not m:return None
    d,mo,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
    y=2000+y if y<100 else y
    return {"date":iso_date(d,mo,y),"time":m.group(4)}

def parse_long_date(text,year=2026):
    low=text.lower().replace("’","'").replace("d'","")
    m=re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zà-ü]+)",low)
    if not m:return None
    mon=MONTHS.get(m.group(2).strip("."))
    if not mon:return None
    tm=re.search(r"(\d{1,2}:\d{2})",text)
    return {"date":iso_date(int(m.group(1)),mon,year),"time":tm.group(1) if tm else None}

def normalize_event(*,source,title,url,municipality,venue=None,category=None,
                    description=None,image=None,sessions=None,date_start=None,date_end=None):
    return {
      "id":stable_id(source,url,title),"title":clean(title),"image":image,
      "municipality":municipality,"venue":clean(venue) or None,
      "category":clean(category) or None,"description":clean(description) or None,
      "url":url,"source":source,"date_start":date_start,"date_end":date_end,
      "sessions":sessions or []
    }

def dedupe_sessions(items):
    seen=set();out=[]
    for x in items or []:
        key=(x.get("date"),x.get("time"))
        if key[0] and key not in seen:
            seen.add(key);out.append({"date":key[0],"time":key[1]})
    return sorted(out,key=lambda x:(x["date"],x.get("time") or ""))
