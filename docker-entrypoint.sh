#!/bin/bash
set -e

# Перевірка доступності PostgreSQL
if [ -n "$POSTGRES_HOST" ]; then
    echo "Очікування PostgreSQL..."
    while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
        sleep 0.5
    done
    echo "PostgreSQL доступний!"
fi

# Перевірка доступності Redis
if [ -n "$REDIS_HOST" ]; then
    echo "Очікування Redis..."
    while ! nc -z $REDIS_HOST $REDIS_PORT; do
        sleep 0.5
    done
    echo "Redis доступний!"
fi

# Застосування міграцій бази даних
echo "Застосування міграцій..."
python manage.py migrate --noinput

# Збирання статичних файлів
echo "Збирання статичних файлів..."
python manage.py collectstatic --noinput

# Створення суперкористувача, якщо передані відповідні змінні
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "Створення суперкористувача..."
    python manage.py createsuperuser --noinput
fi

# Виконання команди
exec "$@"
