from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
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

@app.post("/incidents")
def add_incident(incident: dict):
    try:
        # Calculate priority using submitted severity + typical defaults for manual reports
        severity     = float(incident.get("severity", 3))
        weather      = 1.2   # slight weather risk
        complaints   = 1.0   # single complaint
        impact       = 2.5   # moderate community impact
        accessibility = 1.0  # average

        priority_score = round((severity * weather) + impact + complaints + accessibility, 2)

        # Thresholds from dataset percentiles: p25=6.63, p50=7.42, p75=8.14
        if priority_score >= 8.14:
            priority_label = "Critical"
        elif priority_score >= 7.42:
            priority_label = "High"
        elif priority_score >= 6.63:
            priority_label = "Medium"
        else:
            priority_label = "Low"

        incident.update({
            "weather":       weather,
            "complaints":    complaints,
            "impact":        impact,
            "accessibility": accessibility,
            "priority_score": priority_score,
            "priority_label": priority_label,
        })

        print(f"[add_incident] damage_type={incident.get('damage_type')} severity={severity} "
              f"priority_score={priority_score} priority_label={priority_label}")

        result = supabase.table("incidents").insert(incident).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))