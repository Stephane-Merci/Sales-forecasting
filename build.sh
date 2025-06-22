#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit  # Exit on error

echo "🚀 Starting Smart-Buiz deployment build..."

echo "🐍 Python version:"
python --version

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🗄️ Running database migrations..."
python manage.py migrate --noinput

echo "👤 Creating superuser (if needed)..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@smartbuiz.com').exists():
    User.objects.create_superuser(
        email='admin@smartbuiz.com',
        first_name='Admin',
        last_name='User',
        password='admin123',
        is_verified=True
    )
    print("✅ Superuser created successfully!")
else:
    print("ℹ️  Superuser already exists")
EOF

echo "🎉 Build completed successfully!"
echo "🌐 Smart-Buiz is ready for deployment!" 