FROM python:3.13-slim

# Встановлення середовища
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Встановлення системних залежностей
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gcc \
        python3-dev \
        netcat-openbsd \
        gettext \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Створення та використання непривілейованого користувача
RUN useradd -m animeuser
WORKDIR /app
COPY backend/requirements.txt /app/

# Встановлення Python залежностей
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install watchdog[watchmedo]

# Копіювання проекту
COPY backend /app/

# Виправлення прав доступу
RUN chown -R animeuser:animeuser /app
USER animeuser

# Створення та налаштування entrypoint
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Встановлення порту та entrypoint
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
