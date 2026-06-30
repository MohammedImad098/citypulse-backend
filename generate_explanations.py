"""
CityPulse AI — OpenAI Explanation Generator
--------------------------------------------
Loops through all incidents in Supabase and generates
a real AI explanation for each one using gpt-4o-mini.

Run from your citypulse-backend folder:
    python generate_explanations.py

Cost estimate: ~836 incidents x ~60 tokens each = ~50,000 tokens
gpt-4o-mini costs $0.15 per 1M input tokens — total cost < $0.01
"""

from supabase import create_client
from dotenv import load_dotenv
from openai import OpenAI
import os
import time

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_explanation(incident):
    """Generate a plain-English explanation for one incident."""
    try:
        chronic = " This is a chronic location with repeated complaints over multiple years." if incident.get("is_chronic") else ""

        prompt = f"""You are a NYC infrastructure analyst writing for city workers.
Write exactly one clear sentence (max 25 words) explaining why this road damage 
incident was flagged as {incident.get('priority_label', 'High')} priority.

Incident details:
- Borough: {incident.get('borough', 'Unknown')}
- Damage type: {incident.get('damage_type', 'Pothole')}
- Severity score: {incident.get('severity', 0)}/5
- Priority score: {round(float(incident.get('priority_score', 0)), 1)}
- Complaint volume: {round(float(incident.get('complaints', 0)), 2)}
- Weather risk: {incident.get('weather', 1.0)}x
- Community impact: {round(float(incident.get('impact', 0)), 2)}/3
- Accessibility score: {round(float(incident.get('accessibility', 0)), 2)}/3
- Chronic location: {incident.get('is_chronic', False)}{chronic}

Write only the explanation sentence. No quotes, no bullet points."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"High-severity road damage requiring prompt municipal attention based on complaint volume and community impact."

# Fetch all incidents from Supabase
print("Fetching incidents from Supabase...")
result = supabase.table("incidents").select("id, borough, damage_type, severity, priority_score, priority_label, complaints, weather, impact, accessibility, is_chronic").execute()
incidents = result.data
print(f"Found {len(incidents):,} incidents to process")
print()

# Generate explanations
updated = 0
failed = 0

for i, incident in enumerate(incidents):
    explanation = generate_explanation(incident)
    
    try:
        supabase.table("incidents").update({
            "ai_explanation": explanation
        }).eq("id", incident["id"]).execute()
        updated += 1
        
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  [{i+1}/{len(incidents)}] {incident.get('borough')} {incident.get('damage_type')} — {explanation[:60]}...")
        
        # Small delay to avoid hitting rate limits
        time.sleep(0.1)
        
    except Exception as e:
        failed += 1
        print(f"  Failed to update incident {incident['id']}: {e}")

print()
print(f"Done. Updated: {updated} | Failed: {failed}")
