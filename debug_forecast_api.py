import os
import django
import json
import requests
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

def test_forecast_api():
    print("🧪 Testing forecast API endpoint...")
    
    # Create sample data that mimics what the frontend sends
    sample_data = [
        {"date": "2023-01-01", "sales": 100},
        {"date": "2023-01-02", "sales": 105},
        {"date": "2023-01-03", "sales": 110},
        {"date": "2023-01-04", "sales": 115},
        {"date": "2023-01-05", "sales": 120},
        {"date": "2023-01-06", "sales": 125},
        {"date": "2023-01-07", "sales": 130},
        {"date": "2023-01-08", "sales": 135},
        {"date": "2023-01-09", "sales": 140},
        {"date": "2023-01-10", "sales": 145},
        {"date": "2023-01-11", "sales": 150},
        {"date": "2023-01-12", "sales": 155},
        {"date": "2023-01-13", "sales": 160},
        {"date": "2023-01-14", "sales": 165},
        {"date": "2023-01-15", "sales": 170},
        {"date": "2023-01-16", "sales": 175},
        {"date": "2023-01-17", "sales": 180},
        {"date": "2023-01-18", "sales": 185},
        {"date": "2023-01-19", "sales": 190},
        {"date": "2023-01-20", "sales": 195},
        {"date": "2023-01-21", "sales": 200},
        {"date": "2023-01-22", "sales": 205},
        {"date": "2023-01-23", "sales": 210},
        {"date": "2023-01-24", "sales": 215},
        {"date": "2023-01-25", "sales": 220},
        {"date": "2023-01-26", "sales": 225},
        {"date": "2023-01-27", "sales": 230},
        {"date": "2023-01-28", "sales": 235},
        {"date": "2023-01-29", "sales": 240},
        {"date": "2023-01-30", "sales": 245},
        {"date": "2023-01-31", "sales": 250},
    ]
    
    # Create or get test user
    user, created = User.objects.get_or_create(
        username='testuser2',
        defaults={'email': 'test2@example.com'}
    )
    print(f"👤 Using user: {user.username} (created: {created})")
    
    # Create Django test client
    client = Client()
    client.force_login(user)
    
    # Prepare request data exactly like the frontend
    request_data = {
        'name': 'Test API Forecast',
        'date_column': 'date',
        'target_column': 'sales',
        'method': 'prophet',  # Start with prophet as it worked in our test
        'period': 7,
        'parameters': {
            'growth': 'linear',
            'seasonality_mode': 'additive'
        },
        'historical_data': sample_data
    }
    
    print("📤 Sending POST request to /forecasting/api/generate-forecast/")
    print(f"📊 Data: {len(sample_data)} historical points")
    print(f"🎯 Target: {request_data['target_column']}")
    print(f"📅 Date column: {request_data['date_column']}")
    print(f"🔮 Method: {request_data['method']}")
    
    try:
        # Make the API call
        response = client.post(
            '/forecasting/api/generate-forecast/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"📊 Response: {json.dumps(result, indent=2)}")
        else:
            print("❌ Error response:")
            try:
                error_data = response.json()
                print(f"📄 Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"📄 Raw response: {response.content.decode()}")
                
    except Exception as e:
        print(f"❌ Exception during API call: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_forecast_api() 