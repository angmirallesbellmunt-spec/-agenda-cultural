from datetime import datetime, timezone
import json
import os
from pathlib import Path

from supabase import create_client
from connectors import figueres, bisbal, museu_emporda


ROOT = Path(__file__).parent
connectors = [figueres, bisbal, museu_emporda]

events = []
report = []


# --------------------------------------------------
# 1. RECOLLIDA D'ACTIVITATS DELS CONNECTORS
# --------------------------------------------------

for c in connectors:
    try:
        rows = c.run()
        events.extend(rows)

        report.append({
            "connector": c.__name__,
            "ok": True,
            "events": len(rows),
            "with_image": sum(bool(x["image"]) for x in rows),
            "with_sessions": sum(bool(x["sessions"]) for x in rows),
            "with_venue": sum(bool(x["venue"]) for x in rows),
            "with_municipality": sum(bool(x["municipality"]) for x in rows)
        })

    except Exception as e:
        report.append({
            "connector": c.__name__,
            "ok": False,
            "error": repr(e)
        })


# --------------------------------------------------
# 2. DEDUPLICACIÓ I ORDENACIÓ
# --------------------------------------------------

unique = {e["id"]: e for e in events}
events = list(unique.values())

events.sort(
    key=lambda e: (
        e["sessions"][0]["date"] if e["sessions"] else "9999-12-31",
        e["title"]
    )
)


# --------------------------------------------------
# 3. GENERACIÓ DE data/events.json
#    Mantenim el sistema actual intacte
# --------------------------------------------------

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "events": events,
    "validation": report
}

(ROOT / "data/events.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8"
)


# --------------------------------------------------
# 4. SINCRONITZACIÓ AMB SUPABASE
# --------------------------------------------------

def sync_supabase(events):
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_key:
        print("Supabase: no configurat. Es manté només events.json.")
        return

    try:
        supabase = create_client(supabase_url, supabase_key)

        for event in events:

            event_data = {
                "external_id": event["id"],
                "title": event.get("title"),
                "image": event.get("image"),
                "municipality": event.get("municipality"),
                "venue": event.get("venue"),
                "description": event.get("description"),
                "url": event.get("url"),
                "source": event.get("source"),
                "status": "published",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            # Crea l'activitat si és nova o l'actualitza
            # si external_id ja existeix.
            result = (
                supabase
                .table("events")
                .upsert(event_data, on_conflict="external_id")
                .execute()
            )

            if not result.data:
                continue

            event_db_id = result.data[0]["id"]

            # Eliminem les sessions antigues d'aquesta activitat
            # i hi tornem a escriure les actuals.
            supabase.table("sessions").delete().eq(
                "event_id", event_db_id
            ).execute()

            sessions = []

            for session in event.get("sessions", []):
                if not session.get("date"):
                    continue

                sessions.append({
                    "event_id": event_db_id,
                    "date": session.get("date"),
                    "time": session.get("time") or None
                })

            if sessions:
                supabase.table("sessions").insert(sessions).execute()

        print(f"Supabase: {len(events)} activitats sincronitzades.")

    except Exception as e:
        # IMPORTANT:
        # Un error de Supabase no impedeix generar events.json
        print(f"Supabase ERROR: {repr(e)}")


sync_supabase(events)


# --------------------------------------------------
# 5. INFORME DELS CONNECTORS
# --------------------------------------------------

print(json.dumps(report, ensure_ascii=False, indent=2))
