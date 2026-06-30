from supabase import create_client
from dotenv import load_dotenv
import os
import pandas as pd
import math

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

df = pd.read_csv("citypulse_real_311_scored.csv")

# Keep only columns that exist in Supabase
df['damage_type'] = df['complaint_type']
df['priority_label'] = df['priority_tier']
df['source'] = '311'
df['status'] = 'Open'

# Only these columns exist in Supabase
KEEP = ['latitude', 'longitude', 'damage_type', 'severity', 'complaint_type',
        'borough', 'complaints', 'weather', 'impact', 'accessibility',
        'priority_score', 'priority_label', 'source', 'status']

df = df[KEEP]

print(f"Loaded {len(df):,} rows")
print(f"Columns: {list(df.columns)}")

def clean_value(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v

inserted = 0
failed = 0
BATCH_SIZE = 500
records = df.to_dict(orient="records")

for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]
    cleaned_batch = [{k: clean_value(v) for k, v in row.items()} for row in batch]
    try:
        supabase.table("incidents").insert(cleaned_batch).execute()
        inserted += len(cleaned_batch)
        print(f"Inserted batch {i // BATCH_SIZE + 1} — {inserted}/{len(records)} total")
    except Exception as e:
        failed += len(cleaned_batch)
        print(f"Batch {i // BATCH_SIZE + 1} failed: {e}")

print(f"\nDone. Inserted: {inserted} | Failed: {failed}")