from django.contrib import admin
from .models import BusinessData

@admin.register(BusinessData)
class BusinessDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'sales', 'revenue', 'expenses', 'profit')
    list_filter = ('date', 'user')
    search_fields = ('user__username', 'user__email')
    date_hierarchy = 'date'
    ordering = ('-date',)
