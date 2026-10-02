
from datetime import datetime, timezone
import json
from pathlib import Path
from connectors import figueres, bisbal, museu_emporda

ROOT=Path(__file__).parent
connectors=[figueres,bisbal,museu_emporda]
events=[]; report=[]
for c in connectors:
    try:
        rows=c.run()
        events.extend(rows)
        report.append({"connector":c.__name__,"ok":True,"events":len(rows),
          "with_image":sum(bool(x["image"]) for x in rows),
          "with_sessions":sum(bool(x["sessions"]) for x in rows),
          "with_venue":sum(bool(x["venue"]) for x in rows),
          "with_municipality":sum(bool(x["municipality"]) for x in rows)})
    except Exception as e:
        report.append({"connector":c.__name__,"ok":False,"error":repr(e)})

# Deduplicació per id i ordenació per primera sessió.
unique={e["id"]:e for e in events}
events=list(unique.values())
events.sort(key=lambda e: ((e["sessions"][0]["date"] if e["sessions"] else "9999-12-31"), e["title"]))

payload={"generated_at":datetime.now(timezone.utc).isoformat(),"events":events,"validation":report}
(ROOT/"data/events.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
