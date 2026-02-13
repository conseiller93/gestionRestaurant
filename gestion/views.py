# =========================================================
# views.py — Toutes les vues du restaurant (VERSION CORRIGÉE)
# =========================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, authenticate, login, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from decimal import Decimal
import csv

from .models import (
    CustomUser, TableRestaurant, Tablette,
    Plat, PanierItem, Commande, CommandeItem,
    Paiement, Caisse, Depense
)
from .forms import PlatForm


# =========================================================
# DÉCORATEUR : rôle requis
# =========================================================
def role_required(*roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return wrapper
    return decorator


# =========================================================
# LOGIN / LOGOUT
# =========================================================
def login_view(request):
    initial_identifiant = ''
    initial_password = ''

    u = request.GET.get('u', '')
    p = request.GET.get('p', '')
    if u and p:
        initial_identifiant = u
        initial_password = p

    if request.method == "POST":
        identifiant = request.POST.get('identifiant', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, identifiant=identifiant, password=password)
        if user is not None:
            if user.role == 'tablette':
                tablette = Tablette.objects.filter(user=user).first()
                if tablette and tablette.is_blocked:
                    return render(request, 'login.html', {
                        'error': "Cette tablette est temporairement bloquée par l'administrateur."
                    })
            login(request, user)
            return redirect('Accueil')
        else:
            return render(request, 'login.html', {
                'error': 'Identifiant ou mot de passe incorrect.',
                'initial_identifiant': initial_identifiant,
            })

    return render(request, 'login.html', {
        'initial_identifiant': initial_identifiant,
        'initial_password': initial_password,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


# =========================================================
# ACCUEIL
# =========================================================
@login_required(login_url='login')
def Accueil(request):
    from django.utils import timezone
    today = timezone.now().date()
    context = {}

    if request.user.role in ('admin', 'comptable') or request.user.is_superuser:
        nb_commandes = Commande.objects.filter(date__date=today).count()
        recette_total = (
            Commande.objects.filter(date__date=today, statut='payee')
            .aggregate(Sum('total'))['total__sum'] or 0
        )
        tables_occupees = TableRestaurant.objects.filter(is_occupied=True).count()
        total_tables = TableRestaurant.objects.count()

        plats_populaires = Plat.objects.annotate(
            nombre_ventes=Count('commandeitem')
        ).filter(nombre_ventes__gt=0).order_by('-nombre_ventes')[:3]

        suggestion_chef = plats_populaires.first() if plats_populaires else None

        context.update({
            'nb_commandes': nb_commandes,
            'recette_total': recette_total,
            'tables_occupees': tables_occupees,
            'total_tables': total_tables,
            'plats_populaires': plats_populaires,
            'suggestion_chef': suggestion_chef,
        })

    return render(request, 'Accueil.html', context)


# =========================================================
# TABLETTE
# =========================================================
@login_required(login_url='login')
@role_required('tablette', 'admin')
def tablette_index(request):
    if request.user.role == 'tablette':
        tablette_check = Tablette.objects.filter(user=request.user).first()
        if tablette_check and tablette_check.is_blocked:
            logout(request)
            messages.error(request, "Cette tablette a été bloquée par l'administrateur.")
            return redirect('login')

    tablette = Tablette.objects.filter(user=request.user, active=True).first()

    panier_items = PanierItem.objects.none()
    commandes_envoyees = Commande.objects.none()
    total = 0

    if tablette:
        panier_items = PanierItem.objects.filter(tablette=tablette).select_related('plat')
        total = sum(item.montant() for item in panier_items)
        commandes_envoyees = (
            Commande.objects.filter(tablette=tablette)
            .prefetch_related('items__plat')
            .order_by('-date')
        )

    toutes_les_tablettes = []
    stats_occupation = 0

    if request.user.is_superuser or request.user.role == 'admin':
        toutes_les_tablettes = Tablette.objects.all().select_related('table')
        for t in toutes_les_tablettes:
            t.en_utilisation = Commande.objects.filter(tablette=t).exclude(statut='payee').exists()
            t.panier_actif = PanierItem.objects.filter(tablette=t).exists()
        total_tabs = toutes_les_tablettes.count()
        if total_tabs > 0:
            occupees = sum(1 for t in toutes_les_tablettes if t.en_utilisation)
            stats_occupation = round((occupees / total_tabs) * 100)

    return render(request, 'tablette/index.html', {
        'tablette': tablette,
        'panier_items': panier_items,
        'commandes_envoyees': commandes_envoyees,
        'panier': panier_items.exists(),
        'panier_count': panier_items.count(),
        'total': total,
        'toutes_les_tablettes': toutes_les_tablettes,
        'taux_occupation': stats_occupation,
    })


@login_required(login_url='login')
@role_required('tablette', 'admin')
def ajouter_au_panier(request, plat_id):
    if request.method != "POST":
        return redirect('tablette_index')

    if request.user.role == 'admin' or request.user.is_superuser:
        tablette = Tablette.objects.filter(active=True).first()
    else:
        tablette = Tablette.objects.filter(user=request.user).first()

    if not tablette:
        messages.error(request, "Aucune tablette active trouvée.")
        return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

    plat = get_object_or_404(Plat, id=plat_id)

    if plat.quantite_disponible <= 0:
        if plat.disponible:
            plat.disponible = False
            plat.save()
        messages.error(request, f"Le plat '{plat.nom}' est épuisé.")
        return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

    try:
        qte_demandee = int(request.POST.get('quantite', 1))
    except (ValueError, TypeError):
        qte_demandee = 1

    qte_finale = min(max(1, qte_demandee), plat.quantite_disponible)

    item, created = PanierItem.objects.get_or_create(
        tablette=tablette,
        plat=plat,
        defaults={'quantite': qte_finale}
    )

    if not created:
        nouvelle_qte = item.quantite + qte_finale
        item.quantite = min(nouvelle_qte, plat.quantite_disponible)
        item.save()

    messages.success(request, f"✅ {plat.nom} ajouté (×{qte_finale})")
    return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))


@login_required(login_url='login')
@role_required('tablette', 'admin')
def consulter_panier(request):
    tablette = Tablette.objects.filter(user=request.user, active=True).first()

    if not tablette:
        if request.user.role == 'admin' or request.user.is_superuser:
            messages.warning(request, "En mode admin, vous n'avez pas de panier personnel.")
            return redirect('tablette_index')
        else:
            from django.http import Http404
            raise Http404("Aucune tablette active associée à ce compte.")

    items = PanierItem.objects.filter(tablette=tablette).select_related('plat')
    total = sum(item.montant() for item in items)

    return render(request, 'tablette/panier.html', {
        'tablette': tablette,
        'items': items,
        'total': total,
    })


@login_required(login_url='login')
@role_required('tablette')
def modifier_panier(request, panier_item_id):
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    item = get_object_or_404(PanierItem, id=panier_item_id, tablette=tablette)

    if request.method == "POST":
        if 'supprimer' in request.POST:
            item.delete()
        elif 'quantite' in request.POST:
            try:
                quantite = int(request.POST['quantite'])
            except ValueError:
                quantite = 1
            if quantite <= 0:
                item.delete()
            else:
                item.quantite = max(1, min(quantite, item.plat.quantite_disponible))
                item.save()

    return redirect('voir_panier')


@login_required(login_url='login')
@role_required('tablette')
def supprimer_du_panier(request, panier_item_id):
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    item = get_object_or_404(PanierItem, id=panier_item_id, tablette=tablette)
    item.delete()
    return redirect('voir_panier')


@login_required(login_url='login')
@role_required('tablette')
def valider_panier(request):
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    items = PanierItem.objects.filter(tablette=tablette).select_related('plat')

    if not items.exists():
        messages.warning(request, "Le panier est vide.")
        return redirect('voir_panier')

    total = sum(item.montant() for item in items)

    commande = Commande.objects.create(
        tablette=tablette,
        total=total,
        statut='en_attente'
    )

    for item in items:
        CommandeItem.objects.create(
            commande=commande,
            plat=item.plat,
            quantite=item.quantite,
            prix_unitaire=item.plat.prix_unitaire
        )
        plat = item.plat
        plat.quantite_disponible = max(0, plat.quantite_disponible - item.quantite)
        if plat.quantite_disponible == 0:
            plat.disponible = False
        plat.save()

    items.delete()

    return render(request, 'tablette/validation_commande.html', {
        'commande': commande
    })


# =========================================================
# MENU / CUISINIER
# =========================================================
@login_required(login_url='login')
@role_required('cuisinier', 'tablette', 'admin')
def cuisinier_index(request):
    plats = Plat.objects.all()

    plats_populaires = Plat.objects.annotate(
        total_vendu=Count('commandeitem')
    ).filter(total_vendu__gt=0).order_by('-total_vendu')[:3]

    suggestion_chef = plats_populaires.first() if plats_populaires else None

    panier_items = PanierItem.objects.none()
    if request.user.role == 'tablette':
        tablette = Tablette.objects.filter(user=request.user, active=True).first()
        if tablette:
            panier_items = PanierItem.objects.filter(tablette=tablette)

    return render(request, 'cuisinier/index.html', {
        'plats': plats,
        'plats_populaires': plats_populaires,
        'suggestion_chef': suggestion_chef,
        'panier_items': panier_items,
    })


@login_required(login_url='login')
def ajouter_plat(request):
    if request.user.role not in ('admin', 'cuisinier') and not request.user.is_superuser:
        return HttpResponseForbidden("Accès refusé.")

    if request.method == 'POST':
        form = PlatForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Plat ajouté avec succès.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field} : {error}")
    return redirect('cuisinier_index')


@login_required(login_url='login')
def modifier_plat(request, plat_id):
    if request.user.role not in ('admin', 'cuisinier') and not request.user.is_superuser:
        return HttpResponseForbidden("Accès refusé.")

    plat = get_object_or_404(Plat, id=plat_id)

    if request.method == 'POST':
        form = PlatForm(request.POST, request.FILES, instance=plat)
        if form.is_valid():
            form.save()
            messages.success(request, f"Plat '{plat.nom}' modifié avec succès.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field} : {error}")

    return redirect('cuisinier_index')


@login_required(login_url='login')
def supprimer_plat(request, plat_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        return HttpResponseForbidden("Seul l'admin peut supprimer un plat.")

    plat = get_object_or_404(Plat, id=plat_id)
    plat.delete()
    messages.success(request, "Plat supprimé.")
    return redirect('cuisinier_index')


# =========================================================
# TABLES
# =========================================================
@login_required(login_url='login')
def table_index(request):
    tables = TableRestaurant.objects.all()
    return render(request, 'tables/index.html', {'tables': tables})


# =========================================================
# SERVEUR
# =========================================================
@login_required(login_url='login')
@role_required('serveur')
def serveur_index(request):
    tables = TableRestaurant.objects.all()

    tables_context = []
    for table in tables:
        derniere_commande = (
            Commande.objects.filter(tablette__table=table)
            .exclude(statut='payee')
            .order_by('-date')
            .first()
        )
        etat = 'libre' if derniere_commande is None else derniere_commande.statut
        tables_context.append({
            'table': table,
            'etat': etat,
            'derniere_commande': derniere_commande,
        })

    commandes = (
        Commande.objects.filter(statut__in=['en_attente', 'servie'])
        .select_related('tablette__table')
        .prefetch_related('items__plat')
        .order_by('-date')
    )

    return render(request, 'serveur/index.html', {
        'tables_context': tables_context,
        'commandes': commandes,
    })


@login_required(login_url='login')
@role_required('serveur')
def serveur_valider_commande(request, commande_id):
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('serveur_index')

    commande = get_object_or_404(Commande, id=commande_id, statut='en_attente')
    commande.statut = 'servie'
    commande.serveur = request.user
    commande.save()
    messages.success(request, f"✅ Commande #{commande.id} marquée comme servie.")
    return redirect('serveur_index')


@login_required(login_url='login')
@role_required('serveur')
def serveur_valider_paiement(request, commande_id):
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('serveur_index')

    commande = get_object_or_404(Commande, id=commande_id, statut='servie')

    if hasattr(commande, 'paiement'):
        messages.error(request, "Cette commande est déjà payée.")
        return redirect('serveur_index')

    Paiement.objects.create(
        commande=commande,
        montant=commande.total,
        mode='cash'
    )

    commande.statut = 'payee'
    commande.serveur = request.user
    commande.save()

    caisse, _ = Caisse.objects.get_or_create(id=1)
    caisse.solde_actuel += commande.total
    caisse.save()

    table = commande.tablette.table
    commandes_actives = Commande.objects.filter(
        tablette__table=table
    ).exclude(statut='payee').count()
    if commandes_actives == 0:
        table.is_occupied = False
        table.save()

    messages.success(request, f"💰 Commande #{commande.id} payée. {commande.total} FG ajoutés à la caisse.")
    return redirect('serveur_index')


# =========================================================
# COMMANDE (liste globale)
# =========================================================
@login_required(login_url='login')
def Commande_index(request):
    roles_autorises = ['admin', 'serveur', 'comptable']
    if request.user.role not in roles_autorises and not request.user.is_superuser:
        raise PermissionDenied

    commandes = (
        Commande.objects.all()
        .select_related('tablette__table', 'serveur', 'comptable')
        .prefetch_related('items__plat')
        .order_by('-date')
    )

    return render(request, 'commande/index.html', {
        'commandes': commandes,
        'user': request.user,
    })


# =========================================================
# COMPTABLE
# =========================================================
@login_required(login_url='login')
@role_required('comptable')
def comptable_index(request):
    caisse, _ = Caisse.objects.get_or_create(id=1)
    from django.utils import timezone
    today = timezone.now().date()

    commandes_actives = (
        Commande.objects.filter(statut__in=['en_attente', 'servie'])
        .select_related('tablette__table', 'serveur')
        .prefetch_related('items__plat')
        .order_by('-date')
    )

    paiements = (
        Paiement.objects
        .select_related(
            'commande__tablette__table',
            'commande__serveur',
            'commande__comptable',
        )
        .prefetch_related('commande__items__plat')
        .order_by('-date')
    )

    paiements_today = paiements.filter(date__date=today)
    recette_du_jour = paiements_today.aggregate(Sum('montant'))['montant__sum'] or 0
    nb_paiements_today = paiements_today.count()

    depenses = Depense.objects.select_related('utilisateur').order_by('-date')
    total_depenses = depenses.aggregate(Sum('montant'))['montant__sum'] or 0

    if request.method == "POST":
        if 'ajouter_depense' in request.POST:
            description = request.POST.get('description', '').strip()
            montant_str = request.POST.get('montant', '').strip()
            categorie = request.POST.get('categorie', '').strip()

            try:
                montant_val = Decimal(montant_str)
                if montant_val <= 0:
                    messages.error(request, "Le montant doit être positif.")
                elif montant_val > caisse.solde_actuel:
                    messages.error(request, f"Solde insuffisant. Caisse : {caisse.solde_actuel} FG")
                else:
                    Depense.objects.create(
                        description=description,
                        montant=montant_val,
                        categorie=categorie,
                        utilisateur=request.user
                    )
                    caisse.solde_actuel -= montant_val
                    caisse.save()
                    messages.success(request, "Dépense enregistrée.")
                    return redirect('comptable_index')
            except Exception:
                messages.error(request, "Données invalides.")

    return render(request, 'comptable/index.html', {
        'commandes_actives': commandes_actives,
        'paiements': paiements,
        'depenses': depenses,
        'solde': caisse.solde_actuel,
        'recette_du_jour': recette_du_jour,
        'nb_paiements_today': nb_paiements_today,
        'total_depenses': total_depenses,
    })


# =========================================================
# SUPPRESSIONS
# =========================================================
@login_required
def supprimer_commande_compta(request, commande_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect('comptable_index')
    commande = get_object_or_404(Commande, id=commande_id)
    commande.delete()
    messages.success(request, "La commande a été supprimée.")
    return redirect('comptable_index')


@login_required
def supprimer_depense(request, depense_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect('comptable_index')
    depense = get_object_or_404(Depense, id=depense_id)
    montant = depense.montant
    caisse, _ = Caisse.objects.get_or_create(id=1)
    caisse.solde_actuel += montant
    caisse.save()
    depense.delete()
    messages.success(request, f"Dépense supprimée. {montant} FG réintégrés au solde.")
    return redirect('comptable_index')


# =========================================================
# ACTIONS ADMIN
# =========================================================
@login_required
def admin_supprimer_commande(request, commande_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect(request.META.get('HTTP_REFERER', 'Accueil'))
    commande = get_object_or_404(Commande, id=commande_id)
    commande.delete()
    messages.success(request, f"Commande #{commande_id} supprimée.")
    return redirect(request.META.get('HTTP_REFERER', 'commande_index'))


@login_required
def admin_supprimer_paiement(request, paiement_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect(request.META.get('HTTP_REFERER', 'Accueil'))
    paiement = get_object_or_404(Paiement, id=paiement_id)
    montant = paiement.montant
    caisse, _ = Caisse.objects.get_or_create(id=1)
    caisse.solde_actuel = max(0, caisse.solde_actuel - montant)
    caisse.save()
    paiement.delete()
    messages.success(request, f"Paiement supprimé. {montant} FG retirés de la caisse.")
    return redirect('comptable_index')


@login_required
def admin_reinitialiser_solde(request):
    if request.method != 'POST':
        return redirect('comptable_index')
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect('comptable_index')
    caisse, _ = Caisse.objects.get_or_create(id=1)
    ancien_solde = caisse.solde_actuel
    caisse.solde_actuel = Decimal('0.00')
    caisse.save()
    messages.success(request, f"Caisse réinitialisée. Ancien solde : {ancien_solde} FG.")
    return redirect('comptable_index')


@login_required
def admin_tout_supprimer(request):
    if request.method != 'POST':
        return redirect('Accueil')
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, "Action réservée à l'administrateur.")
        return redirect('Accueil')

    type_suppression = request.POST.get('type', '')
    caisse, _ = Caisse.objects.get_or_create(id=1)

    if type_suppression == 'commandes':
        nb = Commande.objects.count()
        Commande.objects.all().delete()
        messages.success(request, f"{nb} commande(s) supprimée(s).")
        return redirect('commande_index')

    elif type_suppression == 'depenses':
        total = Depense.objects.aggregate(Sum('montant'))['montant__sum'] or 0
        nb = Depense.objects.count()
        Depense.objects.all().delete()
        caisse.solde_actuel += Decimal(str(total))
        caisse.save()
        messages.success(request, f"{nb} dépense(s) supprimée(s). {total} FG réintégrés.")
        return redirect('comptable_index')

    elif type_suppression == 'paiements':
        total = Paiement.objects.aggregate(Sum('montant'))['montant__sum'] or 0
        nb = Paiement.objects.count()
        Paiement.objects.all().delete()
        caisse.solde_actuel = max(Decimal('0.00'), caisse.solde_actuel - Decimal(str(total)))
        caisse.save()
        messages.success(request, f"{nb} paiement(s) supprimé(s). {total} FG retirés de la caisse.")
        return redirect('comptable_index')

    elif type_suppression == 'plats':
        nb = Plat.objects.count()
        Plat.objects.all().delete()
        messages.success(request, f"{nb} plat(s) supprimé(s).")
        return redirect('cuisinier_index')

    messages.error(request, "Type de suppression inconnu.")
    return redirect('Accueil')


# =========================================================
# ADMINISTRATION — CORRIGÉE : association table/tablette
# =========================================================
@login_required(login_url="login")
def admin_page(request):
    if not request.user.is_superuser and getattr(request.user, 'role', None) != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("Accueil")

    if request.method == "POST":

        # ── AJOUTER UTILISATEUR ──
        if "ajouter_utilisateur" in request.POST:
            identifiant = request.POST.get("identifiant", "").strip()
            password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip()
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip()

            if not identifiant or not password:
                messages.error(request, "Identifiant et mot de passe obligatoires.")
            elif CustomUser.objects.filter(identifiant=identifiant).exists():
                messages.error(request, "Cet identifiant existe déjà.")
            else:
                user = CustomUser(
                    identifiant=identifiant,
                    role=role,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=True,
                    is_staff=(role == "admin")
                )
                user.set_password(password)
                user.save()
                messages.success(request, f"Utilisateur « {identifiant} » créé.")

        # ── MODIFIER UTILISATEUR ──
        elif "modifier_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user = get_object_or_404(CustomUser, id=user_id)
            identifiant = request.POST.get("identifiant", "").strip()
            password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip()
            user.first_name = request.POST.get("first_name", "").strip()
            user.last_name = request.POST.get("last_name", "").strip()
            user.email = request.POST.get("email", "").strip()

            if CustomUser.objects.filter(identifiant=identifiant).exclude(id=user.id).exists():
                messages.error(request, "Cet identifiant est déjà utilisé.")
            else:
                user.identifiant = identifiant
                user.role = role
                user.is_staff = (role == "admin")
                if password:
                    user.set_password(password)
                user.save()
                messages.success(request, f"Compte « {identifiant} » mis à jour.")

        # ── SUPPRIMER UTILISATEUR ──
        elif "supprimer_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user_to_del = get_object_or_404(CustomUser, id=user_id)
            if user_to_del == request.user:
                messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
            else:
                user_to_del.delete()
                messages.success(request, "Utilisateur supprimé.")

        # ── CRÉER / ASSOCIER TABLE + TABLETTE ──
        # CORRIGÉ : logique intelligente — crée ce qui manque, évite les doublons
        elif "creer_tablette" in request.POST:
            numero = request.POST.get("numero_table", "").strip()
            places = request.POST.get("nombre_places", "").strip()
            ident_tab = request.POST.get("identifiant_tablette", "").strip()
            pass_tab = request.POST.get("password_tablette", "").strip()

            if not all([numero, places, ident_tab]):
                messages.error(request, "Tous les champs sont requis.")
            else:
                try:
                    numero_int = int(numero)
                    places_int = int(places)
                except ValueError:
                    messages.error(request, "Numéro de table et nombre de places doivent être des entiers.")
                    return redirect("controle_general")

                # 1) Récupérer ou créer la table
                table, table_created = TableRestaurant.objects.get_or_create(
                    numero_table=numero_int,
                    defaults={'nombre_places': places_int}
                )
                if not table_created:
                    # La table existe déjà — on met à jour le nombre de places si fourni
                    table.nombre_places = places_int
                    table.save()

                # 2) Récupérer ou créer l'utilisateur tablette
                user_tab = CustomUser.objects.filter(identifiant=ident_tab).first()
                if user_tab is None:
                    # L'utilisateur n'existe pas → on le crée
                    if not pass_tab:
                        messages.error(request, "Un mot de passe est requis pour créer un nouvel utilisateur tablette.")
                        return redirect("controle_general")
                    user_tab = CustomUser(identifiant=ident_tab, role="tablette", is_active=True)
                    user_tab.set_password(pass_tab)
                    user_tab.save()
                else:
                    # L'utilisateur existe déjà — on met à jour le mot de passe si fourni
                    if pass_tab:
                        user_tab.set_password(pass_tab)
                        user_tab.save()
                    # Vérifier que c'est bien un rôle tablette
                    if user_tab.role != 'tablette':
                        messages.error(request, f"L'utilisateur « {ident_tab} » existe déjà avec un rôle différent (rôle : {user_tab.role}).")
                        return redirect("controle_general")

                # 3) Récupérer ou créer la Tablette (lien table ↔ user)
                # Cas : la table a déjà une tablette liée → on la remplace
                tablette_existante_table = Tablette.objects.filter(table=table).first()
                # Cas : l'user a déjà une tablette liée → on la remplace
                tablette_existante_user = Tablette.objects.filter(user=user_tab).first()

                if tablette_existante_table and tablette_existante_user:
                    if tablette_existante_table == tablette_existante_user:
                        # Déjà associés — rien à faire
                        messages.success(request, f"✅ Table {numero} déjà associée à « {ident_tab} ».")
                    else:
                        # Conflit : deux tablettes différentes → on supprime les deux et on recrée
                        tablette_existante_table.delete()
                        tablette_existante_user.delete()
                        Tablette.objects.create(user=user_tab, table=table)
                        messages.success(request, f"✅ Table {numero} ré-associée à « {ident_tab} » (anciens liens supprimés).")
                elif tablette_existante_table:
                    # La table est déjà liée à un autre user → on met à jour
                    tablette_existante_table.user = user_tab
                    tablette_existante_table.save()
                    messages.success(request, f"✅ Table {numero} ré-associée à « {ident_tab} ».")
                elif tablette_existante_user:
                    # L'user est déjà lié à une autre table → on met à jour
                    tablette_existante_user.table = table
                    tablette_existante_user.save()
                    messages.success(request, f"✅ Tablette « {ident_tab} » ré-associée à la Table {numero}.")
                else:
                    # Aucune tablette existante → création normale
                    Tablette.objects.create(user=user_tab, table=table)
                    msg_table = "créée" if table_created else "existante"
                    messages.success(request, f"✅ Table {numero} ({msg_table}) et tablette « {ident_tab} » associées.")

        # ── SUPPRIMER TABLE ──
        elif "supprimer_table" in request.POST:
            table_id = request.POST.get("table_id")
            table_to_del = get_object_or_404(TableRestaurant, id=table_id)
            tab_liee = Tablette.objects.filter(table=table_to_del).first()
            if tab_liee and tab_liee.user:
                tab_liee.user.delete()
            table_to_del.delete()
            messages.success(request, "Table et compte tablette supprimés.")

        # ── GÉNÉRER QR CODE ──
        elif "generer_qr" in request.POST:
            import qrcode
            from io import BytesIO

            table_id = request.POST.get("table_id")
            table = get_object_or_404(TableRestaurant, id=table_id)
            tab_info = Tablette.objects.filter(table=table).first()

            if tab_info and tab_info.user:
                # CORRIGÉ : on n'inclut PAS le mot de passe dans l'URL
                # Le QR code préremplit seulement l'identifiant — plus sécurisé
                base_url = request.build_absolute_uri(reverse('login'))
                url = f"{base_url}?u={tab_info.user.identifiant}"

                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = BytesIO()
                img.save(buf)
                return HttpResponse(buf.getvalue(), content_type="image/png")
            else:
                messages.error(request, "Aucune tablette liée à cette table.")

        return redirect("controle_general")

    # GET — préparation du contexte
    utilisateurs = CustomUser.objects.all().order_by("role", "identifiant")
    tables_data = []
    for t in TableRestaurant.objects.all().order_by("numero_table"):
        tab_info = Tablette.objects.filter(table=t).first()
        tables_data.append({
            "id": t.id,
            "numero": t.numero_table,
            "nombre_places": t.nombre_places,
            "user_tablette": tab_info.user if tab_info else None,
            "tablette": tab_info,
            "active": tab_info.active if tab_info else False,
        })

    # NOUVEAU : tables sans tablette et tablettes sans table pour l'admin
    tables_sans_tablette = TableRestaurant.objects.filter(tablette__isnull=True).order_by("numero_table")
    users_tablette_sans_table = CustomUser.objects.filter(
        role='tablette', tablette__isnull=True
    ).order_by("identifiant")

    return render(request, "admin/admin.html", {
        "utilisateurs": utilisateurs,
        "tables": tables_data,
        "tables_sans_tablette": tables_sans_tablette,
        "users_tablette_sans_table": users_tablette_sans_table,
    })


# =========================================================
# DÉCONNECTER / BLOQUER TABLETTES
# =========================================================
@login_required
def deconnecter_toutes_tablettes(request):
    if request.user.role != 'admin' and not request.user.is_superuser:
        raise PermissionDenied
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    tablette_users = CustomUser.objects.filter(role='tablette')
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) in [str(u.pk) for u in tablette_users]:
            session.delete()
    messages.success(request, "Toutes les tablettes ont été déconnectées.")
    return redirect('controle_general')


@login_required
def toggle_blocage_tablette(request, tablette_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        raise PermissionDenied
    tablette = get_object_or_404(Tablette, id=tablette_id)
    tablette.is_blocked = not tablette.is_blocked
    tablette.save()
    etat = "bloquée" if tablette.is_blocked else "débloquée"
    messages.success(request, f"Tablette Table {tablette.table.numero_table} {etat}.")
    return redirect('controle_general')


# =========================================================
# MOT DE PASSE
# =========================================================
@login_required
def modifier_mot_de_passe(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, '✅ Mot de passe mis à jour !')
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
            for field in form:
                for error in field.errors:
                    messages.error(request, f"{field.label} : {error}")
    return redirect('Accueil')


# =========================================================
# EXPORT FACTURE
# =========================================================
@login_required
def export_commande_data(request, commande_id=None):
    user = request.user

    if commande_id is None:
        if user.role != 'admin' and not user.is_superuser:
            return HttpResponseForbidden("Accès refusé.")

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="ventes_global.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID', 'Table', 'Serveur', 'Total (FG)', 'Statut', 'Date', 'Plats'])

        commandes = (
            Commande.objects.all()
            .select_related('tablette__table', 'serveur')
            .prefetch_related('items__plat')
            .order_by('-date')
        )
        for cmd in commandes:
            plats_str = ', '.join([f"{i.quantite}x {i.plat.nom}" for i in cmd.items.all()])
            writer.writerow([
                cmd.id,
                f"Table {cmd.tablette.table.numero_table}",
                cmd.serveur.identifiant if cmd.serveur else '—',
                cmd.total,
                cmd.get_statut_display(),
                cmd.date.strftime('%d/%m/%Y %H:%M'),
                plats_str,
            ])
        return response

    try:
        if getattr(user, 'role', None) == 'tablette':
            tablette = Tablette.objects.get(user=user)
            commande = Commande.objects.get(id=commande_id, tablette=tablette)
        else:
            commande = Commande.objects.get(id=commande_id)
    except (Tablette.DoesNotExist, Commande.DoesNotExist):
        return HttpResponseForbidden("Commande introuvable.")

    response = HttpResponse(content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="Recu_{commande.id}.txt"'

    lignes = [
        "   ===========================   ",
        "       ELEGANCE RESTAURANT       ",
        "   ===========================   ",
        f"  Ticket n° : {commande.id}",
        f"  Table     : {commande.tablette.table.numero_table}",
        f"  Date      : {commande.date.strftime('%d/%m/%Y %H:%M')}",
        f"  Statut    : {commande.get_statut_display()}",
        "  ---------------------------   ",
        f"  {'Article':<16} {'Qté':>3}  {'Prix':>8}",
        "  ---------------------------   ",
    ]

    for item in commande.items.all():
        nom = item.plat.nom[:16]
        lignes.append(f"  {nom:<16} {item.quantite:>3}  {item.prix_unitaire:>7} FG")

    lignes += [
        "  ---------------------------   ",
        f"  TOTAL :          {commande.total:>8} FG",
        "  ===========================   ",
        "      MERCI DE VOTRE VISITE !   ",
        "   ===========================   ",
        "\n\n",
    ]

    response.write("\n".join(lignes))
    return response