from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import BusinessData, UserFile
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .services import DataProcessingService
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

# Create a singleton instance of the data processing service
data_service = DataProcessingService()

# Create your views here.

@login_required
def dashboard(request):
    # Get data for the last 30 days
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    business_data = BusinessData.objects.filter(
        user=request.user,
        date__gte=thirty_days_ago
    ).order_by('date')

    # Calculate summary statistics
    total_sales = business_data.aggregate(Sum('sales'))['sales__sum'] or 0
    total_revenue = business_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
    total_expenses = business_data.aggregate(Sum('expenses'))['expenses__sum'] or 0
    total_profit = business_data.aggregate(Sum('profit'))['profit__sum'] or 0
    avg_profit = business_data.aggregate(Avg('profit'))['profit__avg'] or 0

    context = {
        'business_data': business_data,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
    }
    return render(request, 'BuisInt/dashboard.html', context)

@login_required
def add_data(request):
    # Get user's saved files
    saved_files = UserFile.objects.filter(user_id=request.user.id).order_by('-upload_date')
    context = {
        'saved_files': saved_files
    }
    return render(request, 'BuisInt/add_data.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def upload_data(request):
    """Handle CSV file upload and initial data processing"""
    try:
        file_content = request.FILES['file'].read().decode('utf-8')
        result = data_service.load_data(file_content)
        return JsonResponse({
            'status': 'success',
            'data': result
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def get_column_stats(request):
    """Get statistics for a specific column"""
    try:
        data = json.loads(request.body)
        column = data.get('column')
        if not column:
            raise ValueError("Column name is required")

        stats = data_service.get_column_statistics(column)
        return JsonResponse({
            'status': 'success',
            'data': stats
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def get_visualization_data(request):
    """
    API endpoint to get data for visualization based on selected columns and filters.
    """
    try:
        data = json.loads(request.body)
        x_axis = data.get('x_axis')
        y_axis = data.get('y_axis')
        group_by_x_axis = data.get('group_by_x_axis', False)
        aggregation_method = data.get('aggregation_method', 'avg')
        filters = data.get('filters', [])

        print(f"[DEBUG] Received request for visualization data:")
        print(f"X-axis: {x_axis}")
        print(f"Y-axis: {y_axis}")
        print(f"Group by: {group_by_x_axis}")
        print(f"Aggregation: {aggregation_method}")
        print(f"Filters: {filters}")

        if not x_axis or not y_axis:
            return JsonResponse({
                'status': 'error',
                'message': 'X-axis and Y-axis columns are required.'
            }, status=400)

        try:
            # Get visualization data with filters and grouping
            visualization_data = data_service.get_data_for_visualization(
                x_axis=x_axis,
                y_axis=y_axis,
                filters=filters,
                group_by_x_axis=group_by_x_axis,
                aggregation_method=aggregation_method
            )
            
            # Get a preview of the filtered data
            filtered_data = data_service.apply_filters(filters)
            preview_data = filtered_data.head(5).to_dict(orient='records')
            
            print(f"[DEBUG] Visualization data prepared:")
            print(f"Data points: {len(visualization_data['x'])}")
            print(f"Preview rows: {len(preview_data)}")
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    **visualization_data,
                    'preview': preview_data,
                    'total_rows': len(filtered_data)
                }
            })

        except ValueError as e:
            print(f"[ERROR] Error in get_data_for_visualization: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred in get_visualization_data: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'An unexpected server error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def apply_filters(request):
    """Apply filters to the data and return filtered results"""
    try:
        data = json.loads(request.body)
        filters = data.get('filters', [])
        
        filtered_data = data_service.apply_filters(filters)
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'row_count': len(filtered_data),
                'preview': filtered_data.head(5).to_dict(orient='records')
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def save_file(request):
    """Save the current data to MongoDB"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': 'User must be authenticated'
            }, status=401)

        data = json.loads(request.body)
        filename = data.get('filename')
        description = data.get('description', '')

        if not filename:
            return JsonResponse({
                'status': 'error',
                'message': 'Filename is required'
            }, status=400)

        # Get current data from the service
        if data_service.data is None:
            return JsonResponse({
                'status': 'error',
                'message': 'No data to save'
            }, status=400)

        # Convert DataFrame to CSV string
        csv_content = data_service.data.to_csv(index=False)
        
        # Create new UserFile document
        user_file = UserFile(
            user_id=request.user.id,
            username=request.user.username,
            filename=filename,
            file_content=csv_content,
            column_types=data_service.column_types,
            description=description
        )
        user_file.save()

        return JsonResponse({
            'status': 'success',
            'message': 'File saved successfully',
            'file_id': str(user_file.id)
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def load_saved_file(request):
    """Load a saved file from MongoDB"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': 'User must be authenticated'
            }, status=401)

        data = json.loads(request.body)
        file_id = data.get('file_id')

        if not file_id:
            return JsonResponse({
                'status': 'error',
                'message': 'File ID is required'
            }, status=400)
            
        # Get the file from MongoDB
        user_file = UserFile.objects.get(id=file_id, user_id=request.user.id)
        
        # Convert the saved data back to CSV format
        csv_content = user_file.file_content
        
        print(f"Loading file: {user_file.filename}")  # Debug log
        print(f"CSV content length: {len(csv_content)}")  # Debug log
        
        # Process the CSV data as if it was newly uploaded
        result = data_service.load_data(csv_content)
        
        print(f"Load data result: {result}")  # Debug log
        
        if not result:
            return JsonResponse({
                'status': 'error',
                'message': 'No data returned from load_data'
            }, status=500)
            
        # Ensure we have the required data structure
        if not isinstance(result, dict):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid data format from load_data'
            }, status=500)
            
        # Get column statistics for each column
        column_stats = {}
        columns = result.get('columns', [])
        
        print(f"Processing columns: {columns}")  # Debug log
        
        for column in columns:
            try:
                stats = data_service.get_column_statistics(column)
                column_stats[column] = stats
            except Exception as e:
                print(f"Error getting statistics for column {column}: {str(e)}")
                column_stats[column] = None
        
        # Prepare the response data
        response_data = {
            'data': result.get('data', []),
            'columns': columns,
            'column_types': result.get('column_types', {}),
            'column_stats': column_stats,
            'total_rows': result.get('total_rows', 0),
            'total_columns': result.get('total_columns', 0)
        }
        
        print(f"Response data prepared: {response_data}")  # Debug log
        
        return JsonResponse({
            'status': 'success',
            'data': response_data
        })
        
    except UserFile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'File not found'
        }, status=404)
    except Exception as e:
        print(f"Error in load_saved_file: {str(e)}")  # Debug log
        import traceback
        print(traceback.format_exc())  # Print full traceback
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_saved_files(request):
    """Get list of user's saved files"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': 'User must be authenticated'
            }, status=401)

        files = UserFile.objects.filter(user_id=request.user.id).order_by('-upload_date')
        files_list = [{
            'id': str(f.id),
            'filename': f.filename,
            'description': f.description,
            'upload_date': f.upload_date.isoformat(),
            'column_types': f.column_types
        } for f in files]

        return JsonResponse({
            'status': 'success',
            'data': files_list
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def delete_saved_file(request):
    """Delete a saved file from MongoDB"""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': 'User must be authenticated'
            }, status=401)

        data = json.loads(request.body)
        file_id = data.get('file_id')

        if not file_id:
            return JsonResponse({
                'status': 'error',
                'message': 'File ID is required'
            }, status=400)
            
        # Get and delete the file
        user_file = UserFile.objects.get(id=file_id, user_id=request.user.id)
        filename = user_file.filename  # Store filename before deletion
        user_file.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'File "{filename}" deleted successfully'
        })
        
    except UserFile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'File not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
