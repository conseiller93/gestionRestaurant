from django.urls import path
from . import views

urlpatterns = [
    # ─────────────────────────────────────────────────────────
    # Auth
    # ─────────────────────────────────────────────────────────
    path('login/',                                              views.login_view,                       name='login'),
    path('logout/',                                             views.logout_view,                      name='logout'),

    # ─────────────────────────────────────────────────────────
    # Accueil
    # ─────────────────────────────────────────────────────────
    path('',                                                    views.Accueil,                          name='Accueil'),

    # ─────────────────────────────────────────────────────────
    # Tablette
    # ─────────────────────────────────────────────────────────
    path('tablette/',                                           views.tablette_index,                   name='tablette_index'),
    path('tablette/panier/',                                    views.consulter_panier,                 name='voir_panier'),
    path('tablette/ajouter/<int:plat_id>/',                     views.ajouter_au_panier,                name='ajouter_au_panier'),
    path('tablette/modifier/<int:panier_item_id>/',             views.modifier_panier,                  name='modifier_panier'),
    path('tablette/supprimer/<int:panier_item_id>/',            views.supprimer_du_panier,              name='supprimer_du_panier'),
    path('tablette/valider/',                                   views.valider_panier,                   name='valider_panier'),

    # ─────────────────────────────────────────────────────────
    # Menu / Cuisine
    # ─────────────────────────────────────────────────────────
    path('menu/',                                               views.cuisinier_index,                  name='cuisinier_index'),
    path('plat/ajouter/',                                       views.ajouter_plat,                     name='ajouter_plat'),
    path('plat/modifier/<int:plat_id>/',                        views.modifier_plat,                    name='modifier_plat'),
    path('plat/supprimer/<int:plat_id>/',                       views.supprimer_plat,                   name='supprimer_plat'),

    # ─────────────────────────────────────────────────────────
    # Tables
    # ─────────────────────────────────────────────────────────
    path('tables/',                                             views.table_index,                      name='table_index'),

    # ─────────────────────────────────────────────────────────
    # Serveur
    # ─────────────────────────────────────────────────────────
    path('serveur/',                                            views.serveur_index,                    name='serveur_index'),
    path('serveur/valider/<int:commande_id>/',                  views.serveur_valider_commande,         name='serveur_valider_commande'),
    path('serveur/payer/<int:commande_id>/',                    views.serveur_valider_paiement,         name='serveur_valider_paiement'),

    # ─────────────────────────────────────────────────────────
    # Comptable
    # ─────────────────────────────────────────────────────────
    path('comptable/',                                          views.comptable_index,                  name='comptable_index'),

    # ─────────────────────────────────────────────────────────
    # Commandes (vue globale)
    # ─────────────────────────────────────────────────────────
    path('commande/',                                           views.Commande_index,                   name='commande_index'),

    # ─────────────────────────────────────────────────────────
    # Administration — pages
    # CORRIGÉ : préfixe "gestion/" au lieu de "admin/"
    # pour éviter le conflit avec le Django admin natif
    # ─────────────────────────────────────────────────────────
    path('gestion/panel/',                                      views.admin_page,                       name='admin_page'),
    path('gestion/controle/',                                   views.admin_page,                       name='controle_general'),

    # ─────────────────────────────────────────────────────────
    # Administration — gestion tablettes
    # CORRIGÉ : préfixe "gestion/" au lieu de "admin/"
    # ─────────────────────────────────────────────────────────
    path('gestion/tablettes/deconnecter-toutes/',               views.deconnecter_toutes_tablettes,     name='deconnecter_tablettes'),
    path('gestion/tablette/<int:tablette_id>/blocage/',          views.toggle_blocage_tablette,          name='toggle_blocage_tablette'),

    # Alias sans prefixe admin/ (compatibilité)
    path('tablette/<int:tablette_id>/blocage/',                  views.toggle_blocage_tablette,          name='toggle_blocage_tablette_direct'),
    path('tablettes/deconnecter-toutes/',                        views.deconnecter_toutes_tablettes,     name='deconnecter_tablettes_direct'),

    # ─────────────────────────────────────────────────────────
    # SUPPRESSIONS — ADMIN UNIQUEMENT
    # CORRIGÉ : préfixe "gestion/" au lieu de "admin/"
    # ─────────────────────────────────────────────────────────

    # Supprimer une commande individuelle
    path('gestion/commande/supprimer/<int:commande_id>/',        views.admin_supprimer_commande,         name='supprimer_commande'),

    # Supprimer une dépense individuelle
    path('compta/depense/supprimer/<int:depense_id>/',           views.supprimer_depense,                name='supprimer_depense'),

    # Supprimer un paiement individuel
    path('gestion/paiement/supprimer/<int:paiement_id>/',        views.admin_supprimer_paiement,         name='supprimer_paiement'),

    # Ancienne route comptable kept pour compatibilité
    path('compta/commande/supprimer/<int:commande_id>/',         views.admin_supprimer_commande,         name='supprimer_commande_compta'),

    # Réinitialiser le solde de la caisse
    path('gestion/caisse/reinitialiser/',                        views.admin_reinitialiser_solde,        name='reinitialiser_solde'),

    # Suppressions globales (tout supprimer d'un type)
    path('gestion/tout-supprimer/',                              views.admin_tout_supprimer,             name='admin_tout_supprimer'),

    # ─────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────
    path('export/<int:commande_id>/',                            views.export_commande_data,             name='export_facture'),
    path('export/global/',                                       views.export_commande_data,             name='export_global'),

    # ─────────────────────────────────────────────────────────
    # Mot de passe
    # ─────────────────────────────────────────────────────────
    path('profil/securite/',                                     views.modifier_mot_de_passe,            name='password_change'),
]

