from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anime', '0002_add_japanese_title_and_trailer'),
    ]

    operations = [
        migrations.AddField(
            model_name='anime',
            name='poster_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='URL постера'),
        ),
        migrations.AddField(
            model_name='anime',
            name='banner_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='URL банера'),
        ),
        migrations.AlterField(
            model_name='anime',
            name='poster',
            field=models.ImageField(blank=True, null=True, upload_to='anime/posters/'),
        ),
        migrations.AlterField(
            model_name='anime',
            name='banner',
            field=models.ImageField(blank=True, null=True, upload_to='anime/banners/'),
        ),
        migrations.AddField(
            model_name='animescreenshot',
            name='image_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='URL зображення'),
        ),
        migrations.AlterField(
            model_name='animescreenshot',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='anime/screenshots/'),
        ),
        migrations.AddField(
            model_name='episode',
            name='thumbnail_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='URL мініатюри'),
        ),
    ]
