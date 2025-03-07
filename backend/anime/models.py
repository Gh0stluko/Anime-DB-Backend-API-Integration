from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True, max_length=255)  # Increased length

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Жанр'
        verbose_name_plural = 'Жанри'

class DubbingStudio(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='dubbing_studios/', blank=True, null=True)
    established_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Студія дубляжу'
        verbose_name_plural = 'Студії дубляжу'

class Anime(models.Model):
    STATUS_CHOICES = [
        ('ongoing', 'Онгоінг'),
        ('completed', 'Завершено'),
        ('announced', 'Анонсовано'),
        ('dropped', 'Покинуто'),
    ]
    
    TYPE_CHOICES = [
        ('tv', 'TV Серіал'),
        ('movie', 'Фільм'),
        ('ova', 'OVA'),
        ('ona', 'ONA'),
        ('special', 'Спешл'),
    ]
    
    SEASON_CHOICES = [
        ('winter', 'Зима'),
        ('spring', 'Весна'),
        ('summer', 'Літо'),
        ('fall', 'Осінь'),
    ]

    # Titles
    title_original = models.CharField('Оригінальна назва', max_length=255)
    title_english = models.CharField('Англійська назва', max_length=255, blank=True)
    title_japanese = models.CharField('Японська назва', max_length=255, blank=True)
    title_ukrainian = models.CharField('Українська назва', max_length=255)
    
    # Slugs and IDs
    slug = models.SlugField(unique=True, blank=True, max_length=255)  # Increased length
    mal_id = models.IntegerField('MyAnimeList ID', blank=True, null=True)
    
    # Details
    description = models.TextField('Опис')
    
    # Changed from ImageField to URLField
    poster_url = models.URLField('URL постера', max_length=500, blank=True)
    banner_url = models.URLField('URL банера', max_length=500, blank=True)
    
    # Keeping these for backward compatibility, but will be deprecated
    poster = models.ImageField(upload_to='anime/posters/', blank=True, null=True)
    banner = models.ImageField(upload_to='anime/banners/', blank=True, null=True)
    
    youtube_trailer = models.CharField('YouTube трейлер', max_length=255, blank=True)
    
    # Classification
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='ongoing')
    type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='tv')
    genres = models.ManyToManyField(Genre, related_name='anime', verbose_name='Жанри')
    
    # Metadata
    year = models.IntegerField('Рік виходу')
    season = models.CharField('Сезон', max_length=10, choices=SEASON_CHOICES, blank=True, null=True)
    episodes_count = models.IntegerField('Кількість епізодів', default=0)
    rating = models.FloatField('Рейтинг', validators=[MinValueValidator(0), MaxValueValidator(10)], default=0)
    
    # Ukrainian specific
    dubbing_studios = models.ManyToManyField(DubbingStudio, related_name='anime', blank=True, verbose_name='Студії дубляжу')
    has_ukrainian_dub = models.BooleanField('Українська озвучка', default=False)
    ukrainian_release_date = models.DateField('Дата виходу українською', blank=True, null=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If migrating from old format to new, ensure poster_url contains a value
        if not hasattr(self, 'poster_url'):
            self.poster_url = ''
            
        if not hasattr(self, 'banner_url'):
            self.banner_url = ''
            
        # If we have a poster image but no URL, try to get URL from the image
        if not self.poster_url and self.poster and hasattr(self.poster, 'url'):
            self.poster_url = self.poster.url
            
        # If we have a banner image but no URL, try to get URL from the image
        if not self.banner_url and self.banner and hasattr(self.banner, 'url'):
            self.banner_url = self.banner.url
            
        # Add truncation for slug to prevent errors with very long titles
        if not self.slug:
            base_slug = slugify(self.title_ukrainian)
            # Ensure the slug is not too long (max 250 chars to be safe)
            if len(base_slug) > 250:
                base_slug = base_slug[:250]
            self.slug = base_slug
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title_ukrainian

    class Meta:
        ordering = ['-year', 'title_ukrainian']
        verbose_name = 'Аніме'
        verbose_name_plural = 'Аніме'

class Episode(models.Model):
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='episodes')
    number = models.IntegerField('Номер епізоду')
    title = models.CharField('Назва епізоду', max_length=255, blank=True)
    description = models.TextField('Опис', blank=True)
    duration = models.IntegerField('Тривалість (хв)')
    
    # Add thumbnail URL field
    thumbnail_url = models.URLField('URL мініатюри', max_length=500, blank=True)
    thumbnail = models.ImageField(upload_to='episodes/thumbnails/', blank=True, null=True)
    
    # Video sources - using URLs to external resources instead of storing files
    video_url_1080p = models.URLField('Відео 1080p', blank=True)
    video_url_720p = models.URLField('Відео 720p', blank=True)
    video_url_480p = models.URLField('Відео 480p', blank=True)
    
    # Ukrainian specific
    dubbing_studio = models.ForeignKey(DubbingStudio, on_delete=models.SET_NULL, null=True, blank=True, related_name='dubbed_episodes')
    
    # Release info
    release_date = models.DateField('Дата виходу', default=timezone.now)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # If migrating from old format to new
        if not hasattr(self, 'thumbnail_url'):
            self.thumbnail_url = ''
            
        # If we have a thumbnail image but no URL, try to get URL from the image
        if not self.thumbnail_url and self.thumbnail and hasattr(self.thumbnail, 'url'):
            self.thumbnail_url = self.thumbnail.url
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.anime.title_ukrainian} - Епізод {self.number}"
    
    class Meta:
        ordering = ['anime', 'number']
        verbose_name = 'Епізод'
        verbose_name_plural = 'Епізоди'
        unique_together = ['anime', 'number']

class AnimeScreenshot(models.Model):
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='screenshots')
    
    # Add URL field and keep image field for compatibility
    image_url = models.URLField('URL зображення', max_length=500, blank=True)
    image = models.ImageField(upload_to='anime/screenshots/', blank=True, null=True)
    
    description = models.CharField(max_length=255, blank=True)
    
    def save(self, *args, **kwargs):
        # If migrating from old format to new
        if not hasattr(self, 'image_url'):
            self.image_url = ''
            
        # If we have an image but no URL, try to get URL from the image
        if not self.image_url and self.image and hasattr(self.image, 'url'):
            self.image_url = self.image.url
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Скріншот для {self.anime.title_ukrainian}"
    
    class Meta:
        verbose_name = 'Скріншот'
        verbose_name_plural = 'Скріншоти'
