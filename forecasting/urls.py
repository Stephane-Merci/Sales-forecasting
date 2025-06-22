from django.urls import path
from . import views

app_name = 'forecasting'
 
urlpatterns = [
    path('', views.index, name='index'),
    path('api/generate-forecast/', views.generate_forecast, name='generate_forecast'),
    path('api/forecast-history/<int:model_id>/', views.get_forecast_history, name='forecast_history'),
    path('api/delete-model/<int:model_id>/', views.delete_forecast_model, name='delete_model'),
    
    # New MongoDB-based endpoints
    path('api/user-forecasts/', views.get_user_forecasts, name='get_user_forecasts'),
    path('api/user-statistics/', views.get_user_statistics, name='get_user_statistics'),
    path('api/forecast-details/<str:forecast_id>/', views.get_forecast_details, name='get_forecast_details'),
    path('api/delete-forecast/<str:forecast_id>/', views.delete_forecast, name='delete_forecast'),
] 