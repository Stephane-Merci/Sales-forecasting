import os
import django
import json
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from authentication.models import User
from forecasting.mongodb_models import ForecastDocument
from forecasting.services import ForecastingService

def test_forecast_generation():
    print("🧪 Testing forecast generation and MongoDB saving...")
    
    # Create sample data
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
    
    print(f"📊 Created sample data with {len(sample_data)} points")
    
    # Test forecasting service
    try:
        service = ForecastingService()
        print("✅ ForecastingService initialized")
        
        # Test data validation
        is_valid, message = service.validate_data(sample_data, 'date', 'sales')
        print(f"📝 Data validation: {is_valid} - {message}")
        
        if not is_valid:
            print("❌ Data validation failed, cannot proceed")
            return
        
        # Generate forecast
        print("🔮 Generating Prophet forecast...")
        result = service.generate_forecast(
            data=sample_data,
            method='prophet',
            date_column='date',
            target_column='sales',
            forecast_period=7,
            parameters={'growth': 'linear', 'seasonality_mode': 'additive'}
        )
        
        print("✅ Forecast generated successfully!")
        print(f"📊 Forecast contains {len(result['forecast'])} predictions")
        print(f"📅 Date range: {result['dates'][0]} to {result['dates'][-1]}")
        print(f"📈 Metrics: {json.dumps(result['metrics'], indent=2)}")
        
        # Test MongoDB saving
        print("\n💾 Testing MongoDB saving...")
        
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        print(f"👤 Using user: {user.username} (created: {created})")
        
        # Create MongoDB document
        forecast_doc = ForecastDocument(
            user_id=user.id,
            username=user.username,
            name='Test Forecast',
            method='prophet',
            date_column='date',
            target_column='sales',
            forecast_period=7,
            parameters={'growth': 'linear', 'seasonality_mode': 'additive'},
            historical_data=sample_data,
            forecast_data=result['forecast'],
            forecast_dates=result['dates'],
            metrics={
                'rmse': float(result['metrics'].get('rmse', 0)),
                'mae': float(result['metrics'].get('mae', 0)),
                'r2': float(result['metrics'].get('r2', 0)),
                'mape': float(result['metrics'].get('mape', 0)),
                'mse': float(result['metrics'].get('mse', 0))
            },
            confidence_intervals={
                'lower': result['confidence_intervals']['lower'],
                'upper': result['confidence_intervals']['upper']
            } if result.get('confidence_intervals') else None,
            status='completed'
        )
        
        forecast_doc.save()
        print(f"✅ Saved to MongoDB with ID: {forecast_doc.forecast_id}")
        
        # Verify saving
        count = ForecastDocument.objects(user_id=user.id).count()
        print(f"📊 Total forecasts for user: {count}")
        
        # Test retrieval
        saved_forecast = ForecastDocument.objects(forecast_id=forecast_doc.forecast_id).first()
        if saved_forecast:
            print("✅ Successfully retrieved saved forecast")
            print(f"📊 Retrieved forecast has {len(saved_forecast.forecast_data)} predictions")
        else:
            print("❌ Failed to retrieve saved forecast")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_forecast_generation() 