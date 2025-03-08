from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('anime', '0003_add_image_url_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Season',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.IntegerField(verbose_name='Номер сезону')),
                ('title', models.CharField(blank=True, max_length=255, verbose_name='Назва сезону')),
                ('year', models.IntegerField(blank=True, null=True, verbose_name='Рік виходу')),
                ('episodes_count', models.IntegerField(default=0, verbose_name='Кількість епізодів')),
                ('anime', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seasons', to='anime.anime')),
            ],
            options={
                'verbose_name': 'Сезон',
                'verbose_name_plural': 'Сезони',
                'ordering': ['anime', 'number'],
                'unique_together': {('anime', 'number')},
            },
        ),
        migrations.AddField(
            model_name='episode',
            name='absolute_number',
            field=models.IntegerField(blank=True, null=True, verbose_name='Загальний номер'),
        ),
        migrations.AddField(
            model_name='episode',
            name='season',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='episodes', to='anime.season'),
        ),
        migrations.AlterUniqueTogether(
            name='episode',
            unique_together={('anime', 'season', 'number')},
        ),
    ]
