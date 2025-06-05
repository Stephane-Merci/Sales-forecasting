from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import BusinessData
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .services import DataProcessingService
from django.core.cache import cache

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
    if request.method == 'POST':
        try:
            data = BusinessData(
                user=request.user,
                date=request.POST.get('date'),
                sales=request.POST.get('sales'),
                revenue=request.POST.get('revenue'),
                expenses=request.POST.get('expenses'),
            )
            data.save()
            messages.success(request, 'Business data added successfully!')
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f'Error adding data: {str(e)}')
    
    return render(request, 'BuisInt/add_data.html')

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
    """Get processed data for visualization"""
    try:
        data = json.loads(request.body)
        x_axis = data.get('x_axis')
        y_axis = data.get('y_axis')
        category = data.get('category')
        filters = data.get('filters', [])

        if not x_axis or not y_axis:
            raise ValueError("X-axis and Y-axis are required")

        viz_data = data_service.get_data_for_visualization(
            x_axis=x_axis,
            y_axis=y_axis,
            category=category,
            filters=filters
        )

        return JsonResponse({
            'status': 'success',
            'data': viz_data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

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
