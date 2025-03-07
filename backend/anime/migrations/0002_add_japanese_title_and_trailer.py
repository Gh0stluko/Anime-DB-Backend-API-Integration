from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anime', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='anime',
            name='title_japanese',
            field=models.CharField(blank=True, max_length=255, verbose_name='Японська назва'),
        ),
        migrations.AddField(
            model_name='anime',
            name='youtube_trailer',
            field=models.CharField(blank=True, max_length=255, verbose_name='YouTube трейлер'),
        ),
    ]
