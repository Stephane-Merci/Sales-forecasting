from django.db import models
from django.contrib.auth import get_user_model

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
