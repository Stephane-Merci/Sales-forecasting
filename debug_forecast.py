#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Now we can import Django modules
from forecasting.services import ForecastingService
import pandas as pd

def test_column_detection():
    """Test the column type detection with sample data"""
    
    # Sample data that might cause the "Sports" error
    sample_data = [
        {'Date': '2023-01-01', 'Sales': 100, 'Category': 'Electronics', 'Region': 'North'},
        {'Date': '2023-01-02', 'Sales': 150, 'Category': 'Sports', 'Region': 'South'},
        {'Date': '2023-01-03', 'Sales': 200, 'Category': 'Electronics', 'Region': 'East'},
        {'Date': '2023-01-04', 'Sales': 120, 'Category': 'Sports', 'Region': 'West'},
        {'Date': '2023-01-05', 'Sales': 180, 'Category': 'Electronics', 'Region': 'North'},
    ]
    
    print("Testing with sample data:")
    print("Sample records:", sample_data[:2])
    
    # Test the forecasting service
    service = ForecastingService()
    
    # Test validation
    print("\n=== Testing Validation ===")
    
    # Test with Category column (should fail)
    print("\n1. Testing with 'Category' as target (should fail):")
    try:
        is_valid, message = service.validate_data(sample_data, 'Date', 'Category')
        print(f"Valid: {is_valid}, Message: {message}")
    except Exception as e:
        print(f"Exception during validation: {e}")
    
    # Test with Sales column (should pass)
    print("\n2. Testing with 'Sales' as target (should pass):")
    try:
        is_valid, message = service.validate_data(sample_data, 'Date', 'Sales')
        print(f"Valid: {is_valid}, Message: {message}")
    except Exception as e:
        print(f"Exception during validation: {e}")
    
    # Test prepare_data
    print("\n=== Testing Data Preparation ===")
    try:
        print("\n1. Testing prepare_data with 'Sales' column:")
        df = service.prepare_data(sample_data, 'Date', 'Sales')
        print(f"Prepared data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"Sample prepared data:\n{df.head()}")
    except Exception as e:
        print(f"Error in prepare_data: {e}")

if __name__ == "__main__":
    test_column_detection() 