from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
import json

User = get_user_model()

class ForecastModel(models.Model):
    METHODS = [
        ('lstm', 'LSTM Neural Network'),
        ('arima', 'ARIMA'),
        ('prophet', 'Prophet')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    method = models.CharField(max_length=20, choices=METHODS)
    target_column = models.CharField(max_length=100)
    date_column = models.CharField(max_length=100)
    forecast_period = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(365)])
    parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.method} ({self.user.username})"

    class Meta:
        ordering = ['-created_at']

class ForecastResult(models.Model):
    model = models.ForeignKey(ForecastModel, on_delete=models.CASCADE, related_name='results')
    forecast_date = models.DateTimeField()
    historical_data = models.JSONField()  # Store historical data points
    forecast_data = models.JSONField()    # Store forecast data points
    metrics = models.JSONField()          # Store evaluation metrics
    confidence_intervals = models.JSONField(null=True)  # Store confidence intervals if applicable
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Forecast for {self.model.name} at {self.forecast_date}"

    class Meta:
        ordering = ['-forecast_date']

    def get_metrics_display(self):
        """Return formatted metrics for display"""
        metrics = {}
        for key, value in self.metrics.items():
            if isinstance(value, (int, float)):
                metrics[key] = round(value, 4)
            else:
                metrics[key] = value
        return metrics
