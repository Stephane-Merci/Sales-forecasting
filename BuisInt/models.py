from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from mongoengine import Document, StringField, ReferenceField, DateTimeField, ListField, DictField, IntField
from datetime import datetime

User = get_user_model()

class BusinessData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='business_data')
    date = models.DateField()
    sales = models.DecimalField(max_digits=10, decimal_places=2)
    revenue = models.DecimalField(max_digits=10, decimal_places=2)
    expenses = models.DecimalField(max_digits=10, decimal_places=2)
    profit = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Business Data'
        verbose_name_plural = 'Business Data'

    def __str__(self):
        return f"{self.user.username}'s data for {self.date}"

    def save(self, *args, **kwargs):
        # Calculate profit if not set
        if not self.profit:
            self.profit = self.revenue - self.expenses
        super().save(*args, **kwargs)

class UserFile(Document):
    user_id = IntField(required=True)  # Store Django user ID instead of reference
    username = StringField(required=True)  # Store username for display purposes
    filename = StringField(required=True)
    file_content = StringField(required=True)  # Store CSV content as string
    column_types = DictField()  # Store column types
    upload_date = DateTimeField(default=datetime.utcnow)
    description = StringField(max_length=500)
    
    meta = {
        'collection': 'user_files',
        'indexes': [
            'user_id',
            'filename',
            'upload_date'
        ]
    }
