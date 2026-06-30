from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Service-role client for privileged operations (DELETE)
supabase_admin = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
)

# ── Static lookup tables ───────────────────────────────────────────────────────

WEATHER_BY_MONTH = {
    12: 1.4, 1: 1.4, 2: 1.4,    # Winter
    3: 1.2,  4: 1.2, 11: 1.2,   # Shoulder seasons
}
WEATHER_DEFAULT = 1.05           # May–October

IMPACT_BY_BOROUGH = {
    "MANHATTAN":    2.0,
    "BROOKLYN":     1.8,
    "BRONX":        1.6,
    "QUEENS":       1.5,
    "STATEN ISLAND":1.2,
}

ACCESSIBILITY_BY_BOROUGH = {
    "BRONX":         1.3,
    "BROOKLYN":      1.1,
    "QUEENS":        1.0,
    "STATEN ISLAND": 1.0,
    "MANHATTAN":     0.9,
}

# ── Dataset stats (computed once at startup) ───────────────────────────────────

_borough_avg_complaints: dict[str, float] = {}

# Fixed thresholds calibrated for the manual-incident scoring formula.
# The 311 dataset was scored by a different ML pipeline, so dynamically
# re-deriving p25/p50/p75 from those scores produces incompatible cutoffs.
THRESHOLDS: tuple[float, float, float] = (6.63, 7.42, 8.14)


def _load_dataset_stats() -> None:
    global _borough_avg_complaints  # noqa: PLW0603
    try:
        all_rows = []
        batch, offset = 1000, 0
        while True:
            result = (
                supabase.table("incidents")
                .select("borough,complaints")
                .range(offset, offset + batch - 1)
                .execute()
            )
            all_rows.extend(result.data)
            if len(result.data) < batch:
                break
            offset += batch

        borough_complaints: dict[str, list[float]] = defaultdict(list)

        for row in all_rows:
            b = (row.get("borough") or "").upper().strip()
            c = row.get("complaints")
            if c is not None:
                try:
                    borough_complaints[b].append(float(c))
                except (ValueError, TypeError):
                    pass

        _borough_avg_complaints = {
            b: round(sum(vals) / len(vals), 3)
            for b, vals in borough_complaints.items() if vals
        }

        print(f"[startup] loaded {len(all_rows)} rows")
        print(f"[startup] borough avg complaints: {_borough_avg_complaints}")
        print(f"[startup] thresholds p25={_thresholds[0]:.3f} p50={_thresholds[1]:.3f} p75={_thresholds[2]:.3f}")

    except Exception as e:
        print(f"[startup] stats load failed, using fallbacks: {e}")


_load_dataset_stats()

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "CityPulse AI Backend is running"}


@app.get("/incidents")
def get_incidents(borough: str = None):
    all_data = []
    batch = 1000
    offset = 0
    while True:
        query = (
            supabase.table("incidents")
            .select("*")
            .order("priority_score", desc=True)
            .range(offset, offset + batch - 1)
        )
        if borough:
            query = query.eq("borough", borough.upper())
        result = query.execute()
        all_data.extend(result.data)
        if len(result.data) < batch:
            break
        offset += batch
    return all_data


@app.delete("/incidents/{incident_id}")
def delete_incident(incident_id: str):
    try:
        supabase_admin.table("incidents").delete().eq("id", incident_id).execute()
        return {"deleted": incident_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/incidents")
def add_incident(incident: dict):
    try:
        # [3] received severity
        print(f"[3] received severity={incident.get('severity')!r} (type={type(incident.get('severity')).__name__}) source={incident.get('source')!r}")

        severity = float(incident.get("severity", 3))
        borough  = (incident.get("borough") or "").upper().strip()
        month    = datetime.now().month

        weather       = WEATHER_BY_MONTH.get(month, WEATHER_DEFAULT)
        impact        = IMPACT_BY_BOROUGH.get(borough, 1.5)
        accessibility = ACCESSIBILITY_BY_BOROUGH.get(borough, 1.0)
        complaints    = _borough_avg_complaints.get(borough, 1.5)

        # [4] before priority_score
        print(f"[4] borough={borough!r} severity={severity} weather={weather} impact={impact} complaints={complaints} accessibility={accessibility}")

        priority_score = round((severity * weather) + impact + complaints + accessibility, 2)

        # [5] after priority_score
        print(f"[5] priority_score={priority_score}")

        p25, p50, p75 = THRESHOLDS

        # [6] before label assignment
        print(f"[6] score={priority_score} vs p25={p25} p50={p50} p75={p75} → ", end="")

        if priority_score >= p75:
            priority_label = "Critical"
        elif priority_score >= p50:
            priority_label = "High"
        elif priority_score >= p25:
            priority_label = "Medium"
        else:
            priority_label = "Low"

        print(priority_label)

        incident.update({
            "weather":        weather,
            "complaints":     complaints,
            "impact":         impact,
            "accessibility":  accessibility,
            "priority_score": priority_score,
            "priority_label": priority_label,
        })

        print(f"[insert] source={incident.get('source')!r} priority_label={priority_label!r}")

        result = supabase.table("incidents").insert(incident).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
