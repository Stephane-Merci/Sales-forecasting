from django.urls import path
from . import views

app_name = 'forecasting'
 
urlpatterns = [
    path('api/generate-forecast/', views.generate_forecast, name='generate_forecast'),
] 