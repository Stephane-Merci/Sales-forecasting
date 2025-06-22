import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from forecasting.mongodb_models import ForecastDocument

def check_forecasts():
    print("🔍 Checking all forecasts in MongoDB...")
    
    # Get all forecasts
    all_forecasts = list(ForecastDocument.objects())
    print(f"📊 Total forecasts in database: {len(all_forecasts)}")
    
    if all_forecasts:
        for i, forecast in enumerate(all_forecasts, 1):
            print(f"\n📋 Forecast {i}:")
            print(f"   ID: {forecast.forecast_id}")
            print(f"   User: {forecast.username} (ID: {forecast.user_id})")
            print(f"   Name: {forecast.name}")
            print(f"   Method: {forecast.method}")
            print(f"   Target: {forecast.target_column}")
            print(f"   Status: {forecast.status}")
            print(f"   Created: {forecast.created_at}")
            print(f"   Forecast data: {len(forecast.forecast_data)} points")
            print(f"   Metrics: RMSE={forecast.metrics.rmse:.4f}, R²={forecast.metrics.r2:.4f}")
    else:
        print("❌ No forecasts found in database")

if __name__ == "__main__":
    check_forecasts() 