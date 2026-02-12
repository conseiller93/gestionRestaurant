from django.urls import path, include
from . import views

urlpatterns = [
    # ── Auth ──
    path('login/',                                          views.login_view,                   name='login'),
    path('logout/',                                         views.logout_view,                  name='logout'),

    # ── Accueil ──
    path('',                                                views.Accueil,                      name='Accueil'),

    # ── Tablette ──
    path('tablette/',                                       views.tablette_index,               name='tablette_index'),
    path('tablette/panier/',                                views.consulter_panier,             name='voir_panier'),
    path('tablette/ajouter/<int:plat_id>/',                 views.ajouter_au_panier,            name='ajouter_au_panier'),
    path('tablette/modifier/<int:panier_item_id>/',         views.modifier_panier,              name='modifier_panier'),
    path('tablette/supprimer/<int:panier_item_id>/',        views.supprimer_du_panier,          name='supprimer_du_panier'),
    path('tablette/valider/',                               views.valider_panier,               name='valider_panier'),

    # ── Menu / Cuisinier ──
    path('menu/',                                           views.cuisinier_index,              name='cuisinier_index'),
    path('plat/ajouter/',                                   views.ajouter_plat,                 name='ajouter_plat'),
    path('plat/modifier/<int:plat_id>/',                    views.modifier_plat,                name='modifier_plat'),
    path('plat/supprimer/<int:plat_id>/',                   views.supprimer_plat,               name='supprimer_plat'),

    # ── Tables ──
    path('tables/',                                         views.table_index,                  name='table_index'),

    # ── Serveur ──
    path('serveur/',                                        views.serveur_index,                name='serveur_index'),
    path('serveur/valider/<int:commande_id>/',              views.serveur_valider_commande,     name='serveur_valider_commande'),
    path('serveur/payer/<int:commande_id>/',                views.serveur_valider_paiement,     name='serveur_valider_paiement'),

    # ── Comptable ──
    path('comptable/',                                      views.comptable_index,              name='comptable_index'),
    path('compta/depense/supprimer/<int:depense_id>/', views.supprimer_depense, name='supprimer_depense'),

    # ── Commandes (admin) ──
    path('commande/',                                      views.Commande_index,               name='commande_index'),
    path('compta/commande/supprimer/<int:commande_id>/', views.supprimer_commande_compta, name='supprimer_commande'),


    # ── Admin ──
    path('admin/',                                          views.admin_page,                   name='admin_page'),
    path('controle general/',                                 views.admin_page,             name='controle_general'),
    path('export/<int:commande_id>/', views.export_commande_data, name='export_facture'), # Pour tablette
    path('export/global/', views.export_commande_data, name='export_global'), # Pour admin
    path('profil/securite/', views.modifier_mot_de_passe, name='password_change'),
]
  

