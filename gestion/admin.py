from django.contrib import admin
from .models import CustomUser, Plat, TableRestaurant, Caisse, Commande, Depense,Tablette

admin.site.register(CustomUser)
admin.site.register(Plat)
admin.site.register(TableRestaurant)
admin.site.register(Caisse)
admin.site.register(Commande)
admin.site.register(Depense)
admin.site.register(Tablette)
from django.contrib import admin
from .models import Plat

"""@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prix_unitaire', 'disponible')"""


# Register your models here.
