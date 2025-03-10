from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.db.models import Count, Q
from django.utils import timezone
import json
from datetime import timedelta

from .models import (
    Anime, Episode, Genre, DubbingStudio, AnimeScreenshot,
    UpdateStrategy, APIUsageStatistics, APIRequestLog, UpdateLog
)
from .tasks import (
    fetch_top_anime_task, fetch_seasonal_anime_task, fetch_anime_details_task,
    update_anime_screenshots_task, update_anime_episodes_task, 
    update_anime_by_priority_task, recalculate_update_priorities_task,
    reschedule_updates_task
)

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1
    fields = ('number', 'title', 'duration', 'release_date', 'dubbing_studio', 'thumbnail_url', 'display_thumbnail_preview')
    readonly_fields = ('display_thumbnail_preview',)
    show_change_link = True  # Add link to edit the episode
    
    # Make episodes collapsible and collapsed by default
    classes = ('collapse',)
    
    # Control how many episodes are shown initially
    max_num = 500
    per_page = 20
    
    def display_thumbnail_preview(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" width="80" height="45" style="object-fit: cover;" />', obj.thumbnail_url)
        return "Немає мініатюри"
    display_thumbnail_preview.short_description = 'Превью'

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
    list_display = ('name', 'name_ukrainian', 'slug')
    search_fields = ('name', 'name_ukrainian')
    prepopulated_fields = {'slug': ('name',)}
    fields = ('name', 'name_ukrainian', 'description', 'slug')
    actions = ['translate_to_ukrainian']
    
    def translate_to_ukrainian(self, request, queryset):
        from anime.services.translation_service import TranslationService
        
        translated_count = 0
        for genre in queryset.filter(name_ukrainian__exact=''):
            try:
                ukrainian_name = TranslationService.translate_text(genre.name, 'en', 'uk')
                genre.name_ukrainian = ukrainian_name
                genre.save(update_fields=['name_ukrainian'])
                translated_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Помилка перекладу жанру '{genre.name}': {str(e)}",
                    messages.ERROR
                )
        
        self.message_user(
            request, 
            f"Успішно перекладено {translated_count} жанрів на українську мову.", 
            messages.SUCCESS
        )
    
    translate_to_ukrainian.short_description = "Перекласти вибрані жанри на українську"

@admin.register(DubbingStudio)
class DubbingStudioAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'established_date')
    search_fields = ('name',)
    list_filter = ('established_date',)

@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ('title_ukrainian', 'display_japanese_title', 'year', 'status', 'type', 'episodes_count', 'has_ukrainian_dub', 'display_poster', 'rating', 'update_priority', 'next_update')
    list_filter = ('status', 'type', 'year', 'has_ukrainian_dub', 'dubbing_studios', 'update_priority')
    search_fields = ('title_ukrainian', 'title_original', 'title_english', 'title_japanese')
    prepopulated_fields = {'slug': ('title_ukrainian',)}
    readonly_fields = (
        'created_at', 'updated_at', 'display_trailer', 'display_poster_preview', 
        'display_banner_preview', 'display_screenshots_gallery', 'episodes_summary',
        'display_update_history', 'last_full_update', 'last_metadata_update', 
        'last_episodes_update', 'last_images_update'
    )
    filter_horizontal = ('genres', 'dubbing_studios')
    inlines = [ScreenshotInline, EpisodeInline]
    
    # Add actions buttons to the changelist view
    change_list_template = 'admin/anime/anime_changelist.html'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('genres', 'dubbing_studios')
    
    def next_update(self, obj):
        """Display when the next update is scheduled"""
        if not obj.next_update_scheduled:
            return "-"
            
        now = timezone.now()
        if obj.next_update_scheduled < now:
            return "Зараз"
            
        days = (obj.next_update_scheduled - now).days
        hours = int((obj.next_update_scheduled - now).seconds / 3600)
        
        if days > 0:
            return f"{days}д {hours}г"
        else:
            return f"{hours}г"
    next_update.short_description = 'Наступне оновлення'
    
    def display_update_history(self, obj):
        """Display update history for an anime"""
        updates = obj.update_logs.all().order_by('-created_at')[:10]
        
        if not updates:
            return "Немає історії оновлень"
            
        html = '<div class="update-history-container">'
        html += '<table style="width:100%; border-collapse:collapse;">'
        html += '<thead><tr>'
        html += '<th style="background-color:#f2f2f2; padding:8px; text-align:left; border-bottom:1px solid #ddd;">Дата</th>'
        html += '<th style="background-color:#f2f2f2; padding:8px; text-align:left; border-bottom:1px solid #ddd;">Тип</th>'
        html += '<th style="background-color:#f2f2f2; padding:8px; text-align:left; border-bottom:1px solid #ddd;">Статус</th>'
        html += '<th style="background-color:#f2f2f2; padding:8px; text-align:left; border-bottom:1px solid #ddd;">Помилка</th>'
        html += '</tr></thead><tbody>'
        
        update_types = {
            'full': 'Повне',
            'metadata': 'Метадані',
            'episodes': 'Епізоди',
            'images': 'Зображення'
        }
        
        for update in updates:
            status_class = 'success' if update.success else 'error'
            bg_color = '#d4edda' if update.success else '#f8d7da'
            status_text = 'Успішно' if update.success else 'Помилка'
            
            html += f'<tr>'
            html += f'<td style="padding:8px; text-align:left; border-bottom:1px solid #ddd; background-color:{bg_color};">{update.created_at.strftime("%d.%m.%Y %H:%M")}</td>'
            html += f'<td style="padding:8px; text-align:left; border-bottom:1px solid #ddd; background-color:{bg_color};">{update_types.get(update.update_type, update.update_type)}</td>'
            html += f'<td style="padding:8px; text-align:left; border-bottom:1px solid #ddd; background-color:{bg_color};">{status_text}</td>'
            
            error_message = update.error_message
            if error_message and len(error_message) > 50:
                error_message = error_message[:50] + '...'
                
            html += f'<td style="padding:8px; text-align:left; border-bottom:1px solid #ddd; background-color:{bg_color};">{error_message}</td>'
            html += '</tr>'
            
        html += '</tbody></table></div>'
        
        return format_html(html)
    display_update_history.short_description = 'Історія оновлень'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fetch_top_anime/', self.admin_site.admin_view(self.fetch_top_anime), name='fetch-top-anime'),
            path('fetch_seasonal_anime/', self.admin_site.admin_view(self.fetch_seasonal_anime), name='fetch-seasonal-anime'),
            path('update_screenshots/', self.admin_site.admin_view(self.update_screenshots), name='update-screenshots'),
            path('update_episodes/', self.admin_site.admin_view(self.update_episodes), name='update-episodes'),
            path('update_priority_anime/', self.admin_site.admin_view(self.update_priority_anime), name='update-priority-anime'),
            path('recalculate_priorities/', self.admin_site.admin_view(self.recalculate_priorities), name='recalculate-priorities'),
            path('api_usage_stats/', self.admin_site.admin_view(self.api_usage_stats), name='api-usage-stats'),
            path('update_stats/', self.admin_site.admin_view(self.update_stats), name='update-stats'),
            path('force-update-scheduled/',
                 self.admin_site.admin_view(self.force_update_scheduled),
                 name='force-update-scheduled'),
        ]
        return custom_urls + urls
    
    def fetch_top_anime(self, request):
        task = fetch_top_anime_task.delay(1, 25)
        self.message_user(request, "Завдання на отримання топ аніме з обох джерел було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def fetch_seasonal_anime(self, request):
        task = fetch_seasonal_anime_task.delay()
        self.message_user(request, "Завдання на отримання сезонного аніме з обох джерел було запущено. ID завдання: {}".format(task.id), messages.SUCCESS)
        return HttpResponseRedirect("../")
    
    def update_screenshots(self, request):
        anime_count = Anime.objects.annotate(
            screenshots_count=Count('screenshots')
        ).filter(screenshots_count__lt=5).count()
        
        task = update_anime_screenshots_task.delay(count=20)
        
        self.message_user(
            request, 
            f"Завдання на оновлення скріншотів запущено для аніме з малою кількістю зображень. "
            f"Знайдено {anime_count} аніме з менш ніж 5 скріншотами. ID завдання: {task.id}", 
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
        
    def update_episodes(self, request):
        ongoing_count = Anime.objects.filter(status='ongoing').count()
        
        task = update_anime_episodes_task.delay(count=20)
        
        self.message_user(
            request,
            f"Завдання на оновлення епізодів запущено. Знайдено {ongoing_count} аніме зі статусом 'ongoing'. ID завдання: {task.id}",
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
        
    def update_priority_anime(self, request):
        task = update_anime_by_priority_task.delay(batch_size=20, update_type='full')
        
        self.message_user(
            request,
            f"Завдання на оновлення аніме за пріоритетом запущено. ID завдання: {task.id}",
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
        
    def recalculate_priorities(self, request):
        task = recalculate_update_priorities_task.delay()
        reschedule_task = reschedule_updates_task.delay()
        
        self.message_user(
            request,
            f"Завдання на перерахунок пріоритетів запущено. ID завдання: {task.id}",
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
    
    def api_usage_stats(self, request):
        from django.shortcuts import render
        
        jikan_stats = APIUsageStatistics.objects.filter(api_name="Jikan").first()
        anilist_stats = APIUsageStatistics.objects.filter(api_name="Anilist").first()
        
        # Get recent requests
        recent_requests = APIRequestLog.objects.all().order_by('-created_at')[:100]
        
        # Calculate daily stats
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        jikan_today = APIRequestLog.objects.filter(
            api_name="Jikan",
            created_at__date=today
        ).count()
        
        jikan_yesterday = APIRequestLog.objects.filter(
            api_name="Jikan",
            created_at__date=yesterday
        ).count()
        
        anilist_today = APIRequestLog.objects.filter(
            api_name="Anilist",
            created_at__date=today
        ).count()
        
        anilist_yesterday = APIRequestLog.objects.filter(
            api_name="Anilist",
            created_at__date=yesterday
        ).count()
        
        # Calculate success rates
        jikan_success = APIRequestLog.objects.filter(
            api_name="Jikan",
            success=True
        ).count()
        
        jikan_total = max(1, APIRequestLog.objects.filter(
            api_name="Jikan"
        ).count())
        
        anilist_success = APIRequestLog.objects.filter(
            api_name="Anilist",
            success=True
        ).count()
        
        anilist_total = max(1, APIRequestLog.objects.filter(
            api_name="Anilist"
        ).count())
        
        jikan_success_rate = (jikan_success / jikan_total * 100)
        anilist_success_rate = (anilist_success / anilist_total * 100)
        
        # Get active strategy
        active_strategy = UpdateStrategy.objects.filter(is_active=True).first()
        
        context = {
            'jikan_stats': jikan_stats,
            'anilist_stats': anilist_stats,
            'recent_requests': recent_requests,
            'jikan_today': jikan_today,
            'jikan_yesterday': jikan_yesterday,
            'anilist_today': anilist_today,
            'anilist_yesterday': anilist_yesterday,
            'jikan_success_rate': jikan_success_rate,
            'anilist_success_rate': anilist_success_rate,
            'active_strategy': active_strategy,
            'title': 'API Usage Statistics',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/anime/api_usage_stats.html', context)
    
    def update_stats(self, request):
        from django.shortcuts import render
        
        # Get update statistics
        total_updates = UpdateLog.objects.count()
        successful_updates = UpdateLog.objects.filter(success=True).count()
        failed_updates = UpdateLog.objects.filter(success=False).count()
        
        # Success rate
        if total_updates > 0:
            success_rate = (successful_updates / total_updates) * 100
        else:
            success_rate = 0
        
        # Updates by type
        updates_by_type = {}
        for update_type in ['full', 'metadata', 'episodes', 'images']:
            count = UpdateLog.objects.filter(update_type=update_type).count()
            updates_by_type[update_type] = count
        
        # Recent updates
        recent_updates = UpdateLog.objects.select_related('anime').order_by('-created_at')[:100]
        
        # Updates by day
        today = timezone.now().date()
        updates_by_day = []
        
        for i in range(7):
            day = today - timedelta(days=i)
            count = UpdateLog.objects.filter(created_at__date=day).count()
            updates_by_day.append({
                'date': day.strftime('%d.%m'),
                'count': count
            })
        
        # Upcoming updates
        upcoming_updates = Anime.objects.filter(
            next_update_scheduled__gte=timezone.now()
        ).order_by('next_update_scheduled')[:20]
        
        # Need immediate updates
        need_updates = Anime.objects.filter(
            Q(next_update_scheduled__lte=timezone.now()) | Q(next_update_scheduled__isnull=True)
        ).order_by('-update_priority')[:20]
        
        context = {
            'total_updates': total_updates,
            'successful_updates': successful_updates,
            'failed_updates': failed_updates,
            'success_rate': success_rate,
            'updates_by_type': updates_by_type,
            'recent_updates': recent_updates,
            'updates_by_day': updates_by_day,
            'upcoming_updates': upcoming_updates,
            'need_updates': need_updates,
            'title': 'Update Statistics',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/anime/update_stats.html', context)
        
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
    
    def episodes_summary(self, obj):
        """Display a summary of episodes with links to view/edit them"""
        episodes = obj.episodes.all().order_by('number')
        count = episodes.count()
        
        if count == 0:
            return "Немає епізодів"
            
        html = f'<p>Всього епізодів: <strong>{count}</strong></p>'
        html += '<div style="margin-bottom: 10px;">'
        
        # Add quick stats
        filler_count = obj.episodes.filter(is_filler=True).count()
        recap_count = obj.episodes.filter(is_recap=True).count()
        with_thumbnail = obj.episodes.exclude(thumbnail_url='').count()
        
        if filler_count:
            html += f'<span style="margin-right: 15px;"><b>Філлерів:</b> {filler_count}</span>'
        if recap_count:
            html += f'<span style="margin-right: 15px;"><b>Рекапів:</b> {recap_count}</span>'
        html += f'<span><b>З мініатюрами:</b> {with_thumbnail}</span>'
        
        html += '</div>'
        
        # Add button to view all episodes separately
        admin_url = f"/admin/anime/episode/?anime__id__exact={obj.id}"
        html += f'<a href="{admin_url}" class="button" target="_blank">Переглянути всі епізоди окремо</a>'
        
        return format_html(html)
    episodes_summary.short_description = 'Інформація про епізоди'
    
    fieldsets = (
        ('Назви', {
            'fields': ('title_original', 'title_english', 'title_japanese', 'title_ukrainian', 'slug')
        }),
        ('Деталі', {
            'fields': ('description', 'poster_url', 'display_poster_preview', 'banner_url', 'display_banner_preview', 'youtube_trailer', 'display_trailer', 'genres')
        }),
        ('Епізоди', {
            'fields': ('episodes_summary',),
            'description': 'Інформація про епізоди аніме. Для перегляду повного списку епізодів, натисніть на "Епізоди" внизу сторінки'
        }),
        ('Скріншоти', {
            'fields': ('display_screenshots_gallery',),
        }),
        ('Класифікація', {
            'fields': ('status', 'type', 'year', 'season', 'episodes_count', 'duration_per_episode', 'rating')
        }),
        ('Українська локалізація', {
            'fields': ('has_ukrainian_dub', 'dubbing_studios', 'ukrainian_release_date')
        }),
        ('Статус оновлень', {
            'fields': ('update_priority', 'next_update_scheduled', 'last_full_update', 'last_metadata_update', 
                      'last_episodes_update', 'last_images_update', 'update_failures', 'display_update_history'),
            'classes': ('collapse',)
        }),
        ('Посилання', {
            'fields': ('mal_id',),
            'classes': ('collapse',)
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
    
    def display_japanese_title(self, obj):
        """Display Japanese title with proper font styling"""
        if obj.title_japanese:
            return mark_safe(f'<span lang="ja" style="font-family: \'Noto Sans JP\', sans-serif;">{obj.title_japanese}</span>')
        return "-"
    display_japanese_title.short_description = 'Японська назва'
    
    def force_update_scheduled(self, request):
        """Запуск примусового оновлення запланованих аніме"""
        from anime.tasks import force_update_scheduled_anime_task
        
        task = force_update_scheduled_anime_task.delay()
        
        self.message_user(
            request,
            f"Задачу примусового оновлення запланованих аніме запущено. ID завдання: {task.id}",
            messages.SUCCESS
        )
        return HttpResponseRedirect("../")
    
    class Media:
        css = {
            'all': ('https://fonts.googleapis.com/css2?family=Noto+Sans+JP&display=swap',)
        }
        js = ('admin/js/collapse.js',)  # Ensure collapse functionality is available

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'anime', 'release_date', 'duration', 'dubbing_studio', 'display_thumbnail')
    list_filter = ('anime', 'dubbing_studio', 'release_date', 'is_filler', 'is_recap')
    search_fields = ('anime__title_ukrainian', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'display_thumbnail_preview')
    
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
            'fields': ('anime',)
        }),
        ('Основна інформація', {
            'fields': ('number', 'absolute_number', 'title', 'title_japanese', 'title_romanji', 'description', 'duration', 'thumbnail_url', 'display_thumbnail_preview')
        }),
        ('Відео', {
            'fields': ('video_url_1080p', 'video_url_720p', 'video_url_480p')
        }),
        ('Додаткова інформація', {
            'fields': ('is_filler', 'is_recap', 'score')
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

@admin.register(UpdateStrategy)
class UpdateStrategyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'api_requests_per_minute', 'api_requests_per_day', 'batch_size')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Основна інформація', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Обмеження API', {
            'fields': ('api_requests_per_minute', 'api_requests_per_day')
        }),
        ('Частота оновлень', {
            'fields': ('ongoing_update_days', 'announced_update_days', 'completed_update_days')
        }),
        ('Налаштування пріоритетів', {
            'fields': ('ongoing_priority', 'popular_priority', 'recent_priority', 'old_priority')
        }),
        ('Оновлення пакетами', {
            'fields': ('batch_size',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        # If strategy was activated, recalculate priorities
        if obj.is_active:
            recalculate_update_priorities_task.delay()
            reschedule_updates_task.delay()
            messages.success(request, "Пріоритети оновлення будуть перераховані відповідно до нової стратегії.")

@admin.register(APIUsageStatistics)
class APIUsageStatisticsAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'requests_count', 'successful_requests', 'failed_requests', 'daily_count', 'is_rate_limited')
    list_filter = ('api_name', 'is_rate_limited')
    readonly_fields = ('api_name', 'requests_count', 'successful_requests', 'failed_requests', 
                       'last_request_at', 'daily_count', 'daily_reset_at', 'is_rate_limited', 'rate_limited_until')
    
    def has_add_permission(self, request):
        return False

@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'endpoint', 'success', 'response_code', 'created_at')
    list_filter = ('api_name', 'success', 'created_at')
    search_fields = ('endpoint', 'error_message')
    readonly_fields = ('api_name', 'endpoint', 'parameters', 'response_code', 'success', 
                      'error_message', 'created_at')
    
    def has_add_permission(self, request):
        return False

@admin.register(UpdateLog)
class UpdateLogAdmin(admin.ModelAdmin):
    list_display = ('anime', 'update_type', 'success', 'created_at')
    list_filter = ('update_type', 'success', 'created_at')
    search_fields = ('anime__title_ukrainian', 'anime__title_original', 'error_message')
    readonly_fields = ('anime', 'update_type', 'success', 'error_message', 'created_at')
    
    def has_add_permission(self, request):
        return False
