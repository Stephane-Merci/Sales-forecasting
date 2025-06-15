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

            # Check target column
            try:
                df[target_column] = pd.to_numeric(df[target_column])
            except Exception as e:
                return False, f"Invalid numeric format in column '{target_column}': {str(e)}"

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
        df = pd.DataFrame(data)
        df[date_column] = pd.to_datetime(df[date_column])
        df = df.sort_values(date_column)
        
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
        
        return df

    def evaluate_model(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate comprehensive model evaluation metrics"""
        metrics = {
            'mse': mean_squared_error(y_true, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred),
            'mape': np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        }
        
        # Add additional metrics
        metrics['adjusted_r2'] = 1 - (1 - metrics['r2']) * (len(y_true) - 1) / (len(y_true) - 1 - 1)
        metrics['variance_explained'] = 1 - np.var(y_true - y_pred) / np.var(y_true)
        
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
        """Generate forecast using LSTM with enhanced features"""
        try:
            # Validate data
            is_valid, message = self.validate_data(data, date_column, target_column)
            if not is_valid:
                raise ValueError(message)

            # Prepare data
            df = self.prepare_data(data, date_column, target_column)
            values = df[target_column].values.reshape(-1, 1)
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

            # Train with early stopping and validation split
            epochs = parameters.get('epochs', 50)
            early_stopping = tf.keras.callbacks.EarlyStopping(
                monitor='val_loss', patience=5, restore_best_weights=True
            )
            history = model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=32,
                validation_split=0.2,
                callbacks=[early_stopping],
                verbose=0
            )

            # Generate forecast with confidence intervals
            last_sequence = scaled_values[-seq_length:]
            forecast_values = []
            lower_bound = []
            upper_bound = []

            for _ in range(forecast_period):
                # Generate multiple predictions with dropout enabled
                predictions = []
                for _ in range(100):  # Monte Carlo iterations
                    pred = model.predict(last_sequence.reshape(1, seq_length, 1), verbose=0)
                    predictions.append(pred[0, 0])
                
                # Calculate mean and confidence intervals
                mean_pred = np.mean(predictions)
                std_pred = np.std(predictions)
                forecast_values.append(mean_pred)
                lower_bound.append(mean_pred - 1.96 * std_pred)
                upper_bound.append(mean_pred + 1.96 * std_pred)
                
                # Update sequence
                last_sequence = np.roll(last_sequence, -1)
                last_sequence[-1] = mean_pred

            # Inverse transform
            forecast_values = np.array(forecast_values).reshape(-1, 1)
            lower_bound = np.array(lower_bound).reshape(-1, 1)
            upper_bound = np.array(upper_bound).reshape(-1, 1)
            
            forecast_values = self.scaler.inverse_transform(forecast_values)
            lower_bound = self.scaler.inverse_transform(lower_bound)
            upper_bound = self.scaler.inverse_transform(upper_bound)

            # Calculate metrics
            y_pred = model.predict(X_test, verbose=0)
            y_pred = self.scaler.inverse_transform(y_pred)
            y_test_actual = self.scaler.inverse_transform(y_test)
            
            metrics = self.evaluate_model(y_test_actual, y_pred)
            
            # Generate forecast dates
            last_date = df[date_column].max()
            forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=forecast_period)

            return {
                'forecast': forecast_values.flatten().tolist(),
                'dates': forecast_dates.strftime('%Y-%m-%d').tolist(),
                'metrics': metrics,
                'confidence_intervals': {
                    'lower': lower_bound.flatten().tolist(),
                    'upper': upper_bound.flatten().tolist()
                },
                'training_history': {
                    'loss': history.history['loss'],
                    'val_loss': history.history['val_loss']
                }
            }

        except Exception as e:
            logger.error(f"Error in LSTM forecast: {str(e)}")
            raise ValueError(f"Error in LSTM forecast: {str(e)}")

    def arima_forecast(self, data: List[Dict], date_column: str, target_column: str, 
                      forecast_period: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate forecast using ARIMA with enhanced features"""
        try:
            # Validate data
            is_valid, message = self.validate_data(data, date_column, target_column)
            if not is_valid:
                raise ValueError(message)

            # Prepare data
            df = self.prepare_data(data, date_column, target_column)
            values = df[target_column].values

            # Get ARIMA parameters
            p = parameters.get('p', 1)
            d = parameters.get('d', 1)
            q = parameters.get('q', 1)

            # Fit ARIMA model with automatic order selection if not specified
            if all(v == 0 for v in [p, d, q]):
                from pmdarima import auto_arima
                model = auto_arima(values, seasonal=True, stepwise=True)
                p, d, q = model.order
            else:
                model = ARIMA(values, order=(p, d, q))
                model = model.fit()

            # Generate forecast with confidence intervals
            forecast = model.forecast(steps=forecast_period)
            conf_int = model.get_forecast(steps=forecast_period).conf_int()
            
            # Calculate metrics
            train_size = int(len(values) * 0.8)
            train, test = values[:train_size], values[train_size:]
            predictions = model.predict(start=train_size, end=len(values)-1)
            metrics = self.evaluate_model(test, predictions)

            # Generate forecast dates
            last_date = df[date_column].max()
            forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=forecast_period)

            return {
                'forecast': forecast.tolist(),
                'dates': forecast_dates.strftime('%Y-%m-%d').tolist(),
                'metrics': metrics,
                'confidence_intervals': {
                    'lower': conf_int[:, 0].tolist(),
                    'upper': conf_int[:, 1].tolist()
                },
                'model_params': {
                    'p': p, 'd': d, 'q': q,
                    'aic': model.aic,
                    'bic': model.bic
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
            prophet_df = df.rename(columns={date_column: 'ds', target_column: 'y'})

            # Add additional regressors if available
            for col in df.columns:
                if col not in [date_column, target_column] and np.issubdtype(df[col].dtype, np.number):
                    prophet_df[col] = df[col]

            # Initialize and fit Prophet model with additional parameters
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

            # Add additional regressors
            for col in prophet_df.columns:
                if col not in ['ds', 'y']:
                    model.add_regressor(col)

            model.fit(prophet_df)

            # Create future dataframe
            future = model.make_future_dataframe(periods=forecast_period)
            
            # Add regressor values to future dataframe if any
            for col in prophet_df.columns:
                if col not in ['ds', 'y']:
                    future[col] = prophet_df[col].mean()  # Use mean for simplicity

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
        """Main method to generate forecasts using specified method with validation"""
        try:
            # Validate parameters
            if parameters is None:
                parameters = {}

            if method not in ['lstm', 'arima', 'prophet']:
                raise ValueError(f"Unsupported forecasting method: {method}")

            if forecast_period < 1 or forecast_period > 365:
                raise ValueError("Forecast period must be between 1 and 365 days")

            # Map methods to functions
            method_map = {
                'lstm': self.lstm_forecast,
                'arima': self.arima_forecast,
                'prophet': self.prophet_forecast
            }

            # Generate forecast
            forecast_func = method_map[method]
            result = forecast_func(data, date_column, target_column, forecast_period, parameters)

            # Log success
            logger.info(f"Successfully generated {method} forecast for {target_column}")

            return result

        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise ValueError(f"Error generating forecast: {str(e)}") 