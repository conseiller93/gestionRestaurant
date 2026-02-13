from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion', '0012_alter_caisse_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='tablette',
            name='qr_password',
            field=models.CharField(
                max_length=128,
                blank=True,
                null=True,
                help_text='Mot de passe en clair pour générer les QR Codes (usage interne uniquement)'
            ),
        ),
    ]