from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def move_guests_into_families(apps, schema_editor):
    User = apps.get_model('guests', 'User')
    Family = apps.get_model('guests', 'Family')
    Guest = apps.get_model('guests', 'Guest')
    database = schema_editor.connection.alias
    for user_id in User.objects.using(database).values_list('pk', flat=True).iterator():
        family, _ = Family.objects.using(database).get_or_create(responsible_id=user_id)
        Guest.objects.using(database).filter(owner_id=user_id).update(family_id=family.pk)


class Migration(migrations.Migration):
    dependencies = [('guests', '0002_alter_guest_attendance')]
    operations = [
        migrations.AlterModelOptions(name='user', options={'verbose_name': 'responsável da família', 'verbose_name_plural': 'responsáveis das famílias'}),
        migrations.CreateModel(name='Family', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(blank=True, help_text='Opcional. Exemplo: Família Silva.', max_length=150, verbose_name='nome da família')),
            ('responsible', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='family', to=settings.AUTH_USER_MODEL, verbose_name='responsável da família')),
        ], options={'verbose_name': 'família', 'verbose_name_plural': 'famílias'}),
        migrations.AddField(model_name='guest', name='family', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='guests', to='guests.family', verbose_name='família')),
        migrations.RunPython(move_guests_into_families),
        migrations.AlterField(model_name='guest', name='family', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guests', to='guests.family', verbose_name='família')),
        migrations.RemoveField(model_name='guest', name='owner'),
    ]
