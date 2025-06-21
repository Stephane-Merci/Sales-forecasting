#!/usr/bin/env python
import requests
import json

def test_forecast_api():
    """Test the forecast API with sample data"""
    
    # Test data - similar to what might be causing the issue
    test_data = {
        "name": "Test Forecast",
        "date_column": "Date",
        "target_column": "Sales",  # This should be numeric
        "method": "Prophet",
        "period": 30,
        "parameters": {},
        "historical_data": [
            {"Date": "2023-01-01", "Sales": 100, "Category": "Electronics"},
            {"Date": "2023-01-02", "Sales": 150, "Category": "Sports"},
            {"Date": "2023-01-03", "Sales": 200, "Category": "Electronics"},
            {"Date": "2023-01-04", "Sales": 120, "Category": "Sports"},
            {"Date": "2023-01-05", "Sales": 180, "Category": "Electronics"},
            {"Date": "2023-01-06", "Sales": 160, "Category": "Sports"},
            {"Date": "2023-01-07", "Sales": 190, "Category": "Electronics"},
            {"Date": "2023-01-08", "Sales": 140, "Category": "Sports"},
            {"Date": "2023-01-09", "Sales": 210, "Category": "Electronics"},
            {"Date": "2023-01-10", "Sales": 130, "Category": "Sports"},
        ] * 5  # Multiply to get 50 rows (enough for forecasting)
    }
    
    # Add more dates to make it realistic
    import datetime
    base_date = datetime.datetime(2023, 1, 1)
    for i, record in enumerate(test_data["historical_data"]):
        new_date = base_date + datetime.timedelta(days=i)
        record["Date"] = new_date.strftime("%Y-%m-%d")
    
    print(f"Testing with {len(test_data['historical_data'])} records")
    print(f"Sample data: {test_data['historical_data'][:2]}")
    
    # Test the API
    url = "http://127.0.0.1:8000/forecasting/api/generate-forecast/"
    headers = {
        "Content-Type": "application/json",
        # Note: In a real test, you'd need to handle CSRF token and authentication
    }
    
    try:
        response = requests.post(url, json=test_data, headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"Response Data: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Connection error - make sure Django server is running")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_forecast_api() 