from django.urls import path
from . import views

app_name = 'BuisInt'

urlpatterns = [
    path('dashboard/', views.dashboard, name='buisint_dashboard'),
    path('add-data/', views.add_data, name='buisint_add_data'),
    
    # API endpoints
    path('api/upload-data/', views.upload_data, name='api_upload_data'),
    path('api/column-stats/', views.get_column_stats, name='api_column_stats'),
    path('api/visualization-data/', views.get_visualization_data, name='api_visualization_data'),
    path('api/apply-filters/', views.apply_filters, name='api_apply_filters'),
    path('api/save-file/', views.save_file, name='api_save_file'),
    path('api/load-saved-file/', views.load_saved_file, name='api_load_saved_file'),
    path('api/get-saved-files/', views.get_saved_files, name='api_get_saved_files'),
] 