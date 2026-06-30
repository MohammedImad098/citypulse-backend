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
        result = supabase.table("incidents").insert(incident).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))