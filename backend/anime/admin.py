from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from .models import Anime, Episode, Genre, DubbingStudio, AnimeScreenshot
from .tasks import fetch_top_anime_task, fetch_seasonal_anime_task, fetch_anime_details_task, fetch_popular_anilist_anime_task

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1
    fields = ('number', 'title', 'duration', 'release_date', 'dubbing_studio')

class ScreenshotInline(admin.TabularInline):
    model = AnimeScreenshot
    extra = 1
    # Updated to use image_url instead of image
    fields = ('image_url', 'description')

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
    list_display = ('title_ukrainian', 'title_japanese', 'year', 'status', 'type', 'episodes_count', 'has_ukrainian_dub', 'display_poster', 'rating')
    list_filter = ('status', 'type', 'year', 'has_ukrainian_dub', 'dubbing_studios')
    search_fields = ('title_ukrainian', 'title_original', 'title_english', 'title_japanese')
    prepopulated_fields = {'slug': ('title_ukrainian',)}
    readonly_fields = ('created_at', 'updated_at', 'display_trailer', 'display_poster_preview', 'display_banner_preview')
    filter_horizontal = ('genres', 'dubbing_studios')
    inlines = [EpisodeInline, ScreenshotInline]
    
    # Add actions buttons to the changelist view
    change_list_template = 'admin/anime/anime_changelist.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fetch_top_anime/', self.admin_site.admin_view(self.fetch_top_anime), name='fetch-top-anime'),
            path('fetch_seasonal_anime/', self.admin_site.admin_view(self.fetch_seasonal_anime), name='fetch-seasonal-anime'),
            path('fetch_popular_anilist/', self.admin_site.admin_view(self.fetch_popular_anilist), name='fetch-popular-anilist'),
        ]
        return custom_urls + urls
    
    def fetch_top_anime(self, request):
        # Call the Celery task
        task = fetch_top_anime_task.delay(2, 25)
        self.message_user(request, "Завдання на отримання топ аніме було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def fetch_seasonal_anime(self, request):
        # Call the Celery task
        task = fetch_seasonal_anime_task.delay()
        self.message_user(request, "Завдання на отримання сезонного аніме було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def fetch_popular_anilist(self, request):
        # Call the Celery task
        task = fetch_popular_anilist_anime_task.delay(1, 50)
        self.message_user(request, "Завдання на отримання популярного аніме з Anilist було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    fieldsets = (
        ('Назви', {
            'fields': ('title_original', 'title_english', 'title_japanese', 'title_ukrainian', 'slug')
        }),
        ('Деталі', {
            'fields': ('description', 'poster_url', 'display_poster_preview', 'banner_url', 'display_banner_preview', 'youtube_trailer', 'display_trailer', 'genres')
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

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'release_date', 'duration', 'dubbing_studio')
    list_filter = ('anime', 'dubbing_studio', 'release_date')
    search_fields = ('anime__title_ukrainian', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Основна інформація', {
            'fields': ('anime', 'number', 'title', 'description', 'duration', 'thumbnail')
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
    list_display = ('anime', 'description', 'display_image')
    search_fields = ('anime__title_ukrainian', 'description')
    list_filter = ('anime',)
    # Add image_url to form fields and make it the primary field
    fields = ('anime', 'image_url', 'description', 'image')
    
    def display_image(self, obj):
        """Display image from URL or file, with safety checks"""
        try:
            if hasattr(obj, 'image_url') and obj.image_url:
                return format_html('<img src="{}" width="100" height="60" />', obj.image_url)
            elif hasattr(obj, 'image') and obj.image and hasattr(obj.image, 'url'):
                return format_html('<img src="{}" width="100" height="60" />', obj.image.url)
        except Exception as e:
            return f"Помилка: {str(e)}"
        return "Немає зображення"
    display_image.short_description = 'Скріншот'
