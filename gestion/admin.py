from django.contrib import admin
from .models import (
    CustomUser, Plat, TableRestaurant, Tablette, 
    PanierItem, Commande, CommandeItem, Paiement, 
    Caisse, Depense
)

# On enregistre tout de la manière la plus basique possible
# Sans classe Admin personnalisée pour l'instant
admin.site.register(CustomUser)
admin.site.register(Plat)
admin.site.register(TableRestaurant)
admin.site.register(PanierItem)
admin.site.register(Commande)
admin.site.register(CommandeItem)
admin.site.register(Paiement)
admin.site.register(Caisse)
admin.site.register(Depense)

# Pour Tablette, on met juste le minimum pour tester
@admin.register(Tablette)
class TabletteAdmin(admin.ModelAdmin):
    # On n'affiche QUE des champs simples (pas de 'user' ou 'table' qui sont des relations)
    list_display = ('id', 'active', 'is_blocked')