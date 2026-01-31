from django.urls import path
from . import views
urlpatterns = [
    path('', views.Accueil, name='Accueil'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('table/', views.table_index, name='table_index'),
    path('tablette/', views.tablette_index, name='tablette_index'),
    path('serveur/', views.serveur_index, name='serveur_index'),
    path('cuisinier/', views.cuisinier_index, name='cuisinier_index'),
    path('comptable/', views.comptable_index, name='comptable_index'),
    path('p_admin/', views.admin_page, name='admin_page'),
    path('tablette/ajouter_au_panier/<int:plat_id>/', views.ajouter_au_panier, name='ajouter_au_panier'),
    path('tablette/voir_panier', views.consulter_panier, name='voir_panier'),
    path('tablette/validation', views.valider_panier, name='valider_panier'),
    path('tablette/supprimer_du_panier/<int:panier_item_id>/', views.supprimer_du_panier, name='supprimer_du_panier'),
    path('tablette/modification/<int:panier_item_id>/', views.modifier_panier, name='modifier_panier'),
    path('menu/',views.visioner_menu,name="menu"),
    path('tablette/voir_menu', views.voir_menu, name='voir_menu'),
    path('p_admin/table',views.table_index, name='table_admin'),
    path('cuisinier/ajplat/', views.ajouter_plat, name='ajouter_plat'),
    path('cuisinier/modplat/<int:plat_id>/', views.modifier_plat, name='modifier_plat'),
    path('cuisinier/supplat/<int:plat_id>/', views.supprimer_plat, name='supprimer_plat'),
    path('modifier_role/<int:user_id>/', views.admin_page, name='modifier_role'),
    path('supprimer_utilisateur/<int:user_id>/', views.admin_page, name='supprimer_utilisateur'),
    path('ajouter_utilisateur/', views.admin_page, name='ajouter_utilisateur'),
    path('commande/',views.Commande_index,name='commande_index'),
    


   
]
  

