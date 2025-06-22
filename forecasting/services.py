import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
import tensorflow as tf
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet
import logging
from typing import Dict, List, Any, Tuple, Optional
import json

logger = logging.getLogger(__name__)

class ForecastingService:
    def __init__(self):
        self.scaler = MinMaxScaler()
        
    def validate_data(self, data: List[Dict], date_column: str, target_column: str) -> Tuple[bool, str]:
        """Validate input data for forecasting"""
        try:
            # Check if data is empty
            if not data:
                return False, "No data provided"

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Check required columns
            if date_column not in df.columns:
                return False, f"Date column '{date_column}' not found in data"
            if target_column not in df.columns:
                return False, f"Target column '{target_column}' not found in data"

            # Check date column
            try:
                df[date_column] = pd.to_datetime(df[date_column])
            except Exception as e:
                return False, f"Invalid date format in column '{date_column}': {str(e)}"

            # Check target column - must be numeric for forecasting
            try:
                # First check if the column contains any non-numeric values
                sample_values = df[target_column].dropna().head(10).tolist()
                non_numeric_values = []
                for value in sample_values:
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        non_numeric_values.append(str(value))
                
                if non_numeric_values:
                    return False, f"Target column '{target_column}' contains non-numeric values: {non_numeric_values[:3]}. Please select a numeric column for forecasting."
                
                # Try to convert the entire column
                df[target_column] = pd.to_numeric(df[target_column], errors='raise')
                
            except Exception as e:
                return False, f"Target column '{target_column}' must contain only numeric values for forecasting. Found non-numeric data: {str(e)}"

            # Check for missing values
            if df[date_column].isnull().any():
                return False, f"Missing values found in date column '{date_column}'"
            if df[target_column].isnull().any():
                return False, f"Missing values found in target column '{target_column}'"

            # Check for duplicate dates
            if df[date_column].duplicated().any():
                return False, f"Duplicate dates found in column '{date_column}'"

            # Check minimum data points
            if len(df) < 30:  # Arbitrary minimum, adjust as needed
                return False, "Insufficient data points (minimum 30 required)"

            return True, "Data validation successful"

        except Exception as e:
            logger.error(f"Error in data validation: {str(e)}")
            return False, f"Error validating data: {str(e)}"

    def prepare_data(self, data: List[Dict], date_column: str, target_column: str) -> pd.DataFrame:
        """Prepare data for forecasting with enhanced preprocessing"""
        try:
            df = pd.DataFrame(data)
            
            # Ensure date column is properly formatted
            try:
                # First try parsing as is
                df[date_column] = pd.to_datetime(df[date_column])
            except Exception as e:
                logger.error(f"Error parsing dates: {str(e)}")
                # If that fails, try common formats
                for format in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m/%d/%Y']:
                    try:
                        df[date_column] = pd.to_datetime(df[date_column], format=format)
                        break
                    except:
                        continue
                
                if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
                    raise ValueError(f"Unable to parse dates in column {date_column}")

            # Sort by date
            df = df.sort_values(date_column)
            
            # Ensure target column is numeric - be strict about this
            try:
                # Log original data types for debugging
                logger.info(f"Target column '{target_column}' original dtype: {df[target_column].dtype}")
                logger.info(f"Sample values: {df[target_column].head().tolist()}")
                
                # First check for non-numeric values
                original_values = df[target_column].copy()
                numeric_converted = pd.to_numeric(df[target_column], errors='coerce')
                non_numeric_mask = numeric_converted.isna()
                
                if non_numeric_mask.any():
                    non_numeric_values = original_values.loc[non_numeric_mask].unique()[:5]
                    logger.error(f"Found non-numeric values in target column '{target_column}': {list(non_numeric_values)}")
                    
                    # Try to clean the data by removing non-numeric rows
                    logger.warning(f"Removing {non_numeric_mask.sum()} rows with non-numeric values")
                    df = df[~non_numeric_mask].copy()
                    
                    if len(df) == 0:
                        raise ValueError(f"All rows in target column '{target_column}' contain non-numeric values")
                    
                    # Re-convert after cleaning
                    df[target_column] = pd.to_numeric(df[target_column], errors='coerce')
                else:
                    df[target_column] = numeric_converted
                    
                # Final check for successful conversion
                if df[target_column].isna().all():
                    raise ValueError(f"Could not convert any values in target column '{target_column}' to numeric")
                    
                logger.info(f"Successfully converted target column to numeric. Final dtype: {df[target_column].dtype}")
                
            except Exception as e:
                logger.error(f"Error in target column conversion: {str(e)}")
                raise ValueError(f"Cannot convert target column '{target_column}' to numeric: {str(e)}")
            
            # Remove any rows with NaN values
            df = df.dropna(subset=[date_column, target_column])
            
            # Ensure data is complete and continuous
            date_range = pd.date_range(start=df[date_column].min(), end=df[date_column].max(), freq='D')
            df = df.set_index(date_column).reindex(date_range).reset_index()
            df = df.rename(columns={'index': date_column})
            
            # Handle missing values
            df[target_column] = df[target_column].interpolate(method='linear')
            
            # Remove outliers (using IQR method)
            Q1 = df[target_column].quantile(0.25)
            Q3 = df[target_column].quantile(0.75)
            IQR = Q3 - Q1
            df.loc[df[target_column] < (Q1 - 1.5 * IQR), target_column] = Q1
            df.loc[df[target_column] > (Q3 + 1.5 * IQR), target_column] = Q3
            
            # Standardize column names for internal processing
            df = df.rename(columns={
                date_column: 'Date',
                target_column: 'Value'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Error in prepare_data: {str(e)}")
            raise ValueError(f"Error preparing data: {str(e)}")

    def evaluate_model(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate comprehensive model evaluation metrics"""
        def safe_metric_calculation(func, *args, default_value=0.0):
            """Safely calculate a metric, returning default if calculation fails"""
            try:
                result = func(*args)
                if np.isnan(result) or np.isinf(result):
                    logger.warning(f"Invalid metric value calculated: {result}, using default: {default_value}")
                    return float(default_value)
                return float(result)
            except Exception as e:
                logger.warning(f"Error calculating metric: {e}, using default: {default_value}")
                return float(default_value)

        # Ensure arrays are numpy arrays and have same length
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)
        
        if len(y_true) != len(y_pred):
            min_len = min(len(y_true), len(y_pred))
            y_true = y_true[:min_len]
            y_pred = y_pred[:min_len]
            logger.warning(f"Array length mismatch, truncated to {min_len} elements")

        # Calculate metrics with error handling
        mse_val = safe_metric_calculation(mean_squared_error, y_true, y_pred)
        rmse_val = safe_metric_calculation(np.sqrt, mse_val)
        mae_val = safe_metric_calculation(mean_absolute_error, y_true, y_pred)
        r2_val = safe_metric_calculation(r2_score, y_true, y_pred)
        
        # MAPE calculation with zero-division protection
        def safe_mape():
            with np.errstate(divide='ignore', invalid='ignore'):
                mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
                return mape if np.isfinite(mape) else 0.0
        
        mape_val = safe_metric_calculation(safe_mape)
        
        # Additional metrics with safety checks
        def safe_adjusted_r2():
            n = len(y_true)
            if n <= 2:  # Need at least 3 points for adjusted R²
                return r2_val
            return 1 - (1 - r2_val) * (n - 1) / (n - 2)
        
        def safe_variance_explained():
            var_residual = np.var(y_true - y_pred) if len(y_true) > 1 else 0
            var_true = np.var(y_true) if len(y_true) > 1 else 1
            if var_true == 0:
                return 1.0 if var_residual == 0 else 0.0
            return 1 - var_residual / var_true

        adjusted_r2_val = safe_metric_calculation(safe_adjusted_r2)
        variance_explained_val = safe_metric_calculation(safe_variance_explained)

        metrics = {
            'mse': mse_val,
            'rmse': rmse_val,
            'mae': mae_val,
            'r2': r2_val,
            'mape': mape_val,
            'adjusted_r2': adjusted_r2_val,
            'variance_explained': variance_explained_val
        }
        
        # Log metrics for debugging
        logger.debug(f"Calculated metrics: {metrics}")
        
        return metrics

    def cross_validate(self, data: np.ndarray, n_splits: int = 5) -> Dict[str, List[float]]:
        """Perform time series cross-validation"""
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = {
            'mse': [], 'rmse': [], 'mae': [], 'r2': [], 'mape': []
        }
        
        for train_idx, test_idx in tscv.split(data):
            train, test = data[train_idx], data[test_idx]
            # TODO: Implement model training and prediction for cross-validation
            # This will depend on the specific model being used
        
        return cv_scores

    def create_sequences(self, data: np.ndarray, seq_length: int) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM with validation"""
        if len(data) <= seq_length:
            raise ValueError(f"Data length ({len(data)}) must be greater than sequence length ({seq_length})")
        
        xs, ys = [], []
        for i in range(len(data) - seq_length):
            xs.append(data[i:(i + seq_length)])
            ys.append(data[i + seq_length])
        return np.array(xs), np.array(ys)

    def lstm_forecast(self, data: List[Dict], date_column: str, target_column: str, 
                     forecast_period: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate forecast using LSTM"""
        try:
            # Validate data
            is_valid, message = self.validate_data(data, date_column, target_column)
            if not is_valid:
                raise ValueError(message)

            # Prepare data
            df = self.prepare_data(data, date_column, target_column)
            
            # At this point, df has standardized column names 'Date' and 'Value'
            values = df['Value'].values.reshape(-1, 1)
            scaled_values = self.scaler.fit_transform(values)

            # Create sequences
            seq_length = parameters.get('sequence_length', 10)
            X, y = self.create_sequences(scaled_values, seq_length)

            # Split data
            train_size = int(len(X) * 0.8)
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]

            # Build model with additional layers and dropout
            model = tf.keras.Sequential([
                tf.keras.layers.LSTM(50, activation='relu', input_shape=(seq_length, 1), return_sequences=True),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.LSTM(30, activation='relu'),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.Dense(20, activation='relu'),
                tf.keras.layers.Dense(1)
            ])

            # Compile with learning rate schedule
            initial_learning_rate = 0.001
            lr_schedule = tf.keras.optimizers.schedules.ExponentialDecay(
                initial_learning_rate, decay_steps=100, decay_rate=0.9
            )
            optimizer = tf.keras.optimizers.Adam(learning_rate=lr_schedule)
            model.compile(optimizer=optimizer, loss='mse')

            # Train model with early stopping
            early_stopping = tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )

            model.fit(
                X_train, y_train,
                epochs=100,
                batch_size=32,
                validation_split=0.2,
                callbacks=[early_stopping],
                verbose=0
            )

            # Generate future dates
            last_date = pd.to_datetime(df['Date'].iloc[-1])
            future_dates = pd.date_range(
                start=last_date + pd.Timedelta(days=1),
                periods=forecast_period,
                freq='D'
            )

            # Prepare input sequence for forecasting
            input_sequence = scaled_values[-seq_length:]

            # Generate forecasts
            forecasts = []
            for _ in range(forecast_period):
                # Reshape input sequence for prediction
                X_pred = input_sequence.reshape(1, seq_length, 1)
                # Get prediction
                y_pred = model.predict(X_pred, verbose=0)
                # Append prediction to forecasts
                forecasts.append(y_pred[0, 0])
                # Update input sequence
                input_sequence = np.roll(input_sequence, -1)
                input_sequence[-1] = y_pred

            # Inverse transform the forecasts
            forecasts = self.scaler.inverse_transform(np.array(forecasts).reshape(-1, 1))

            # Calculate metrics using the test set
            y_pred_test = model.predict(X_test, verbose=0)
            y_pred_test = self.scaler.inverse_transform(y_pred_test)
            y_test_actual = self.scaler.inverse_transform(y_test.reshape(-1, 1))
            metrics = self.evaluate_model(y_test_actual, y_pred_test)

            # Calculate confidence intervals (using prediction std as a simple approach)
            std = np.std(y_test_actual - y_pred_test)
            confidence_intervals = {
                'lower': forecasts - 1.96 * std,
                'upper': forecasts + 1.96 * std
            }

            # Convert forecast to simple list of floats (like Prophet)
            forecast_list = forecasts.flatten().tolist()

            return {
                'forecast': forecast_list,  # Simple list of numbers
                'dates': [d.strftime('%Y-%m-%d') for d in future_dates],
                'metrics': metrics,
                'confidence_intervals': {
                    'lower': confidence_intervals['lower'].flatten().tolist(),
                    'upper': confidence_intervals['upper'].flatten().tolist()
                }
            }

        except Exception as e:
            logger.error(f"Error in LSTM forecast: {str(e)}")
            raise ValueError(f"Error in LSTM forecast: {str(e)}")

    def arima_forecast(self, data: List[Dict], date_column: str, target_column: str, 
                      forecast_period: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate forecast using ARIMA"""
        try:
            # Validate data
            is_valid, message = self.validate_data(data, date_column, target_column)
            if not is_valid:
                raise ValueError(message)

            # Prepare data
            df = self.prepare_data(data, date_column, target_column)
            
            # At this point, df has standardized column names 'Date' and 'Value'
            values = df['Value'].values

            # Fit ARIMA model with parameters
            p = parameters.get('p', 1)
            d = parameters.get('d', 1) 
            q = parameters.get('q', 1)
            model = ARIMA(values, order=(p, d, q))
            model_fit = model.fit()

            # Generate forecast
            forecast = model_fit.forecast(steps=forecast_period)
            
            # Calculate confidence intervals
            conf_int = model_fit.get_forecast(steps=forecast_period).conf_int()
            lower = conf_int[:, 0]
            upper = conf_int[:, 1]

            # Generate future dates
            last_date = pd.to_datetime(df['Date'].iloc[-1])
            future_dates = pd.date_range(
                start=last_date + pd.Timedelta(days=1),
                periods=forecast_period,
                freq='D'
            )

            # Calculate metrics
            train_pred = model_fit.get_prediction(0)
            y_pred = train_pred.predicted_mean
            metrics = self.evaluate_model(values, y_pred)

            # Convert forecast to simple list of floats (like Prophet)
            forecast_list = [float(forecast[i]) for i in range(len(forecast))]

            return {
                'forecast': forecast_list,  # Simple list of numbers
                'dates': [d.strftime('%Y-%m-%d') for d in future_dates],
                'metrics': metrics,
                'confidence_intervals': {
                    'lower': lower.tolist(),
                    'upper': upper.tolist()
                }
            }

        except Exception as e:
            logger.error(f"Error in ARIMA forecast: {str(e)}")
            raise ValueError(f"Error in ARIMA forecast: {str(e)}")

    def prophet_forecast(self, data: List[Dict], date_column: str, target_column: str, 
                        forecast_period: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate forecast using Prophet with enhanced features"""
        try:
            # Validate data
            is_valid, message = self.validate_data(data, date_column, target_column)
            if not is_valid:
                raise ValueError(message)

            # Prepare data
            df = self.prepare_data(data, date_column, target_column)
            # Note: prepare_data standardizes column names to 'Date' and 'Value'
            prophet_df = df.rename(columns={'Date': 'ds', 'Value': 'y'})

            # Additional validation for Prophet - ensure y column is strictly numeric
            if not pd.api.types.is_numeric_dtype(prophet_df['y']):
                logger.error(f"Prophet target column 'y' is not numeric. Dtype: {prophet_df['y'].dtype}")
                raise ValueError(f"Prophet requires numeric target values, but got {prophet_df['y'].dtype}")
            
            # Check for any remaining non-finite values
            if prophet_df['y'].isna().any() or np.isinf(prophet_df['y']).any():
                logger.warning("Found NaN or infinite values in Prophet target column, cleaning...")
                prophet_df = prophet_df.dropna(subset=['y'])
                prophet_df = prophet_df[np.isfinite(prophet_df['y'])]
                
            if len(prophet_df) == 0:
                raise ValueError("No valid numeric data remaining for Prophet forecasting")
            
            logger.info(f"Prophet data prepared successfully. Shape: {prophet_df.shape}, y column dtype: {prophet_df['y'].dtype}")

            # Initialize Prophet model (without additional regressors for now to avoid issues)
            model = Prophet(
                growth=parameters.get('growth', 'linear'),
                seasonality_mode=parameters.get('seasonality_mode', 'additive'),
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=parameters.get('changepoint_prior_scale', 0.05),
                seasonality_prior_scale=parameters.get('seasonality_prior_scale', 10.0)
            )

            # Add country holidays if specified
            if parameters.get('add_holidays'):
                model.add_country_holidays(country='US')  # Adjust country as needed

            # Note: Skipping additional regressors for now to avoid data type issues
            # Future enhancement: Add proper validation for numeric regressors

            model.fit(prophet_df)

            # Create future dataframe
            future = model.make_future_dataframe(periods=forecast_period)
            
            # Note: No additional regressors to add for now

            # Generate forecast
            forecast = model.predict(future)

            # Extract forecast values
            forecast_values = forecast.tail(forecast_period)['yhat'].values

            # Calculate metrics
            train_size = int(len(prophet_df) * 0.8)
            train = prophet_df.iloc[:train_size]
            test = prophet_df.iloc[train_size:]
            
            model_train = Prophet(
                growth=parameters.get('growth', 'linear'),
                seasonality_mode=parameters.get('seasonality_mode', 'additive')
            )
            model_train.fit(train)
            
            future_test = model_train.make_future_dataframe(periods=len(test))
            forecast_test = model_train.predict(future_test)
            predictions = forecast_test.tail(len(test))['yhat'].values
            
            metrics = self.evaluate_model(test['y'].values, predictions)

            # Generate component plots data
            components = model.predict(future)
            components_data = {
                'trend': components['trend'].tail(forecast_period).tolist(),
                'yearly': components['yearly'].tail(forecast_period).tolist() if 'yearly' in components else None,
                'weekly': components['weekly'].tail(forecast_period).tolist() if 'weekly' in components else None
            }

            return {
                'forecast': forecast_values.tolist(),
                'dates': forecast.tail(forecast_period)['ds'].dt.strftime('%Y-%m-%d').tolist(),
                'metrics': metrics,
                'confidence_intervals': {
                    'lower': forecast.tail(forecast_period)['yhat_lower'].tolist(),
                    'upper': forecast.tail(forecast_period)['yhat_upper'].tolist()
                },
                'components': components_data
            }

        except Exception as e:
            logger.error(f"Error in Prophet forecast: {str(e)}")
            raise ValueError(f"Error in Prophet forecast: {str(e)}")

    def generate_forecast(self, data: List[Dict], method: str, date_column: str, 
                        target_column: str, forecast_period: int, 
                        parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate forecast using specified method"""
        try:
            if parameters is None:
                parameters = {}

            if method == 'lstm':
                return self.lstm_forecast(data, date_column, target_column, forecast_period, parameters)
            elif method == 'arima':
                return self.arima_forecast(data, date_column, target_column, forecast_period, parameters)
            elif method == 'prophet':
                return self.prophet_forecast(data, date_column, target_column, forecast_period, parameters)
            else:
                raise ValueError(f"Unsupported forecasting method: {method}")

        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise ValueError(f"Error generating forecast: {str(e)}") 