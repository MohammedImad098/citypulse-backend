from supabase import create_client
from dotenv import load_dotenv
import os
import random

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

boroughs = ['BROOKLYN', 'BRONX', 'MANHATTAN', 'QUEENS', 'STATEN ISLAND']
damage_types = ['Pothole', 'Crack', 'Street Condition']
priority_labels = ['Critical', 'High', 'Medium', 'Low']

for i in range(50):
    incident = {
        'latitude': random.uniform(40.57, 40.74),
        'longitude': random.uniform(-74.04, -73.83),
        'damage_type': random.choice(damage_types),
        'severity': round(random.uniform(1, 5), 2),
        'complaint_type': random.choice(damage_types),
        'borough': random.choice(boroughs),
        'complaints': random.randint(1, 20),
        'weather': round(random.uniform(1.0, 1.5), 2),
        'impact': random.randint(0, 3),
        'accessibility': random.randint(0, 3),
        'priority_score': round(random.uniform(1, 15), 2),
        'priority_label': random.choice(priority_labels),
        'cv_verified': False,
        'ai_explanation': 'This location requires attention based on damage severity and community impact.',
        'days_unrepaired': random.randint(1, 365)
    }
    supabase.table('incidents').insert(incident).execute()
    print(f'Added incident {i+1}/50')

print('Done')