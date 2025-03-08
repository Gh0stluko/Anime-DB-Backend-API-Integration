from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.db.models import Count
from .models import Anime, Episode, Genre, DubbingStudio, AnimeScreenshot, Season
from .tasks import fetch_top_anime_task, fetch_seasonal_anime_task, fetch_anime_details_task

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1
    fields = ('number', 'title', 'duration', 'release_date', 'dubbing_studio', 'thumbnail_url', 'display_thumbnail_preview')
    readonly_fields = ('display_thumbnail_preview',)
    
    def display_thumbnail_preview(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" width="80" height="45" style="object-fit: cover;" />', obj.thumbnail_url)
        return "Немає мініатюри"
    display_thumbnail_preview.short_description = 'Превью'

class SeasonInline(admin.TabularInline):
    model = Season
    extra = 1
    fields = ('number', 'title', 'year', 'episodes_count')
    readonly_fields = ('episodes_count',)

class ScreenshotInline(admin.TabularInline):
    model = AnimeScreenshot
    extra = 1
    fields = ('image_url', 'description', 'display_screenshot_preview')
    readonly_fields = ('display_screenshot_preview',)
    
    def display_screenshot_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" width="120" height="68" style="object-fit: cover;" />', obj.image_url)
        elif obj.image and hasattr(obj.image, 'url'):
            return format_html('<img src="{}" width="120" height="68" style="object-fit: cover;" />', obj.image.url)
        return "Немає зображення"
    display_screenshot_preview.short_description = 'Превью'

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(DubbingStudio)
class DubbingStudioAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'established_date')
    search_fields = ('name',)
    list_filter = ('established_date',)

@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ('title_ukrainian', 'title_japanese', 'year', 'status', 'type', 'episodes_count', 'has_ukrainian_dub', 'display_poster', 'rating', 'seasons_count')
    list_filter = ('status', 'type', 'year', 'has_ukrainian_dub', 'dubbing_studios')
    search_fields = ('title_ukrainian', 'title_original', 'title_english', 'title_japanese')
    prepopulated_fields = {'slug': ('title_ukrainian',)}
    readonly_fields = ('created_at', 'updated_at', 'display_trailer', 'display_poster_preview', 'display_banner_preview', 'display_screenshots_gallery')
    filter_horizontal = ('genres', 'dubbing_studios')
    inlines = [SeasonInline, ScreenshotInline]
    
    # Add actions buttons to the changelist view
    change_list_template = 'admin/anime/anime_changelist.html'
    
    def seasons_count(self, obj):
        return obj.seasons.count()
    seasons_count.short_description = 'Сезони'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(seasons_count=Count('seasons', distinct=True))
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fetch_top_anime/', self.admin_site.admin_view(self.fetch_top_anime), name='fetch-top-anime'),
            path('fetch_seasonal_anime/', self.admin_site.admin_view(self.fetch_seasonal_anime), name='fetch-seasonal-anime'),
        ]
        return custom_urls + urls
    
    def fetch_top_anime(self, request):
        # Call the Celery task (з більшим лімітом для отримання більше аніме)
        task = fetch_top_anime_task.delay(1, 25)
        self.message_user(request, "Завдання на отримання топ аніме з обох джерел було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def fetch_seasonal_anime(self, request):
        # Call the Celery task
        task = fetch_seasonal_anime_task.delay()
        self.message_user(request, "Завдання на отримання сезонного аніме з обох джерел було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def update_screenshots(self, request):
        """Запускає задачу оновлення скріншотів для аніме з найменшою кількістю скріншотів"""
        # Отримуємо кількість аніме без скріншотів
        anime_count = Anime.objects.annotate(
            screenshots_count=models.Count('screenshots')
        ).filter(screenshots_count__lt=5).count()
        
        # Запускаємо задачу для аніме з найменшою кількістю скріншотів (максимум 20 аніме)
        task = update_anime_screenshots_task.delay(count=20)
        
        self.message_user(
            request, 
            f"Завдання на оновлення скріншотів запущено для аніме з малою кількістю зображень. "
            f"Знайдено {anime_count} аніме з менш ніж 5 скріншотами. ID завдання: {task.id}", 
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
    
    def display_screenshots_gallery(self, obj):
        screenshots = obj.screenshots.all()
        if screenshots:
            html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
            for screenshot in screenshots:
                if screenshot.display_image():
                    html += f'<div style="margin-bottom: 10px;"><img src="{screenshot.display_image()}" width="200" style="max-height: 150px; object-fit: cover;" /><br/>{screenshot.description}</div>'
            html += '</div>'
            return format_html(html)
        return "Немає скріншотів для цього аніме"
    display_screenshots_gallery.short_description = 'Галерея скріншотів'
    
    fieldsets = (
        ('Назви', {
            'fields': ('title_original', 'title_english', 'title_japanese', 'title_ukrainian', 'slug')
        }),
        ('Деталі', {
            'fields': ('description', 'poster_url', 'display_poster_preview', 'banner_url', 'display_banner_preview', 'youtube_trailer', 'display_trailer', 'genres')
        }),
        ('Скріншоти', {
            'fields': ('display_screenshots_gallery',),
        }),
        ('Класифікація', {
            'fields': ('status', 'type', 'year', 'season', 'episodes_count', 'rating')
        }),
        ('Українська локалізація', {
            'fields': ('has_ukrainian_dub', 'dubbing_studios', 'ukrainian_release_date')
        }),
        ('Посилання', {
            'fields': ('mal_id',)
        }),
        ('Службова інформація', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def display_poster(self, obj):
        """Display poster from URL or file, with safety checks"""
        try:
            if hasattr(obj, 'poster_url') and obj.poster_url:
                return format_html('<img src="{}" width="50" height="70" />', obj.poster_url)
            elif hasattr(obj, 'poster') and obj.poster and hasattr(obj.poster, 'url'):
                return format_html('<img src="{}" width="50" height="70" />', obj.poster.url)
        except Exception as e:
            return f"Помилка: {str(e)}"
        return "Немає постера"
    display_poster.short_description = 'Постер'
    
    def display_poster_preview(self, obj):
        """Preview poster with safety checks"""
        try:
            if hasattr(obj, 'poster_url') and obj.poster_url:
                return format_html('<img src="{}" width="200" /><br>URL: {}', obj.poster_url, obj.poster_url)
            elif hasattr(obj, 'poster') and obj.poster and hasattr(obj.poster, 'url'):
                return format_html('<img src="{}" width="200" /><br>URL: {}', obj.poster.url, obj.poster.url)
        except Exception as e:
            return f"Помилка: {str(e)}"
        return "Немає URL постера"
    display_poster_preview.short_description = 'Перегляд постера'
    
    def display_banner_preview(self, obj):
        """Preview banner with safety checks"""
        try:
            if hasattr(obj, 'banner_url') and obj.banner_url:
                return format_html('<img src="{}" width="400" /><br>URL: {}', obj.banner_url, obj.banner_url)
            elif hasattr(obj, 'banner') and obj.banner and hasattr(obj.banner, 'url'):
                return format_html('<img src="{}" width="400" /><br>URL: {}', obj.banner.url, obj.banner.url)
        except Exception as e:
            return f"Помилка: {str(e)}"
        return "Немає URL банера"
    display_banner_preview.short_description = 'Перегляд банера'
    
    def display_trailer(self, obj):
        try:
            if hasattr(obj, 'youtube_trailer') and obj.youtube_trailer:
                return format_html('<iframe width="560" height="315" src="https://www.youtube.com/embed/{}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>', obj.youtube_trailer)
        except Exception as e:
            return f"Помилка: {str(e)}"
        return "Немає трейлера"
    display_trailer.short_description = 'Трейлер'

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'anime', 'number', 'year', 'episodes_count')
    list_filter = ('anime', 'year')
    search_fields = ('anime__title_ukrainian', 'title')
    inlines = [EpisodeInline]

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'anime', 'season_info', 'release_date', 'duration', 'dubbing_studio', 'display_thumbnail')
    list_filter = ('anime', 'season', 'dubbing_studio', 'release_date')
    search_fields = ('anime__title_ukrainian', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'display_thumbnail_preview')
    
    def season_info(self, obj):
        if obj.season:
            return f"Сезон {obj.season.number}"
        return "-"
    season_info.short_description = 'Сезон'
    
    def display_thumbnail(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" width="80" height="45" style="object-fit: cover;" />', obj.thumbnail_url)
        return "Немає мініатюри"
    display_thumbnail.short_description = 'Мініатюра'
    
    def display_thumbnail_preview(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" width="320" /><br>URL: {}', obj.thumbnail_url, obj.thumbnail_url)
        return "Немає мініатюри"
    display_thumbnail_preview.short_description = 'Перегляд мініатюри'
    
    fieldsets = (
        ('Зв\'язки', {
            'fields': ('anime', 'season')
        }),
        ('Основна інформація', {
            'fields': ('number', 'absolute_number', 'title', 'description', 'duration', 'thumbnail_url', 'display_thumbnail_preview')
        }),
        ('Відео', {
            'fields': ('video_url_1080p', 'video_url_720p', 'video_url_480p')
        }),
        ('Українська локалізація', {
            'fields': ('dubbing_studio',)
        }),
        ('Дати', {
            'fields': ('release_date', 'created_at', 'updated_at')
        }),
    )

@admin.register(AnimeScreenshot)
class AnimeScreenshotAdmin(admin.ModelAdmin):
    list_display = ('anime', 'description', 'display_image_preview')
    search_fields = ('anime__title_ukrainian', 'description')
    list_filter = ('anime',)
    fields = ('anime', 'image_url', 'description', 'display_image_preview')
    readonly_fields = ('display_image_preview',)
    
    def display_image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" width="200" style="max-height: 150px; object-fit: cover;" />', obj.image_url)
        elif obj.image and hasattr(obj.image, 'url'):
            return format_html('<img src="{}" width="200" style="max-height: 150px; object-fit: cover;" />', obj.image.url)
        return "Немає зображення"
    display_image_preview.short_description = 'Скріншот'
