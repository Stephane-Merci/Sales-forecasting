from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import ForecastModel, ForecastResult
from .mongodb_models import ForecastDocument, ForecastMetrics, ConfidenceInterval
from .services import ForecastingService
import json
from datetime import datetime
import pandas as pd
import numpy as np
import logging
from mongoengine.errors import DoesNotExist, ValidationError

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
                # Create metrics embedded document with proper error handling
                def safe_float_conversion(value, default=0.0):
                    """Safely convert a value to float, handling various data types"""
                    try:
                        if value is None:
                            logger.debug(f"Converting None value, using default: {default}")
                            return default
                        
                        # Handle basic numeric types
                        if isinstance(value, (int, float)):
                            if np.isnan(value) or np.isinf(value):
                                logger.warning(f"NaN or Inf value detected: {value}, using default: {default}")
                                return default
                            return float(value)
                        
                        # Handle string conversion
                        if isinstance(value, str):
                            try:
                                result = float(value)
                                if np.isnan(result) or np.isinf(result):
                                    logger.warning(f"String converted to NaN/Inf: {value}, using default: {default}")
                                    return default
                                return result
                            except (ValueError, TypeError):
                                logger.warning(f"Cannot convert string to float: {value}, using default: {default}")
                                return default
                        
                        # Handle numpy types
                        if hasattr(value, 'item'):  # numpy scalar
                            try:
                                result = float(value.item())
                                if np.isnan(result) or np.isinf(result):
                                    logger.warning(f"Numpy value is NaN/Inf: {value}, using default: {default}")
                                    return default
                                return result
                            except (ValueError, TypeError):
                                logger.warning(f"Cannot convert numpy value: {value}, using default: {default}")
                                return default
                        
                        # Handle dictionaries more thoroughly
                        if isinstance(value, dict):
                            logger.warning(f"Dict found in metrics: {value}")
                            # Try common keys
                            for key in ['value', 'mean', 'avg', 'result', 'score']:
                                if key in value:
                                    return safe_float_conversion(value[key], default)
                            # If single key-value pair, use the value
                            if len(value) == 1:
                                single_value = list(value.values())[0]
                                return safe_float_conversion(single_value, default)
                            logger.warning(f"Complex dict in metrics: {value}, using default: {default}")
                            return default
                        
                        # Handle arrays/lists
                        if isinstance(value, (list, tuple, np.ndarray)):
                            if len(value) == 0:
                                logger.warning(f"Empty array in metrics, using default: {default}")
                                return default
                            if len(value) == 1:
                                return safe_float_conversion(value[0], default)
                            # For arrays with multiple values, use mean
                            try:
                                numeric_values = [safe_float_conversion(v, 0.0) for v in value]
                                result = sum(numeric_values) / len(numeric_values)
                                logger.warning(f"Array converted to mean: {value} -> {result}")
                                return result
                            except:
                                logger.warning(f"Cannot process array: {value}, using default: {default}")
                                return default
                        
                        # Handle pandas Series or other objects with numeric conversion
                        if hasattr(value, '__float__'):
                            try:
                                result = float(value)
                                if np.isnan(result) or np.isinf(result):
                                    logger.warning(f"Object float conversion is NaN/Inf: {value}, using default: {default}")
                                    return default
                                return result
                            except:
                                pass
                        
                        logger.warning(f"Unexpected metric value type: {type(value)}, value: {value}, using default: {default}")
                        return default
                        
                    except Exception as e:
                        logger.error(f"Error converting metric value {value} (type: {type(value)}) to float: {e}")
                        return default

                logger.debug(f"Raw metrics from forecasting service: {result['metrics']}")
                
                # Log each metric individually for debugging
                raw_metrics = result['metrics']
                for metric_name, metric_value in raw_metrics.items():
                    logger.debug(f"Raw metric {metric_name}: value={metric_value}, type={type(metric_value)}")
                
                # Convert metrics with detailed logging
                converted_metrics = {}
                converted_metrics['rmse'] = safe_float_conversion(raw_metrics.get('rmse'))
                converted_metrics['mae'] = safe_float_conversion(raw_metrics.get('mae'))
                converted_metrics['r2'] = safe_float_conversion(raw_metrics.get('r2'))
                converted_metrics['mape'] = safe_float_conversion(raw_metrics.get('mape'))
                converted_metrics['mse'] = safe_float_conversion(raw_metrics.get('mse'))
                
                logger.debug(f"Converted metrics: {converted_metrics}")
                
                # Double-check all values are actually floats before creating MongoDB document
                final_metrics = {}
                for key, value in converted_metrics.items():
                    if isinstance(value, (int, float)) and not (np.isnan(value) or np.isinf(value)):
                        final_metrics[key] = float(value)
                    else:
                        logger.warning(f"Final metric {key} is not a valid float: {value} (type: {type(value)}), using 0.0")
                        final_metrics[key] = 0.0
                
                logger.debug(f"Final validated metrics: {final_metrics}")
                
                metrics_doc = ForecastMetrics(
                    rmse=final_metrics['rmse'],
                    mae=final_metrics['mae'],
                    r2=final_metrics['r2'],
                    mape=final_metrics['mape'],
                    mse=final_metrics['mse']
                )
                
                logger.debug(f"Processed metrics for MongoDB: rmse={metrics_doc.rmse}, mae={metrics_doc.mae}, r2={metrics_doc.r2}, mape={metrics_doc.mape}, mse={metrics_doc.mse}")
                
                # Create confidence intervals embedded document if available
                confidence_doc = None
                if result.get('confidence_intervals'):
                    try:
                        # Clean confidence interval data
                        lower_clean = []
                        upper_clean = []
                        
                        if 'lower' in result['confidence_intervals']:
                            for val in result['confidence_intervals']['lower']:
                                lower_clean.append(safe_float_conversion(val, 0.0))
                        
                        if 'upper' in result['confidence_intervals']:
                            for val in result['confidence_intervals']['upper']:
                                upper_clean.append(safe_float_conversion(val, 0.0))
                        
                        logger.debug(f"Cleaned confidence intervals: lower={len(lower_clean)}, upper={len(upper_clean)}")
                        
                        confidence_doc = ConfidenceInterval(
                            lower=lower_clean,
                            upper=upper_clean
                        )
                    except Exception as conf_e:
                        logger.warning(f"Error creating confidence intervals: {conf_e}")
                        confidence_doc = None
                
                # Ensure forecast_data is a list of floats
                forecast_data_clean = []
                if isinstance(result['forecast'], (list, tuple)):
                    for item in result['forecast']:
                        clean_value = safe_float_conversion(item, 0.0)
                        forecast_data_clean.append(clean_value)
                else:
                    forecast_data_clean = [safe_float_conversion(result['forecast'], 0.0)]
                
                logger.debug(f"Cleaned forecast_data: {len(forecast_data_clean)} values, first few: {forecast_data_clean[:3]}")
                
                # Ensure forecast_dates is a list of strings
                forecast_dates_clean = []
                if isinstance(result['dates'], (list, tuple)):
                    for date_item in result['dates']:
                        if isinstance(date_item, str):
                            forecast_dates_clean.append(date_item)
                        else:
                            forecast_dates_clean.append(str(date_item))
                else:
                    forecast_dates_clean = [str(result['dates'])]
                
                logger.debug(f"Cleaned forecast_dates: {len(forecast_dates_clean)} dates, first few: {forecast_dates_clean[:3]}")
                
                # Save to MongoDB
                forecast_doc = ForecastDocument(
                    user_id=request.user.id,
                    username=request.user.username,
                    name=name,
                    method=method,
                    date_column=date_column,
                    target_column=target_column,
                    forecast_period=period,
                    parameters=parameters,
                    historical_data=historical_data,
                    forecast_data=forecast_data_clean,
                    forecast_dates=forecast_dates_clean,
                    metrics=metrics_doc,
                    confidence_intervals=confidence_doc,
                    status='completed'
                )

                forecast_doc.save()
                logger.info(f"Saved forecast to MongoDB with ID: {forecast_doc.forecast_id}")

                return JsonResponse({
                    'status': 'success',
                    'data': {
                        'forecast': result['forecast'],
                        'dates': result['dates'],
                        'metrics': result['metrics'],
                        'confidence_intervals': result.get('confidence_intervals'),
                        'model_id': forecast_doc.forecast_id
                    }
                })

            except Exception as e:
                logger.error(f"Error saving forecast results to MongoDB: {str(e)}")
                logger.error(f"Problematic metrics data: {result.get('metrics', 'No metrics found')}")
                logger.error(f"Type of metrics: {type(result.get('metrics', 'N/A'))}")
                
                # Log individual metric values and types for debugging
                if 'metrics' in result and isinstance(result['metrics'], dict):
                    for key, value in result['metrics'].items():
                        logger.error(f"Metric {key}: value={value}, type={type(value)}")
                
                # Return error status to indicate saving failed
                return JsonResponse({
                    'status': 'error',
                    'message': f'Forecast generated but failed to save to database: {str(e)}',  
                    'data': {
                        'forecast': result['forecast'],
                        'dates': result['dates'],
                        'metrics': result['metrics'],
                        'confidence_intervals': result.get('confidence_intervals')
                    }
                }, status=500)

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

# New MongoDB-based endpoints

@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_user_forecasts(request):
    """Get forecasts for the current user with pagination support"""
    try:
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 5))
        
        # Calculate skip for pagination
        skip = (page - 1) * limit
        
        # Get total count for pagination info
        total_count = ForecastDocument.objects(user_id=request.user.id, status='completed').count()
        
        # Get paginated forecasts
        forecasts = ForecastDocument.objects(
            user_id=request.user.id, 
            status='completed'
        ).order_by('-created_at').skip(skip).limit(limit)
        
        forecasts_data = [forecast.to_dict() for forecast in forecasts]
        
        return JsonResponse({
            'status': 'success',
            'data': forecasts_data,
            'count': len(forecasts_data),
            'total_count': total_count,
            'page': page,
            'total_pages': (total_count + limit - 1) // limit,  # Ceiling division
            'has_next': skip + limit < total_count,
            'has_previous': page > 1
        })
    
    except ValueError as e:
        logger.error(f"Invalid pagination parameters: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid pagination parameters'
        }, status=400)
    except Exception as e:
        logger.error(f"Error fetching user forecasts: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error fetching forecasts: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_user_statistics(request):
    """Get overall statistics for the current user"""
    try:
        stats = ForecastDocument.get_user_statistics(request.user.id)
        
        return JsonResponse({
            'status': 'success',
            'data': stats
        })
    
    except Exception as e:
        logger.error(f"Error fetching user statistics: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error fetching statistics: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_forecast(request, forecast_id):
    """Delete a specific forecast"""
    try:
        # Find the forecast
        forecast = ForecastDocument.objects(
            forecast_id=forecast_id, 
            user_id=request.user.id
        ).first()
        
        if not forecast:
            return JsonResponse({
                'status': 'error',
                'message': 'Forecast not found or you do not have permission to delete it'
            }, status=404)
        
        # Delete the forecast
        forecast.delete()
        logger.info(f"Deleted forecast {forecast_id} for user {request.user.username}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Forecast deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error deleting forecast {forecast_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting forecast: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_forecast_details(request, forecast_id):
    """Get detailed information about a specific forecast"""
    try:
        # Find the forecast
        forecast = ForecastDocument.objects(
            forecast_id=forecast_id,
            user_id=request.user.id
        ).first()
        
        if not forecast:
            return JsonResponse({
                'status': 'error',
                'message': 'Forecast not found or you do not have permission to access it'
            }, status=404)
        
        return JsonResponse({
            'status': 'success',
            'data': forecast.to_dict()
        })
    
    except Exception as e:
        logger.error(f"Error fetching forecast details for {forecast_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error fetching forecast details: {str(e)}'
        }, status=500)
