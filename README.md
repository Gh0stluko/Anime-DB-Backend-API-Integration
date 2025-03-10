# 🌸 Anime DB parser from API

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Django](https://img.shields.io/badge/Django-5.1-blue.svg)

Бекенд/збирач бази данних та початкова точка вашого проекту. 

Що це таке?

Це бекенд, який бере інформацію з jikan/anilist api та інтегрує в вашу базу данних.

<div align="center">
    <img src="docs/images/preview.png" alt="Anime Platform Preview" width="800"/>
</div>

## 📌 Особливості проекту

- 🔍 **Каталог аніме** з детальною інформацією (описи, рейтинги, жанри)
- 🔄 **Інтеграція з API** (Jikan, AniList) з розумним обмеженням швидкості запитів
- 🧠 **Система пріоритетного оновлення даних** на основі популярності та статусу аніме
- 📊 **Розширена адмін-панель** для моніторингу API та управління оновленнями
- 🇯🇵 **Оптимізована підтримка японського тексту**
- 🌓 **Темна та світла теми** інтерфейсу адмін-панелі

## 💻 Технології

- **Backend**: Django 5.1, Django REST Framework
- **База даних**: PostgreSQL
- **Черги**: Celery
- **Контейнеризація**: Docker, Docker Compose

## 🚀 Запуск проекту

### Використання Docker Compose (рекомендовано):

```bash
# Клонуйте репозиторій
git clone https://github.com/your-username/anime.git
cd anime

# Створіть .env файл на основі прикладу
cp .env.example .env
# Відредагуйте .env файл за потреби

# Запустіть за допомогою Docker Compose
docker-compose up -d
```

### Налаштування середовища розробки:

```bash
# Створіть віртуальне середовище
python -m venv venv
source venv/bin/activate  # Linux/Mac
# або
venv\Scripts\activate     # Windows

# Встановіть залежності
cd backend
pip install -r requirements.txt

# Застосуйте міграції
python manage.py migrate

# Запустіть сервер розробки
python manage.py runserver
```

## 📸 Скріншоти

<div align="center">
    <div>
        <img src="docs/images/admin_panel.png" width="45%" alt="Адмін-панель"/>
        <img src="docs/images/dark_mode.png" width="45%" alt="Темна тема"/>
    </div>
    <div>
        <img src="docs/images/api_stats.png" width="45%" alt="Статистика API"/>
        <img src="docs/images/update_stats.png" width="45%" alt="Статистика оновлень"/>
    </div>
</div>

## 📋 Система оновлень даних

Проект реалізує розумну систему оновлення даних з зовнішніх API:

- **Пріоритизація контенту**: онгоїнги та популярні аніме оновлюються частіше
- **Обмеження швидкості API**: дотримання лімітів API з адаптивним очікуванням
- **Диференційні оновлення**: вибір типу оновлення в залежності від потреб (метадані, епізоди, зображення)
- **Моніторинг процесу**: повна статистика успішності та графіки використання

## 📄 Ліцензія

Цей проект поширюється під ліцензією MIT. Детальніше у файлі [LICENSE](LICENSE).
