from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

# Create your views here.

def index(request):
    """Basic view for testing the forecasting app setup"""
    return JsonResponse({
        'status': 'success',
        'message': 'Forecasting app is working'
    })

@csrf_exempt
@require_http_methods(["POST"])
def generate_forecast(request):
    """API endpoint to generate forecasts"""
    try:
        data = json.loads(request.body)
        target_column = data.get('target_column')
        
        if not target_column:
            return JsonResponse({
                'status': 'error',
                'message': 'Target column is required.'
            }, status=400)
            
        # TODO: Implement actual forecasting logic
        return JsonResponse({
            'status': 'success',
            'message': f'Forecast requested for column: {target_column}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)
