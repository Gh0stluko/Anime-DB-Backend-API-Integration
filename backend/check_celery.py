#!/usr/bin/env python
"""
Скрипт для перевірки роботи Celery
"""
import sys
from django import setup
import os

# Налаштування Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
setup()

from celery.app.control import Control
from core.celery import app
from celery.exceptions import CeleryError

def get_active_workers():
    """Отримати список активних воркерів"""
    control = Control(app)
    try:
        ping = control.ping(timeout=1.0)
        if not ping:
            print("Немає активних воркерів Celery")
            return False
        
        print(f"Активні воркери Celery ({len(ping)}):")
        for worker, response in ping.items():
            status = "✅ Працює" if response.get('ok') == 'pong' else "❌ Помилка"
            print(f"  • {worker}: {status}")
        
        stats = control.inspect().stats()
        if stats:
            print("\nДетальна інформація:")
            for worker, info in stats.items():
                print(f"  • {worker}:")
                print(f"    - Процеси: {info.get('pool', {}).get('processes', [])}")
                print(f"    - Частота: {info.get('pool', {}).get('freq', 0)}")
                
        return True
    except CeleryError as e:
        print(f"Помилка з'єднання з Celery: {e}")
        return False

def check_scheduled_tasks():
    """Перевірити заплановані завдання"""
    try:
        inspector = app.control.inspect()
        scheduled = inspector.scheduled()
        
        if not scheduled:
            print("\nНемає запланованих завдань")
            return
        
        print("\nЗаплановані завдання:")
        for worker, tasks in scheduled.items():
            print(f"  • {worker}:")
            for task in tasks:
                print(f"    - {task['request']['name']} (ID: {task['request']['id']})")
                print(f"      Час виконання: {task.get('eta', 'Невідомо')}")
    except CeleryError as e:
        print(f"Помилка отримання запланованих завдань: {e}")

def run_test_task():
    """Запустити тестове завдання"""
    from anime.tasks import test_celery_task
    
    print("\nЗапуск тестового завдання...")
    task = test_celery_task.delay()
    print(f"Завдання відправлено з ID: {task.id}")
    print("Перевірте журнали Celery для підтвердження виконання")

if __name__ == "__main__":
    print("=" * 60)
    print("ПЕРЕВІРКА СТАТУСУ CELERY")
    print("=" * 60)
    
    workers_active = get_active_workers()
    if workers_active:
        check_scheduled_tasks()
        
    action = input("\nБажаєте запустити тестове завдання? (так/ні): ")
    if action.lower() in ['так', 'yes', 'y', 't']:
        run_test_task()
    
    print("\n" + "=" * 60)
