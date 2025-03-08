from django.core.management.base import BaseCommand
from anime.models import Genre
from anime.services.translation_service import TranslationService
import logging

logger = logging.getLogger(__name__)

# Dictionary of common genre translations
GENRE_TRANSLATIONS = {
    'Action': 'Екшн',
    'Adventure': 'Пригоди',
    'Comedy': 'Комедія',
    'Drama': 'Драма',
    'Fantasy': 'Фентезі',
    'Horror': 'Жахи',
    'Mystery': 'Містика',
    'Romance': 'Романтика',
    'Sci-Fi': 'Наукова фантастика',
    'Shounen': 'Сьонен',
    'Shoujo': 'Сьодзьо',
    'Slice of Life': 'Повсякденність',
    'Sports': 'Спорт',
    'Supernatural': 'Надприродне',
    'Thriller': 'Трилер',
    'Psychological': 'Психологічне',
    'Seinen': 'Сейнен',
    'Josei': 'Дзьосей',
    'Mecha': 'Меха',
    'Music': 'Музика',
    'Ecchi': 'Етті',
    'Harem': 'Гарем',
    'Historical': 'Історичне',
    'Isekai': 'Ісекай',
    'Military': 'Мілітарі',
    'School': 'Школа',
    'Magic': 'Магія',
    'Demons': 'Демони',
    'Game': 'Гра',
    'Hentai': 'Хентай',
    'Martial Arts': 'Бойові мистецтва',
    'Vampire': 'Вампіри',
    'Mystery': 'Детектив',
    'Space': 'Космос',
    'Super Power': 'Суперсили',
    'Award Winning': 'Нагороджені',
    'Cars': 'Автомобілі',
    'Dementia': 'Деменція',
    'Kids': 'Для дітей',
    'Police': 'Поліція',
    'Parody': 'Пародія',
    'Samurai': 'Самураї',
    'Gore': 'Жорстокість',
    'Yaoi': 'Яой',
    'Yuri': 'Юрі',
    'Cyberpunk': 'Кіберпанк',
    'Post-Apocalyptic': 'Пост-апокаліпсис',
    'Gourmet': 'Кулінарія',
    'Suspense': 'Саспенс',
    'Horror': 'Горор',
    'Medical': 'Медицина',
    # Add more as needed
}

class Command(BaseCommand):
    help = 'Translates genre names to Ukrainian'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Translate all genres, even those with existing translations',
        )

    def handle(self, *args, **options):
        translate_all = options['all']
        genres = Genre.objects.all()
        if not translate_all:
            genres = genres.filter(name_ukrainian__exact='')
            
        total_count = genres.count()
        self.stdout.write(f"Translating {total_count} genres to Ukrainian...")
        
        translated_count = 0
        failed_count = 0
        
        for genre in genres:
            try:
                # First check our predefined translations dictionary
                if genre.name in GENRE_TRANSLATIONS:
                    ukraine_name = GENRE_TRANSLATIONS[genre.name]
                    self.stdout.write(f"Using predefined translation for '{genre.name}': {ukraine_name}")
                else:
                    # Otherwise use translation service
                    ukraine_name = TranslationService.translate_text(genre.name, 'en', 'uk')
                    self.stdout.write(f"Translated '{genre.name}' -> '{ukraine_name}'")
                
                genre.name_ukrainian = ukraine_name
                genre.save(update_fields=['name_ukrainian'])
                translated_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error translating genre '{genre.name}': {str(e)}"))
                failed_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"Translation complete! Successfully translated {translated_count} genres. "
            f"Failed: {failed_count}"
        ))
