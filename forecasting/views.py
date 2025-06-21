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
import logging

# Initialize forecasting service
forecasting_service = ForecastingService()

# Initialize logger
logger = logging.getLogger(__name__)

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
        # Log request information
        logger.info(f"Received forecast request from user: {request.user.username}")
        
        try:
            data = json.loads(request.body)
            logger.debug(f"Request data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid JSON in request body: {str(e)}'
            }, status=400)
        
        # Log the received data structure
        logger.debug("Request data structure:")
        for key, value in data.items():
            if key == 'historical_data':
                logger.debug(f"historical_data: {len(value)} records")
                if value:
                    logger.debug(f"Sample record: {value[0]}")
                    logger.debug(f"Available columns: {list(value[0].keys())}")
            else:
                logger.debug(f"{key}: {value}")
        
        # Validate required fields
        required_fields = ['date_column', 'target_column', 'method', 'period']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
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
            logger.warning("No historical data provided")
            return JsonResponse({
                'status': 'error',
                'message': 'No historical data provided'
            }, status=400)

        # Validate data structure
        if not all(isinstance(record, dict) for record in historical_data):
            logger.error("Invalid data structure: historical_data must be a list of dictionaries")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid data structure: historical_data must be a list of dictionaries'
            }, status=400)

        # Check if required columns exist in the data
        sample_record = historical_data[0]
        if date_column not in sample_record:
            logger.error(f"Date column '{date_column}' not found in data")
            return JsonResponse({
                'status': 'error',
                'message': f"Date column '{date_column}' not found in data"
            }, status=400)
        if target_column not in sample_record:
            logger.error(f"Target column '{target_column}' not found in data")
            return JsonResponse({
                'status': 'error',
                'message': f"Target column '{target_column}' not found in data"
            }, status=400)
        
        # Debug: Log sample values from target column
        logger.info(f"Sample values from target column '{target_column}':")
        target_values = [record.get(target_column) for record in historical_data[:10]]
        logger.info(f"First 10 values: {target_values}")
        
        # Check for non-numeric values in target column
        non_numeric_values = []
        for i, record in enumerate(historical_data[:20]):  # Check first 20 records
            value = record.get(target_column)
            if value is not None:
                try:
                    float(value)
                except (ValueError, TypeError):
                    non_numeric_values.append(f"Row {i}: '{value}' (type: {type(value).__name__})")
        
        if non_numeric_values:
            logger.error(f"Non-numeric values found in target column '{target_column}': {non_numeric_values}")
            return JsonResponse({
                'status': 'error',
                'message': f"Target column '{target_column}' contains non-numeric values: {non_numeric_values[:3]}. Please select a numeric column for forecasting."
            }, status=400)

        logger.info(f"Generating {method} forecast for {target_column} with {len(historical_data)} data points")

        try:
            # Generate forecast
            result = forecasting_service.generate_forecast(
                data=historical_data,
                method=method,
                date_column=date_column,
                target_column=target_column,
                forecast_period=period,
                parameters=parameters
            )

            logger.info("Forecast generated successfully")

            try:
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

                logger.info(f"Saved forecast model with ID: {forecast_model.id}")

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

            except Exception as e:
                logger.error(f"Error saving forecast results: {str(e)}")
                # If saving fails, still return the forecast results
                return JsonResponse({
                    'status': 'success',
                    'data': {
                        'forecast': result['forecast'],
                        'dates': result['dates'],
                        'metrics': result['metrics'],
                        'confidence_intervals': result.get('confidence_intervals')
                    }
                })

        except ValueError as e:
            logger.error(f"Value error in forecast generation: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            logger.error(f"Error in forecast generation: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Error generating forecast: {str(e)}'
            }, status=500)

    except Exception as e:
        logger.error(f"Unexpected error in generate_forecast view: {str(e)}", exc_info=True)
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
