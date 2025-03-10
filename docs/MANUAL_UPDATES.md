# Мануальне оновлення аніме

Цей документ описує різні способи мануального оновлення аніме, включаючи примусове оновлення аніме, що вже стоять у черзі.

## 1. Використання Django Shell

Найпростіший спосіб примусово оновити аніме через Django shell:

```bash
# У Docker середовищі
docker-compose exec backend python manage.py shell

# У локальному середовищі
python manage.py shell
```

Потім у shell виконайте:

```python
# Імпортуємо задачу
from anime.tasks import force_update_scheduled_anime_task

# Оновити всі заплановані аніме (next_update_scheduled <= now)
result = force_update_scheduled_anime_task.delay()
print(f"Задачу запущено з ID: {result.id}")

# Або оновити конкретні аніме за їхніми ID
anime_ids = [1, 2, 3]  # Замініть на реальні ID
result = force_update_scheduled_anime_task.delay(anime_ids=anime_ids)
print(f"Задачу запущено з ID: {result.id}")

# Вказати тип оновлення (full, metadata, episodes, images)
result = force_update_scheduled_anime_task.delay(update_type='episodes')
print(f"Задачу запущено з ID: {result.id}")
```

## 2. Підготовка списку ID аніме для оновлення

Щоб отримати ID аніме, які заплановані на оновлення:

```python
from anime.models import Anime
from django.utils import timezone

# Аніме, заплановані на оновлення (дата оновлення вже настала)
now = timezone.now()
scheduled_anime = Anime.objects.filter(next_update_scheduled__lte=now)
print(f"Знайдено {scheduled_anime.count()} аніме для оновлення")

# Отримати їхні ID
anime_ids = list(scheduled_anime.values_list('id', flat=True))
print(f"ID аніме для оновлення: {anime_ids}")

# Запустити оновлення для цих ID
from anime.tasks import force_update_scheduled_anime_task
result = force_update_scheduled_anime_task.delay(anime_ids=anime_ids)
print(f"Задачу запущено з ID: {result.id}")
```

## 3. Оновлення аніме за їхніми MAL ID

Якщо у вас є список MAL ID (MyAnimeList ID):

```python
from anime.models import Anime

# Отримати ID аніме за їхніми MAL ID
mal_ids = [5114, 9253, 1535]  # Приклад: Fullmetal Alchemist: Brotherhood, Steins;Gate тощо
anime_objects = Anime.objects.filter(mal_id__in=mal_ids)
anime_ids = list(anime_objects.values_list('id', flat=True))

# Запустити оновлення
from anime.tasks import force_update_scheduled_anime_task
result = force_update_scheduled_anime_task.delay(anime_ids=anime_ids)
print(f"Задачу запущено з ID: {result.id}")
```

## 4. Моніторинг оновлення

Для перевірки статусу оновлень:

```bash
# Перегляд логів Celery
docker-compose logs -f celery_worker

# Перегляд статусу задач
docker-compose exec backend celery -A core inspect active
```

Також можна перевірити в адмін-панелі Django, у розділі "Аніме" - колонка "Останнє оновлення" 
повинна відображати нову дату оновлення після успішного виконання задачі.
