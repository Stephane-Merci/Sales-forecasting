from mongoengine import Document, EmbeddedDocument, fields
from datetime import datetime
import uuid

class ForecastMetrics(EmbeddedDocument):
    """Embedded document for forecast metrics"""
    rmse = fields.FloatField()
    mae = fields.FloatField()
    r2 = fields.FloatField()
    mape = fields.FloatField()
    mse = fields.FloatField(default=0.0)

class ConfidenceInterval(EmbeddedDocument):
    """Embedded document for confidence intervals"""
    lower = fields.ListField(fields.FloatField())
    upper = fields.ListField(fields.FloatField())

class ForecastDocument(Document):
    """MongoDB document for storing forecasts"""
    
    # Unique identifier
    forecast_id = fields.StringField(required=True, unique=True, default=lambda: str(uuid.uuid4()))
    
    # User information
    user_id = fields.IntField(required=True)  # Django user ID
    username = fields.StringField(required=True)
    
    # Model information
    name = fields.StringField(required=True, max_length=200)
    method = fields.StringField(required=True, choices=['lstm', 'arima', 'prophet'])
    
    # Data columns
    date_column = fields.StringField(required=True)
    target_column = fields.StringField(required=True)
    
    # Forecast settings
    forecast_period = fields.IntField(required=True, min_value=1, max_value=365)
    parameters = fields.DictField(default=dict)
    
    # Data
    historical_data = fields.ListField(fields.DictField())
    forecast_data = fields.ListField(fields.FloatField())
    forecast_dates = fields.ListField(fields.StringField())
    
    # Results
    metrics = fields.EmbeddedDocumentField(ForecastMetrics)
    confidence_intervals = fields.EmbeddedDocumentField(ConfidenceInterval)
    
    # Timestamps
    created_at = fields.DateTimeField(default=datetime.utcnow)
    updated_at = fields.DateTimeField(default=datetime.utcnow)
    
    # Metadata
    status = fields.StringField(default='completed', choices=['pending', 'completed', 'failed'])
    error_message = fields.StringField()
    
    meta = {
        'collection': 'forecasts',
        'indexes': [
            'user_id',
            'username',
            '-created_at',
            'method',
            'status'
        ]
    }
    
    def save(self, *args, **kwargs):
        """Override save to update timestamp"""
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def to_dict(self):
        """Convert document to dictionary for JSON serialization"""
        return {
            'id': str(self.forecast_id),
            'name': self.name,
            'method': self.method,
            'date_column': self.date_column,
            'target_column': self.target_column,
            'forecast_period': self.forecast_period,
            'parameters': self.parameters,
            'forecast_data': self.forecast_data,
            'forecast_dates': self.forecast_dates,
            'metrics': {
                'rmse': self.metrics.rmse if self.metrics else 0,
                'mae': self.metrics.mae if self.metrics else 0,
                'r2': self.metrics.r2 if self.metrics else 0,
                'mape': self.metrics.mape if self.metrics else 0,
                'mse': self.metrics.mse if self.metrics else 0,
            } if self.metrics else {},
            'confidence_intervals': {
                'lower': self.confidence_intervals.lower if self.confidence_intervals else [],
                'upper': self.confidence_intervals.upper if self.confidence_intervals else [],
            } if self.confidence_intervals else {},
            'created_at': self.created_at.isoformat(),
            'status': self.status
        }
    
    @classmethod
    def get_user_forecasts(cls, user_id, limit=None):
        """Get forecasts for a specific user"""
        query = cls.objects(user_id=user_id, status='completed').order_by('-created_at')
        if limit:
            query = query.limit(limit)
        return query
    
    @classmethod
    def get_user_statistics(cls, user_id):
        """Get overall statistics for a user"""
        forecasts = cls.objects(user_id=user_id, status='completed')
        
        if not forecasts:
            return {
                'total_forecasts': 0,
                'methods_used': {},
                'avg_forecast_period': 0,
                'most_recent': None,
                'best_model': None
            }
        
        methods_count = {}
        total_period = 0
        best_r2 = -1
        best_model = None
        
        for forecast in forecasts:
            # Count methods
            method = forecast.method
            methods_count[method] = methods_count.get(method, 0) + 1
            
            # Sum periods
            total_period += forecast.forecast_period
            
            # Find best model by R²
            if forecast.metrics and forecast.metrics.r2 and forecast.metrics.r2 > best_r2:
                best_r2 = forecast.metrics.r2
                best_model = {
                    'name': forecast.name,
                    'method': forecast.method,
                    'r2': forecast.metrics.r2,
                    'created_at': forecast.created_at.isoformat()
                }
        
        return {
            'total_forecasts': len(forecasts),
            'methods_used': methods_count,
            'avg_forecast_period': round(total_period / len(forecasts), 1) if forecasts else 0,
            'most_recent': forecasts.first().to_dict() if forecasts else None,
            'best_model': best_model
        } 