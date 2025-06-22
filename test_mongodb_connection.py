#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

try:
    from forecasting.mongodb_models import ForecastDocument
    import mongoengine
    
    print("✅ Django setup successful")
    print("✅ MongoDB models imported successfully")
    
    # Test MongoDB connection
    try:
        # Try to query the collection (this will test the connection)
        count = ForecastDocument.objects.count()
        print(f"✅ MongoDB connection successful - Found {count} forecasts")
        
        # Test creating a sample document
        test_doc = ForecastDocument(
            user_id=1,
            username="test_user",
            name="Test Forecast",
            method="arima",
            date_column="Date",
            target_column="Sales",
            forecast_period=30,
            forecast_data=[1, 2, 3],
            forecast_dates=["2023-01-01", "2023-01-02", "2023-01-03"],
            status="completed"
        )
        
        # Don't save, just validate
        test_doc.validate()
        print("✅ Document validation successful")
        
    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Setup error: {e}") 