from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import ForecastModel, ForecastResult
from .services import ForecastingService
import json
from datetime import datetime
import pandas as pd

# Initialize forecasting service
forecasting_service = ForecastingService()

@login_required
def index(request):
    """Dashboard view for forecasting"""
    models = ForecastModel.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'forecasting/dashboard.html', {'models': models})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def generate_forecast(request):
    """API endpoint to generate forecasts"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['date_column', 'target_column', 'method', 'period']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JsonResponse({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)

        # Extract parameters
        date_column = data['date_column']
        target_column = data['target_column']
        method = data['method']
        period = int(data['period'])
        parameters = data.get('parameters', {})
        name = data.get('name', f'{target_column} forecast')
        
        # Get historical data from the request
        historical_data = data.get('historical_data', [])
        if not historical_data:
            return JsonResponse({
                'status': 'error',
                'message': 'No historical data provided'
            }, status=400)

        # Generate forecast
        result = forecasting_service.generate_forecast(
            data=historical_data,
            method=method,
            date_column=date_column,
            target_column=target_column,
            forecast_period=period,
            parameters=parameters
        )

        # Save the model and results
        forecast_model = ForecastModel.objects.create(
            user=request.user,
            name=name,
            method=method,
            target_column=target_column,
            date_column=date_column,
            forecast_period=period,
            parameters=parameters
        )

        # Create forecast result
        ForecastResult.objects.create(
            model=forecast_model,
            forecast_date=datetime.now(),
            historical_data=historical_data,
            forecast_data=result['forecast'],
            metrics=result['metrics'],
            confidence_intervals=result.get('confidence_intervals')
        )

        return JsonResponse({
            'status': 'success',
            'data': {
                'forecast': result['forecast'],
                'dates': result['dates'],
                'metrics': result['metrics'],
                'confidence_intervals': result.get('confidence_intervals'),
                'model_id': forecast_model.id
            }
        })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)

@login_required
def get_forecast_history(request, model_id):
    """Get historical forecasts for a specific model"""
    try:
        model = ForecastModel.objects.get(id=model_id, user=request.user)
        results = model.results.all().order_by('-forecast_date')
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'model': {
                    'id': model.id,
                    'name': model.name,
                    'method': model.method,
                    'target_column': model.target_column,
                    'parameters': model.parameters
                },
                'results': [{
                    'id': result.id,
                    'forecast_date': result.forecast_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'metrics': result.get_metrics_display(),
                    'forecast_data': result.forecast_data
                } for result in results]
            }
        })
    except ForecastModel.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Forecast model not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def delete_forecast_model(request, model_id):
    """Delete a forecast model and its results"""
    try:
        model = ForecastModel.objects.get(id=model_id, user=request.user)
        model.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Forecast model deleted successfully'
        })
    except ForecastModel.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Forecast model not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
