# Generated manually – 2026-01-31
# Changements :
#   - Commande : suppression du champ 'valide', ajout du champ 'statut'
#   - Ajout du modèle CommandeItem
#   - Suppression du modèle MenuItem (doublon)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion', '0005_remove_commande_items_remove_commande_user_and_more'),
    ]

    operations = [
        # 1) Supprimer le champ 'valide' sur Commande
        migrations.RemoveField(
            model_name='commande',
            name='valide',
        ),

        # 2) Ajouter le champ 'statut' sur Commande
        migrations.AddField(
            model_name='commande',
            name='statut',
            field=models.CharField(
                choices=[
                    ('en_attente', 'En attente'),
                    ('servie', 'Servie'),
                    ('payee', 'Payée'),
                ],
                default='en_attente',
                max_length=20,
            ),
        ),

        # 3) Créer le modèle CommandeItem
        migrations.CreateModel(
            name='CommandeItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantite', models.PositiveIntegerField(default=1)),
                ('prix_unitaire', models.DecimalField(decimal_places=2, max_digits=10)),
                ('commande', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='gestion.commande',
                )),
                ('plat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='gestion.plat',
                )),
            ],
        ),

        # 4) Ajouter unique_together sur PanierItem
        migrations.AlterUniqueTogether(
            name='panieritem',
            unique_together={('tablette', 'plat')},
        ),

        # 5) Supprimer le modèle MenuItem (doublon avec Plat)
        migrations.DeleteModel(
            name='MenuItem',
        ),
    ]