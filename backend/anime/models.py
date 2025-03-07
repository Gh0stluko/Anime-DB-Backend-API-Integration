from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True)

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
    title_ukrainian = models.CharField('Українська назва', max_length=255)
    
    # Slugs and IDs
    slug = models.SlugField(unique=True, blank=True)
    mal_id = models.IntegerField('MyAnimeList ID', blank=True, null=True)
    
    # Details
    description = models.TextField('Опис')
    poster = models.ImageField(upload_to='anime/posters/')
    banner = models.ImageField(upload_to='anime/banners/', blank=True, null=True)
    
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
        if not self.slug:
            self.slug = slugify(self.title_ukrainian)
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
    
    def __str__(self):
        return f"{self.anime.title_ukrainian} - Епізод {self.number}"
    
    class Meta:
        ordering = ['anime', 'number']
        verbose_name = 'Епізод'
        verbose_name_plural = 'Епізоди'
        unique_together = ['anime', 'number']

class AnimeScreenshot(models.Model):
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='screenshots')
    image = models.ImageField(upload_to='anime/screenshots/')
    description = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"Скріншот для {self.anime.title_ukrainian}"
    
    class Meta:
        verbose_name = 'Скріншот'
        verbose_name_plural = 'Скріншоти'
