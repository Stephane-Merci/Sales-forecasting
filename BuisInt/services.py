import pandas as pd
import numpy as np
import io
from typing import List, Dict, Any, Optional
import json
import re
from datetime import datetime

class DataProcessingService:
    def __init__(self):
        self.data = None
        self.column_types = {}

    def check_date_format(self, value: str) -> tuple[bool, str]:
        """
        Check if a string matches common date formats.
        Returns (is_date, format_found)
        """
        # Strip any leading/trailing whitespace
        value = value.strip()
        
        # Common date formats to check
        date_formats = [
            # DD/MM/YYYY
            (r'^\d{2}/\d{2}/\d{4}$', '%d/%m/%Y'),
            # YYYY/MM/DD
            (r'^\d{4}/\d{2}/\d{2}$', '%Y/%m/%d'),
            # DD-MM-YYYY
            (r'^\d{2}-\d{2}-\d{4}$', '%d-%m-%Y'),
            # YYYY-MM-DD
            (r'^\d{4}-\d{2}-\d{2}$', '%Y-%m-%d'),
            # DD.MM.YYYY
            (r'^\d{2}\.\d{2}\.\d{4}$', '%d.%m.%Y'),
            # MM/DD/YYYY
            (r'^\d{2}/\d{2}/\d{4}$', '%m/%d/%Y'),
            # Short year formats
            (r'^\d{2}/\d{2}/\d{2}$', '%d/%m/%y'),
            (r'^\d{2}-\d{2}-\d{2}$', '%d-%m-%y'),
        ]
        
        for pattern, date_format in date_formats:
            if re.match(pattern, value):
                try:
                    # Try to parse the date to validate it
                    datetime.strptime(value, date_format)
                    return True, date_format
                except ValueError:
                    # If parsing fails, continue to next format
                    continue
        
        return False, ""

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
                print(f"[DEBUG] Processing column: {column}")
                print(f"[DEBUG] First few values: {self.data[column].head()}")
                
                # Check if column is numeric - be more strict about this
                is_numeric = False
                try:
                    # Try to convert all non-null values to numeric
                    non_null_values = self.data[column].dropna()
                    if len(non_null_values) == 0:
                        print(f"[DEBUG] {column} is empty, marking as categorical")
                        self.column_types[column] = 'categorical'
                        continue
                    
                    # Check if we can convert all values to numeric
                    numeric_converted = pd.to_numeric(non_null_values, errors='coerce')
                    numeric_success_rate = numeric_converted.notna().sum() / len(non_null_values)
                    
                    # Only consider it numeric if 95% or more values can be converted
                    if numeric_success_rate >= 0.95:
                        print(f"[DEBUG] {column} detected as numeric (success rate: {numeric_success_rate:.2%})")
                        self.column_types[column] = 'numeric'
                        is_numeric = True
                    else:
                        print(f"[DEBUG] {column} has mixed types (numeric success rate: {numeric_success_rate:.2%}), marking as categorical")
                        # Show some examples of non-numeric values
                        non_numeric_mask = numeric_converted.isna()
                        if non_numeric_mask.any():
                            non_numeric_examples = non_null_values[non_numeric_mask].head(3).tolist()
                            print(f"[DEBUG] Non-numeric examples in {column}: {non_numeric_examples}")
                        self.column_types[column] = 'categorical'
                except Exception as e:
                    print(f"[DEBUG] Error checking numeric type for {column}: {str(e)}")
                    self.column_types[column] = 'categorical'
                
                # If not numeric, check if it's a date column
                if not is_numeric:
                    # Try to detect if it's a date column using our custom function
                    sample_size = min(100, len(self.data))
                    date_matches = 0
                    non_null_samples = 0
                    detected_format = None
                    
                    # Sample non-null values
                    for value in self.data[column].dropna().head(sample_size):
                        if isinstance(value, str):
                            is_date, format_found = self.check_date_format(str(value))
                            if is_date:
                                date_matches += 1
                                if not detected_format:
                                    detected_format = format_found
                            non_null_samples += 1
                    
                    # If more than 90% of non-null samples match date format
                    if non_null_samples > 0 and (date_matches / non_null_samples) > 0.9:
                        print(f"[DEBUG] {column} detected as date with format {detected_format}")
                        try:
                            # Convert the column to datetime
                            self.data[column] = pd.to_datetime(self.data[column], format=detected_format)
                            # Convert to string format YYYY-MM-DD for consistency
                            self.data[column] = self.data[column].dt.strftime('%Y-%m-%d')
                            self.column_types[column] = 'date'
                        except Exception as e:
                            print(f"[DEBUG] Failed to convert {column} to datetime: {str(e)}")
                            self.column_types[column] = 'categorical'
                    else:
                        print(f"[DEBUG] {column} detected as categorical")
                        self.column_types[column] = 'categorical'

            print(f"[DEBUG] Final column types: {self.column_types}")

            return {
                'columns': list(self.data.columns),
                'column_types': self.column_types,
                'data': self.data.to_dict(orient='records'),  # Return full data
                'total_rows': len(self.data),
                'total_columns': len(self.data.columns)
            }
        except Exception as e:
            print(f"[DEBUG] Error in load_data: {str(e)}")
            raise ValueError(f"Error loading data: {str(e)}")

    def apply_filters(self, filters: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply filters to the data using pandas query operations
        """
        if self.data is None:
            raise ValueError("No data loaded")
        
        if not filters:
            return self.data.copy()

        filtered_data = self.data.copy()
        print(f"[DEBUG] Initial data shape: {filtered_data.shape}")
        
        for filter_config in filters:
            try:
                column = filter_config.get('column')
                operator = filter_config.get('operator')
                value = filter_config.get('value')

                if not column or not operator or value is None or value == '':
                    continue

                print(f"[DEBUG] Applying filter: {column} {operator} {value}")
                
                # Handle different column types
                if self.column_types.get(column) == 'numeric':
                    # Convert column to numeric if it's not already
                    filtered_data[column] = pd.to_numeric(filtered_data[column], errors='coerce')
                    
                    if isinstance(value, dict) and operator == 'between':
                        try:
                            min_val = float(value['min'])
                            max_val = float(value['max'])
                            mask = (filtered_data[column] >= min_val) & (filtered_data[column] <= max_val)
                            filtered_data = filtered_data[mask]
                            print(f"[DEBUG] Applied between filter: {min_val} <= {column} <= {max_val}")
                            print(f"[DEBUG] Remaining rows: {len(filtered_data)}")
                        except (ValueError, KeyError) as e:
                            print(f"[ERROR] Invalid between values: {e}")
                            continue
                            
                    elif isinstance(value, list) and operator == 'in':
                        try:
                            numeric_values = [float(v) for v in value if v.strip()]
                            if numeric_values:
                                filtered_data = filtered_data[filtered_data[column].isin(numeric_values)]
                                print(f"[DEBUG] Applied in filter: {column} in {numeric_values}")
                                print(f"[DEBUG] Remaining rows: {len(filtered_data)}")
                        except ValueError as e:
                            print(f"[ERROR] Invalid numeric values in list: {e}")
                            continue
                            
                    else:
                        try:
                            numeric_value = float(value)
                            if operator == '==':
                                filtered_data = filtered_data[filtered_data[column] == numeric_value]
                            elif operator == '!=':
                                filtered_data = filtered_data[filtered_data[column] != numeric_value]
                            elif operator == '>':
                                filtered_data = filtered_data[filtered_data[column] > numeric_value]
                            elif operator == '<':
                                filtered_data = filtered_data[filtered_data[column] < numeric_value]
                            elif operator == '>=':
                                filtered_data = filtered_data[filtered_data[column] >= numeric_value]
                            elif operator == '<=':
                                filtered_data = filtered_data[filtered_data[column] <= numeric_value]
                            print(f"[DEBUG] Applied numeric filter: {column} {operator} {numeric_value}")
                            print(f"[DEBUG] Remaining rows: {len(filtered_data)}")
                        except ValueError as e:
                            print(f"[ERROR] Invalid numeric value: {e}")
                            continue
                
                elif self.column_types.get(column) == 'datetime':
                    try:
                        if isinstance(value, dict) and operator == 'between':
                            min_val = pd.to_datetime(value['min'])
                            max_val = pd.to_datetime(value['max'])
                            filtered_data = filtered_data[
                                (filtered_data[column] >= min_val) & 
                                (filtered_data[column] <= max_val)
                            ]
                        else:
                            value = pd.to_datetime(value)
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
                        print(f"[DEBUG] Applied datetime filter: {column} {operator} {value}")
                        print(f"[DEBUG] Remaining rows: {len(filtered_data)}")
                    except ValueError as e:
                        print(f"[ERROR] Invalid datetime value: {e}")
                        continue
                
                else:  # String/categorical
                    try:
                        if operator == 'contains':
                            filtered_data = filtered_data[
                                filtered_data[column].astype(str).str.contains(str(value), case=False, na=False)
                            ]
                        elif operator == 'starts_with':
                            filtered_data = filtered_data[
                                filtered_data[column].astype(str).str.startswith(str(value), na=False)
                            ]
                        elif operator == 'ends_with':
                            filtered_data = filtered_data[
                                filtered_data[column].astype(str).str.endswith(str(value), na=False)
                            ]
                        elif operator == 'in':
                            if isinstance(value, str):
                                value = [v.strip() for v in value.split(',') if v.strip()]
                            if value:
                                filtered_data = filtered_data[filtered_data[column].isin(value)]
                        else:
                            filtered_data = filtered_data[filtered_data[column] == value]
                        print(f"[DEBUG] Applied string filter: {column} {operator} {value}")
                        print(f"[DEBUG] Remaining rows: {len(filtered_data)}")
                    except Exception as e:
                        print(f"[ERROR] Error applying string filter: {e}")
                        continue

            except Exception as e:
                print(f"[ERROR] Error applying filter for column {column}: {str(e)}")
                continue

        print(f"[DEBUG] Final filtered data shape: {filtered_data.shape}")
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

    def get_data_for_visualization(self, x_axis, y_axis, category=None, filters=None, group_by_x_axis=False, aggregation_method='avg'):
        """
        Get data for visualization based on selected columns and filters.
        Returns data in format suitable for chart.js
        """
        print(f"[DEBUG] get_data_for_visualization called with: x_axis={x_axis}, y_axis={y_axis}, filters={filters}, group_by={group_by_x_axis}, agg_method={aggregation_method}")
        
        if self.data is None or len(self.data) == 0:
            raise ValueError("No data available for visualization")

        try:
            # Apply filters first
            df = self.apply_filters(filters) if filters else self.data.copy()
            print(f"[DEBUG] Data after applying filters:\n{df.head()}")
            print(f"[DEBUG] Filtered data shape: {df.shape}")
            
            if group_by_x_axis:
                print(f"[DEBUG] Grouping by X-axis: {x_axis} with aggregation method: {aggregation_method}")
                
                # Convert numeric columns to float to handle potential mixed types
                if self.column_types.get(y_axis) == 'numeric':
                    df[y_axis] = pd.to_numeric(df[y_axis], errors='coerce')
                
                # Define aggregation function based on method
                if aggregation_method == 'avg':
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].mean()
                elif aggregation_method == 'sum':
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].sum()
                elif aggregation_method == 'count':
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].count()
                elif aggregation_method == 'min':
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].min()
                elif aggregation_method == 'max':
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].max()
                else:
                    grouped = df.groupby(x_axis, as_index=False)[y_axis].mean()  # default to mean
                
                print(f"[DEBUG] Grouped data ({aggregation_method}):\n{grouped}")
                
                # Sort values for better visualization
                grouped = grouped.sort_values(by=x_axis)
                
                # Return grouped data for visualization
                result = {
                    'x': grouped[x_axis].tolist(),
                    'y': grouped[y_axis].tolist()
                }
                print(f"[DEBUG] Returning grouped data for visualization: {result}")
                return result
                
            else:  # If no grouping
                # Sort values for better visualization
                df = df.sort_values(by=x_axis)
                
                # Return raw data for visualization
                result = {
                    'x': df[x_axis].tolist(),
                    'y': df[y_axis].tolist()
                }
                print(f"[DEBUG] Returning raw data for visualization: {result}")
                return result
                
        except Exception as e:
            print(f"[ERROR] Error in get_data_for_visualization: {str(e)}")
            raise ValueError(f"Error preparing visualization data: {str(e)}") 