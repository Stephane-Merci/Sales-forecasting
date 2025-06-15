document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2 for all select elements
    $('select').select2({
        width: '100%'
    });

    // Handle forecasting method change
    const methodSelect = document.querySelector('select[name="method"]');
    methodSelect.addEventListener('change', function() {
        // Hide all parameter groups
        document.querySelectorAll('.parameter-group').forEach(group => {
            group.classList.remove('active');
        });

        // Show selected method's parameters
        const selectedMethod = this.value;
        document.getElementById(`${selectedMethod}Params`).classList.add('active');
    });

    // Handle data source change
    const dataSourceSelect = document.querySelector('select[name="dataSource"]');
    const uploadSection = document.getElementById('uploadSection');

    dataSourceSelect.addEventListener('change', function() {
        uploadSection.style.display = this.value === 'upload' ? 'block' : 'none';
    });

    // Handle file upload and column detection
    const fileInput = document.querySelector('input[name="dataFile"]');
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const csv = e.target.result;
                const lines = csv.split('\n');
                if (lines.length > 0) {
                    const headers = lines[0].split(',').map(h => h.trim());
                    
                    // Populate column selects
                    const dateSelect = document.querySelector('select[name="dateColumn"]');
                    const targetSelect = document.querySelector('select[name="targetColumn"]');
                    
                    dateSelect.innerHTML = '';
                    targetSelect.innerHTML = '';
                    
                    headers.forEach(header => {
                        dateSelect.add(new Option(header, header));
                        targetSelect.add(new Option(header, header));
                    });

                    // Trigger Select2 update
                    $(dateSelect).trigger('change');
                    $(targetSelect).trigger('change');
                }
            };
            reader.readAsText(file);
        }
    });

    // Handle form submission
    const generateForecastBtn = document.getElementById('generateForecastBtn');
    const newForecastForm = document.getElementById('newForecastForm');

    generateForecastBtn.addEventListener('click', async function() {
        if (!newForecastForm.checkValidity()) {
            newForecastForm.reportValidity();
            return;
        }

        const formData = new FormData(newForecastForm);
        const method = formData.get('method');
        
        // Collect method-specific parameters
        let parameters = {};
        switch (method) {
            case 'lstm':
                parameters = {
                    sequence_length: parseInt(formData.get('lstmSequenceLength')),
                    epochs: parseInt(formData.get('lstmEpochs'))
                };
                break;
            case 'arima':
                parameters = {
                    p: parseInt(formData.get('arimaP')),
                    d: parseInt(formData.get('arimaD')),
                    q: parseInt(formData.get('arimaQ'))
                };
                break;
            case 'prophet':
                parameters = {
                    growth: formData.get('prophetGrowth'),
                    seasonality_mode: formData.get('prophetSeasonality')
                };
                break;
        }

        // Prepare data
        let historicalData = [];
        if (formData.get('dataSource') === 'upload') {
            const file = formData.get('dataFile');
            if (file) {
                const text = await file.text();
                const lines = text.split('\n');
                const headers = lines[0].split(',').map(h => h.trim());
                
                for (let i = 1; i < lines.length; i++) {
                    const values = lines[i].split(',').map(v => v.trim());
                    if (values.length === headers.length) {
                        const row = {};
                        headers.forEach((header, index) => {
                            row[header] = values[index];
                        });
                        historicalData.push(row);
                    }
                }
            }
        }

        // Prepare request data
        const requestData = {
            name: formData.get('name'),
            date_column: formData.get('dateColumn'),
            target_column: formData.get('targetColumn'),
            method: method,
            period: parseInt(formData.get('period')),
            parameters: parameters,
            historical_data: historicalData
        };

        try {
            const response = await fetch('/forecasting/api/generate-forecast/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();
            
            if (result.status === 'success') {
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('newForecastModal'));
                modal.hide();

                // Update chart
                updateForecastChart(result.data);
                
                // Add new model to list
                addModelToList({
                    id: result.data.model_id,
                    name: requestData.name,
                    method: requestData.method,
                    target_column: requestData.target_column,
                    created_at: new Date().toISOString()
                });

                // Show success message
                showAlert('success', 'Forecast generated successfully!');
            } else {
                showAlert('error', result.message);
            }
        } catch (error) {
            showAlert('error', 'Error generating forecast: ' + error.message);
        }
    });

    // Handle model selection
    document.getElementById('forecastModelsList').addEventListener('click', async function(e) {
        const modelItem = e.target.closest('.list-group-item-action');
        if (modelItem) {
            e.preventDefault();
            const modelId = modelItem.dataset.modelId;
            
            try {
                const response = await fetch(`/forecasting/api/forecast-history/${modelId}/`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    // Update model details
                    updateModelDetails(result.data);
                    
                    // Update chart
                    if (result.data.results.length > 0) {
                        const latestResult = result.data.results[0];
                        updateForecastChart({
                            forecast: latestResult.forecast_data,
                            metrics: latestResult.metrics
                        });
                    }
                } else {
                    showAlert('error', result.message);
                }
            } catch (error) {
                showAlert('error', 'Error loading forecast details: ' + error.message);
            }
        }
    });
});

// Helper Functions

function updateForecastChart(data) {
    const chartDiv = document.getElementById('forecastChart');
    
    const traces = [
        {
            name: 'Historical',
            x: data.dates.slice(0, -data.forecast.length),
            y: data.historical,
            type: 'scatter',
            mode: 'lines',
            line: { color: '#2196F3' }
        },
        {
            name: 'Forecast',
            x: data.dates.slice(-data.forecast.length),
            y: data.forecast,
            type: 'scatter',
            mode: 'lines',
            line: { color: '#4CAF50' }
        }
    ];

    if (data.confidence_intervals) {
        traces.push({
            name: 'Upper Bound',
            x: data.dates.slice(-data.forecast.length),
            y: data.confidence_intervals.upper,
            type: 'scatter',
            mode: 'lines',
            line: { color: '#90CAF9', dash: 'dot' },
            showlegend: false
        });
        traces.push({
            name: 'Lower Bound',
            x: data.dates.slice(-data.forecast.length),
            y: data.confidence_intervals.lower,
            type: 'scatter',
            mode: 'lines',
            line: { color: '#90CAF9', dash: 'dot' },
            fill: 'tonexty',
            showlegend: false
        });
    }

    const layout = {
        title: 'Forecast Results',
        xaxis: { title: 'Date' },
        yaxis: { title: 'Value' },
        hovermode: 'x unified',
        showlegend: true,
        legend: { orientation: 'h', y: -0.2 }
    };

    Plotly.newPlot(chartDiv, traces, layout);
}

function updateModelDetails(data) {
    // Update parameters
    const paramsDiv = document.getElementById('modelParameters');
    paramsDiv.innerHTML = `
        <table class="table table-sm">
            <tr><th>Method:</th><td>${data.model.method}</td></tr>
            <tr><th>Target:</th><td>${data.model.target_column}</td></tr>
            ${Object.entries(data.model.parameters).map(([key, value]) => 
                `<tr><th>${key}:</th><td>${value}</td></tr>`
            ).join('')}
        </table>
    `;

    // Update metrics
    const metricsDiv = document.getElementById('modelMetrics');
    if (data.results.length > 0) {
        const metrics = data.results[0].metrics;
        metricsDiv.innerHTML = `
            <table class="table table-sm">
                ${Object.entries(metrics).map(([key, value]) => 
                    `<tr><th>${key}:</th><td>${typeof value === 'number' ? value.toFixed(4) : value}</td></tr>`
                ).join('')}
            </table>
        `;
    }
}

function addModelToList(model) {
    const list = document.getElementById('forecastModelsList');
    const item = document.createElement('a');
    item.href = '#';
    item.className = 'list-group-item list-group-item-action';
    item.dataset.modelId = model.id;
    
    item.innerHTML = `
        <div class="d-flex w-100 justify-content-between">
            <h6 class="mb-1">${model.name}</h6>
            <small>${model.method}</small>
        </div>
        <p class="mb-1">${model.target_column}</p>
        <small>Created: ${new Date(model.created_at).toLocaleString()}</small>
    `;
    
    list.insertBefore(item, list.firstChild);
}

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.querySelector('.container-fluid').insertBefore(alertDiv, document.querySelector('.container-fluid').firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = bootstrap.Alert.getOrCreateInstance(alertDiv);
        alert.close();
    }, 5000);
} 