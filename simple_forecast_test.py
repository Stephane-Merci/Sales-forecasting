import os
import django
import sys

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def test_imports():
    print("🔍 Testing imports...")
    
    try:
        from forecasting.views import generate_forecast
        print("✅ generate_forecast view imported successfully")
    except Exception as e:
        print(f"❌ Error importing generate_forecast: {e}")
        return
    
    try:
        from forecasting.services import ForecastingService
        print("✅ ForecastingService imported successfully")
    except Exception as e:
        print(f"❌ Error importing ForecastingService: {e}")
        return
    
    try:
        from forecasting.mongodb_models import ForecastDocument
        print("✅ MongoDB models imported successfully")
    except Exception as e:
        print(f"❌ Error importing MongoDB models: {e}")
        return
    
    # Test service initialization
    try:
        service = ForecastingService()
        print("✅ ForecastingService initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing ForecastingService: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("🎉 All imports and initialization successful!")

if __name__ == "__main__":
    test_imports() 