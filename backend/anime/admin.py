from django.contrib import admin
from django.utils.html import format_html
from .models import Anime, Episode, Genre, DubbingStudio, AnimeScreenshot

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1
    fields = ('number', 'title', 'duration', 'release_date', 'dubbing_studio')

class ScreenshotInline(admin.TabularInline):
    model = AnimeScreenshot
    extra = 1
    fields = ('image', 'description')

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
    list_display = ('title_ukrainian', 'year', 'status', 'type', 'episodes_count', 'has_ukrainian_dub', 'display_poster', 'rating')
    list_filter = ('status', 'type', 'year', 'has_ukrainian_dub', 'dubbing_studios')
    search_fields = ('title_ukrainian', 'title_original', 'title_english')
    prepopulated_fields = {'slug': ('title_ukrainian',)}
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('genres', 'dubbing_studios')
    inlines = [EpisodeInline, ScreenshotInline]
    fieldsets = (
        ('Назви', {
            'fields': ('title_original', 'title_english', 'title_ukrainian', 'slug')
        }),
        ('Деталі', {
            'fields': ('description', 'poster', 'banner', 'genres')
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
        if obj.poster:
            return format_html('<img src="{}" width="50" height="70" />', obj.poster.url)
        return "Немає постера"
    display_poster.short_description = 'Постер'

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
    
    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="60" />', obj.image.url)
        return "Немає зображення"
    display_image.short_description = 'Скріншот'
