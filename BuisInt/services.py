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
        if self.data is None:
            raise ValueError("No data loaded")

        # Apply filters if provided
        filtered_data = self.apply_filters(filters) if filters else self.data.copy()

        # Group data if category is provided
        if category:
            grouped_data = filtered_data.groupby(category)[y_axis].agg(['mean', 'count']).reset_index()
            return {
                'x': grouped_data[category].tolist(),
                'y': grouped_data['mean'].tolist(),
                'counts': grouped_data['count'].tolist()
            }
        else:
            return {
                'x': filtered_data[x_axis].tolist(),
                'y': filtered_data[y_axis].tolist()
            } 