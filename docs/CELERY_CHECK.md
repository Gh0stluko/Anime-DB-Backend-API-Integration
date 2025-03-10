# Перевірка роботи Celery

Цей документ описує різні способи перевірки роботи Celery у проекті Anime Platform.

## Перевірка статусу за допомогою скрипта

### В Docker середовищі

```bash
# Виконати скрипт перевірки у контейнері backend
docker-compose exec backend python check_celery.py
```

### У локальному середовищі

```bash
cd backend
python check_celery.py
```

## Перегляд логів Celery

### Logs через Docker

```bash
# Перегляд логів Celery worker
docker-compose logs -f celery_worker

# Перегляд логів Celery beat
docker-compose logs -f celery_beat
```

### Перевірка активних воркерів через командний рядок

```bash
# В Docker середовищі
docker-compose exec backend celery -A core inspect active

# Локально
celery -A core inspect active
```

## Перевірка через адмін-панель Django

1. Відкрийте адмін-панель Django (http://localhost:8000/admin/)
2. Перейдіть до розділу "Periodic tasks" (якщо використовується django-celery-beat)
3. Перевірте статус запланованих завдань

## Ручний запуск завдань

### Через Django shell

```bash
# В Docker середовищі
docker-compose exec backend python manage.py shell

# Локально
python manage.py shell
```

Далі в Python shell:

```python
from anime.tasks import test_celery_task
task = test_celery_task.delay()
print(f"Завдання запущено з ID: {task.id}")
```

## Діагностика проблем

1. **Перевірте підключення до Redis**:
   ```bash
   docker-compose exec redis redis-cli ping
   ```
   Має повернути `PONG`

2. **Перевірте, чи запущені контейнери**:
   ```bash
   docker-compose ps
   ```
   
3. **Перезапустіть Celery у разі проблем**:
   ```bash
   docker-compose restart celery_worker celery_beat
   ```

4. **Перевірте змінні середовища**:
   ```bash
   docker-compose exec backend env | grep CELERY
   ```
