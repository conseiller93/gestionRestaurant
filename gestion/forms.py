from django import forms
from .models import TableRestaurant,Plat

class TableRestaurantForm(forms.ModelForm):
    class Meta:
        model = TableRestaurant
        fields = ['numero_table', 'nombre_places', 'is_occupied']


class PlatForm(forms.ModelForm):
    class Meta:
        model = Plat
        fields = ['nom', 'prix_unitaire', 'image','quantite_disponible', 'disponible']
