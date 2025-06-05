import pandas as pd
import numpy as np
import io
from typing import List, Dict, Any, Optional
import json

class DataProcessingService:
    def __init__(self):
        self.data = None
        self.column_types = {}

    def load_data(self, file_content: str) -> Dict[str, Any]:
        """
        Load data from CSV content and determine column types
        """
        try:
            # Read CSV content
            self.data = pd.read_csv(io.StringIO(file_content))
            
            # Determine column types
            self.column_types = {}
            for column in self.data.columns:
                # Check if column is numeric
                if pd.api.types.is_numeric_dtype(self.data[column]):
                    self.column_types[column] = 'numeric'
                # Check if column is datetime
                elif pd.api.types.is_datetime64_any_dtype(self.data[column]):
                    self.column_types[column] = 'datetime'
                # Default to string/categorical
                else:
                    self.column_types[column] = 'categorical'

            print(f"[DEBUG] Inferred column types: {self.column_types}")

            return {
                'columns': list(self.data.columns),
                'column_types': self.column_types,
                'row_count': len(self.data),
                'preview': self.data.head(5).to_dict(orient='records')
            }
        except Exception as e:
            raise ValueError(f"Error loading data: {str(e)}")

    def apply_filters(self, filters: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply filters to the data
        """
        if self.data is None:
            raise ValueError("No data loaded")

        filtered_data = self.data.copy()

        for filter_config in filters:
            column = filter_config['column']
            operator = filter_config['operator']
            value = filter_config['value']

            if not column or not operator:
                continue

            # Convert value to appropriate type based on column type
            if self.column_types.get(column) == 'numeric':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue
            elif self.column_types.get(column) == 'datetime':
                try:
                    value = pd.to_datetime(value)
                except (ValueError, TypeError):
                    continue

            # Apply filter based on operator
            if operator == '==':
                filtered_data = filtered_data[filtered_data[column] == value]
            elif operator == '!=':
                filtered_data = filtered_data[filtered_data[column] != value]
            elif operator == '>':
                filtered_data = filtered_data[filtered_data[column] > value]
            elif operator == '<':
                filtered_data = filtered_data[filtered_data[column] < value]
            elif operator == '>=':
                filtered_data = filtered_data[filtered_data[column] >= value]
            elif operator == '<=':
                filtered_data = filtered_data[filtered_data[column] <= value]
            elif operator == 'contains':
                filtered_data = filtered_data[filtered_data[column].astype(str).str.contains(str(value), case=False)]

        return filtered_data

    def get_column_statistics(self, column: str) -> Dict[str, Any]:
        """
        Get statistics for a specific column
        """
        if self.data is None:
            raise ValueError("No data loaded")

        if column not in self.data.columns:
            raise ValueError(f"Column {column} not found")

        stats = {}
        col_data = self.data[column]

        if self.column_types[column] == 'numeric':
            stats.update({
                'min': float(col_data.min()),
                'max': float(col_data.max()),
                'mean': float(col_data.mean()),
                'median': float(col_data.median()),
                'std': float(col_data.std()),
                'unique_values': int(col_data.nunique())
            })
        elif self.column_types[column] == 'datetime':
            stats.update({
                'min': col_data.min().isoformat(),
                'max': col_data.max().isoformat(),
                'unique_values': int(col_data.nunique())
            })
        else:  # categorical
            value_counts = col_data.value_counts().head(10).to_dict()
            stats.update({
                'unique_values': int(col_data.nunique()),
                'top_values': value_counts
            })

        return stats

    def get_data_for_visualization(self, 
                                 x_axis: str, 
                                 y_axis: str, 
                                 category: Optional[str] = None,
                                 filters: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Prepare data for visualization based on selected columns and filters
        """
        print(f"[DEBUG] get_data_for_visualization called with: x_axis={x_axis}, y_axis={y_axis}, category={category}, filters={filters}")

        if self.data is None:
            print("[DEBUG] No data loaded in get_data_for_visualization.")
            raise ValueError("No data loaded")

        # Apply filters if provided
        filtered_data = self.apply_filters(filters) if filters else self.data.copy()
        print(f"[DEBUG] Data after applying filters:\n{filtered_data.head()}")
        print(f"[DEBUG] Filtered data shape: {filtered_data.shape}")

        # --- Simplified data preparation for X and Y axes only ---
        # Ensure selected columns exist after filtering
        if x_axis not in filtered_data.columns or y_axis not in filtered_data.columns:
             print(f"[DEBUG] X-axis ('{x_axis}') or Y-axis ('{y_axis}') column not found in filtered data.")
             raise ValueError("Selected X or Y axis column not found after filtering.")

        # Return data as lists for Chart.js
        result = {
            'x': filtered_data[x_axis].tolist(),
            'y': filtered_data[y_axis].tolist()
        }
        print(f"[DEBUG] Returning data for visualization: {result}")
        return result 