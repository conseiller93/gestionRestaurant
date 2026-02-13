# =========================================================
# views.py — Toutes les vues du restaurant
# =========================================================

from urllib import request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from decimal import Decimal, InvalidOperation
# Tu utilises Count mais il n'est pas importé au bon endroit dans views.py
# Ajouter en haut du fichier avec les autres imports :
from django.db.models import Sum, Count
import csv
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
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
    """Autorise l'accès aux superusers et aux utilisateurs dont le rôle est dans `roles`."""
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
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .models import Tablette

from django.contrib.auth import authenticate, login

def login_view(request):
    initial_identifiant = ''
    initial_password = ''

    # Paramètres du QR Code → on pré-remplit uniquement
    u = request.GET.get('u', '')
    p = request.GET.get('p', '')
    if u and p:
        initial_identifiant = u
        initial_password = p  # sera mis dans le champ password (type=password, donc masqué)

    if request.method == "POST":
        identifiant = request.POST.get('identifiant', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, identifiant=identifiant, password=password)
        if user is not None:
            # Vérification blocage tablette
            if user.role == 'tablette':
                tablette = Tablette.objects.filter(user=user).first()
                if tablette and tablette.is_blocked:
                    messages.error(request, "Cette tablette est temporairement bloquée.")
                    return render(request, 'login.html', {'error': 'Tablette bloquée.'})
            login(request, user)
            return redirect('Accueil')
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect.")

    return render(request, 'login.html', {
        'initial_identifiant': initial_identifiant,
        'initial_password': initial_password,
    })
# Déconnecter toutes les tablettes (forcer is_active=False temporairement,
# ou invalider leurs sessions)
@login_required
def deconnecter_toutes_tablettes(request):
    if request.user.role != 'admin' and not request.user.is_superuser:
        raise PermissionDenied
    # Invalide toutes les sessions des users "tablette"
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

# Bloquer / débloquer une tablette
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
def logout_view(request):
    logout(request)
    return redirect('login')


# =========================================================
# ACCUEIL
# =========================================================
@login_required(login_url='login')
def Accueil(request):
    return render(request, 'Accueil.html')


# =========================================================
# TABLETTE (rôle : tablette)
# =========================================================
@login_required(login_url='login')
@role_required('tablette', 'admin')
def tablette_index(request):
    # --- VÉRIFICATION BLOCAGE (avant tout) ---
    if request.user.role == 'tablette':
        tablette_check = Tablette.objects.filter(user=request.user).first()
        if tablette_check and tablette_check.is_blocked:
            logout(request)
            messages.error(request, "Cette tablette a été bloquée par l'administrateur. Contactez le responsable.")
            return redirect('login')

    # --- LOGIQUE EXISTANTE CORRIGÉE ---
    tablette = Tablette.objects.filter(
        user=request.user,
        active=True
    ).first()

    # On initialise avec un QuerySet vide au lieu d'une liste []
    panier_items = PanierItem.objects.none() 
    commandes_envoyees = Commande.objects.none()

    if tablette:
        panier_items = PanierItem.objects.filter(tablette=tablette)
        # On récupère aussi les commandes pour la lecture seule
        commandes_envoyees = Commande.objects.filter(
            tablette=tablette
        ).exclude(statut='payee').order_by('-date')

    # --- LOGIQUE ADMIN ---
    toutes_les_tablettes = []
    stats_occupation = 0
    
    if request.user.role == 'admin':
        toutes_les_tablettes = Tablette.objects.all().select_related('table')
        for t in toutes_les_tablettes:
            t.en_utilisation = Commande.objects.filter(tablette=t).exclude(statut='payee').exists()
            t.panier_actif = PanierItem.objects.filter(tablette=t).exists()
        
        total_tabs = toutes_les_tablettes.count()
        if total_tabs > 0:
            occupees = sum(1 for t in toutes_les_tablettes if t.en_utilisation)
            stats_occupation = (occupees / total_tabs) * 100

    # --- RETOUR UNIQUE ---
    return render(request, 'tablette/index.html', {
        'tablette': tablette,
        'panier_items': panier_items,
        'commandes_envoyees': commandes_envoyees,
        'panier': panier_items.exists(),
        'panier_count': panier_items.count(),
        'toutes_les_tablettes': toutes_les_tablettes,
        'taux_occupation': stats_occupation,
    })

@login_required(login_url='login')
@role_required('tablette', 'admin')
def ajouter_au_panier(request, plat_id):
    if request.method != "POST":
        return redirect('tablette_index')

    # 1. Identification de la tablette (Simulation pour Admin)
    if request.user.role == 'admin':
        tablette = Tablette.objects.filter(active=True).first()
    else:
        tablette = Tablette.objects.filter(user=request.user).first()

    if not tablette:
        messages.error(request, "Erreur : Aucune tablette active trouvée.")
        return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

    # 2. Récupération du plat
    plat = get_object_or_404(Plat, id=plat_id)

    # 3. TA LOGIQUE : Si stock <= 0, alors indisponible
    if plat.quantite_disponible <= 0:
        # On force le booléen à False par sécurité
        if plat.disponible:
            plat.disponible = False
            plat.save()
        
        messages.error(request, f"Désolé, le plat '{plat.nom}' est épuisé.")
        return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

    # 4. Récupération de la quantité demandée
    try:
        qte_demandee = int(request.POST.get('quantite', 1))
    except (ValueError, TypeError):
        qte_demandee = 1

    # On s'assure de ne pas commander plus que le stock actuel
    qte_finale = min(qte_demandee, plat.quantite_disponible)

    # 5. Ajout au panier (Accumulation)
    item, created = PanierItem.objects.get_or_create(
        tablette=tablette,
        plat=plat,
        defaults={'quantite': qte_finale}
    )
    
    if not created:
        nouvelle_qte = item.quantite + qte_finale
        # On plafonne toujours au stock disponible
        item.quantite = min(nouvelle_qte, plat.quantite_disponible)
        item.save()

    messages.success(request, f"✅ {plat.nom} ajouté (Quantité: {qte_finale})")
    return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

@login_required(login_url='login')
@role_required('tablette', 'admin') # Autorise aussi l'admin
def consulter_panier(request):
    """Affiche le contenu du panier avec le total."""
    
    # On utilise .filter().first() au lieu de get_object_or_404
    tablette = Tablette.objects.filter(user=request.user, active=True).first()

    # Si l'utilisateur n'est pas lié à une tablette (ex: Admin)
    if not tablette:
        if request.user.role == 'admin':
            # Optionnel : l'admin peut être redirigé vers l'accueil tablette
            messages.warning(request, "En tant qu'admin, vous n'avez pas de panier personnel.")
            return redirect('tablette_index')
        else:
            # Pour un utilisateur normal sans tablette active
            from django.http import Http404
            raise Http404("Aucune tablette active associée à ce compte.")

    # Suite de la logique normale
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
    """Modifie la quantité ou supprime un item du panier."""
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    item = get_object_or_404(PanierItem, id=panier_item_id, tablette=tablette)

    if request.method == "POST":
        if 'supprimer' in request.POST:
            item.delete()
        elif 'quantite' in request.POST:
            quantite = int(request.POST['quantite'])
            if quantite <= 0:
                item.delete()
            else:
                item.quantite = max(1, min(quantite, 10))
                item.save()

    return redirect('voir_panier')


@login_required(login_url='login')
@role_required('tablette')
def supprimer_du_panier(request, panier_item_id):
    """Supprime un item du panier."""
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    item = get_object_or_404(PanierItem, id=panier_item_id, tablette=tablette)
    item.delete()
    return redirect('voir_panier')


@login_required(login_url='login')
@role_required('tablette')
def valider_panier(request):
    """Valide le panier → crée une Commande + ses CommandeItems, vide le panier."""
    tablette = get_object_or_404(Tablette, user=request.user, active=True)
    items = PanierItem.objects.filter(tablette=tablette).select_related('plat')

    if not items.exists():
        messages.warning(request, "Le panier est vide.")
        return redirect('voir_panier')

    # Calcul du total
    total = sum(item.montant() for item in items)

    # Création de la commande
    commande = Commande.objects.create(
        tablette=tablette,
        total=total,
        statut='en_attente'
    )

    # Copie des items dans CommandeItem (snapshot prix)
    for item in items:
        CommandeItem.objects.create(
            commande=commande,
            plat=item.plat,
            quantite=item.quantite,
            prix_unitaire=item.plat.prix_unitaire
        )

    # Vidage du panier
    items.delete()

    return render(request, 'tablette/validation_commande.html', {
        'commande': commande
    })


# =========================================================
# MENU (visible par tous les utilisateurs authentifiés)
# =========================================================
@login_required(login_url='login')
@role_required('cuisinier', 'tablette', 'admin')# Votre décorateur actuel
def cuisinier_index(request):
    """Page du menu : liste des plats avec statistiques."""
    plats = Plat.objects.all()

    # CORRECTION ICI : Remplacer 'commande__total' par 'commandeitem'
    # On compte le nombre de fois que le plat a été commandé
    plats_populaires = Plat.objects.annotate(
        total_vendu=Count('commandeitem')
    ).filter(total_vendu__gt=0).order_by('-total_vendu')[:3]

    suggestion_chef = plats_populaires.first() if plats_populaires else None

    context = {
        'plats': plats,
        'plats_populaires': plats_populaires,
        'suggestion_chef': suggestion_chef,
    }
    
    return render(request, 'cuisinier/index.html', context)


@login_required(login_url='login')
def ajouter_plat(request):
    if request.user.role not in ('admin', 'cuisinier') and not request.user.is_superuser:
        return HttpResponseForbidden("Accès refusé.")

    if request.method == 'POST':
        form = PlatForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Plat ajouté avec succès.")
        return redirect('cuisinier_index')

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
            return redirect('cuisinier_index')
        else:
            # S'il y a des erreurs (ex: champ vide), on les transforme en messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field} : {error}")
    
    # Au lieu de render un template qui n'existe pas, 
    # on retourne à la page du menu (cuisinier_index)
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
# TABLES (vue récap)
# =========================================================
@login_required(login_url='login')
def table_index(request):
    tables = TableRestaurant.objects.all()
    return render(request, 'tables/index.html', {'tables': tables})


# =========================================================
# SERVEUR
# État des tables : libre / en_attente / servie / payee
# =========================================================
@login_required(login_url='login')
@role_required('serveur')
def serveur_index(request):
    """
    Vue du serveur :
    - Liste des tables avec leur état déduit des commandes
    - Liste des commandes en attente ou servies
    """
    tables = TableRestaurant.objects.all()

    # Pour chaque table, déterminer l'état
    tables_context = []
    for table in tables:
        # Dernière commande non payée sur cette table
        derniere_commande = (
            Commande.objects.filter(tablette__table=table)
            .exclude(statut='payee')
            .order_by('-date')
            .first()
        )

        if derniere_commande is None:
            etat = 'libre'
        else:
            etat = derniere_commande.statut  # en_attente ou servie

        tables_context.append({
            'table': table,
            'etat': etat,
            'derniere_commande': derniere_commande,
        })

    # Commandes en attente ou servies (pas encore payées)
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
    """Le serveur marque une commande comme 'servie'."""
    commande = get_object_or_404(Commande, id=commande_id, statut='en_attente')
    commande.statut = 'servie'
    commande.save()
    messages.success(request, f"Commande #{commande.id} marquée comme servie.")
    return redirect('serveur_index')


@login_required(login_url='login')
@role_required('serveur')
def serveur_valider_paiement(request, commande_id):
    """Le serveur valide le paiement physique → commande 'payee' + enregistrement Paiement + caisse."""
    commande = get_object_or_404(Commande, id=commande_id, statut='servie')

    # Éviter double paiement
    if hasattr(commande, 'paiement'):
        messages.error(request, "Cette commande est déjà payée.")
        return redirect('serveur_index')

    # Créer le paiement
    Paiement.objects.create(
        commande=commande,
        montant=commande.total,
        mode='cash'
    )

    # Mettre à jour le statut
    commande.statut = 'payee'
    commande.save()

    # Mettre à jour la caisse
    caisse, _ = Caisse.objects.get_or_create(id=1)
    caisse.solde_actuel += commande.total
    caisse.save()

    messages.success(request, f"Commande #{commande.id} payée. Caisse mise à jour.")
    return redirect('serveur_index')


# =========================================================
# COMPTABLE
# =========================================================
@login_required(login_url='login')
@role_required('comptable')
def comptable_index(request):
    caisse, _ = Caisse.objects.get_or_create(id=1)
    erreur_depense = None

    # On récupère aussi le 'serveur' pour l'afficher dans le template
    commandes_a_payer = (
        Commande.objects.filter(statut='servie')
        .exclude(paiement__isnull=False)
        .select_related('tablette__table', 'serveur') # Ajout de serveur
    )

    paiements = Paiement.objects.select_related(
        'commande__tablette__table', 'commande__comptable' # Ajout du comptable
    ).order_by('-date')

    depenses = Depense.objects.select_related('utilisateur').order_by('-date')

    if request.method == "POST":
        # ── PAIEMENT COMMANDE ──
        if 'payer_commande' in request.POST:
            commande_id = request.POST.get('commande_id') # Vérifie que le name dans ton HTML est 'commande_id'
            mode = request.POST.get('mode')

            try:
                commande = Commande.objects.get(id=commande_id, statut='servie')

                # 1. Enregistrer le paiement avec le comptable actuel
                Paiement.objects.create(
                    commande=commande,
                    montant=commande.total,
                    mode=mode,
                )

                # 2. Mettre à jour la commande avec le comptable qui a validé
                commande.comptable = request.user # On stocke QUI a encaissé
                commande.statut = 'payee'
                commande.save()

                # 3. Ajouter l'argent dans la caisse
                caisse.solde_actuel += commande.total
                caisse.save()

                messages.success(request, f"✅ Commande #{commande.id} validée par {request.user.identifiant}")
                return redirect('comptable_index')

            except Commande.DoesNotExist:
                messages.error(request, "Commande introuvable ou déjà payée.")

        # ── AJOUT DEPENSE (Ta logique existante gardée) ──
        elif 'ajouter_depense' in request.POST:
            description = request.POST.get('description', '').strip()
            montant_str = request.POST.get('montant', '').strip()
            categorie = request.POST.get('categorie', '').strip()

            try:
                montant_val = Decimal(montant_str)
                if montant_val <= 0:
                    erreur_depense = "Le montant doit être positif."
                elif montant_val > caisse.solde_actuel:
                    erreur_depense = "Solde insuffisant dans la caisse."
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
            except:
                erreur_depense = "Données invalides."

    return render(request, 'comptable/index.html', {
        'commandes_a_payer': commandes_a_payer,
        'paiements': paiements,
        'depenses': depenses,
        'solde': caisse.solde_actuel,
        'erreur_depense': erreur_depense,
    })
# =========================================================
# COMMANDE (liste globale – admin)
# =========================================================
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Commande

@login_required(login_url='login')
def Commande_index(request):
    """
    Interface partagée : 
    - Serveur : Accès total
    - Comptable : Accès lecture seule (détails uniquement)
    - Admin : Accès total
    """
    # Liste des rôles autorisés à voir cette page
    roles_autorises = ['admin', 'serveur', 'comptable']
    
    if request.user.role not in roles_autorises and not request.user.is_superuser:
        raise PermissionDenied

    commandes = (
        Commande.objects.all()
        .select_related('tablette__table')
        .prefetch_related('items__plat')
        .order_by('-date')
    )
    
    return render(request, 'commande/index.html', {'commandes': commandes})

from django.db.models import Sum
from .models import Plat, Commande
from django.utils import timezone

from django.db.models import Sum, Count
from .models import Plat, Commande
from django.utils import timezone

@login_required
def Accueil(request):
    today = timezone.now().date()
    
    # 1. Statistiques de base
    nb_commandes = Commande.objects.filter(date__date=today).count()
    recette_total = Commande.objects.filter(date__date=today, statut='payee').aggregate(Sum('total'))['total__sum'] or 0

    # 2. TOP VENTES (Lecture seule)
    # On compte combien de fois chaque plat apparaît dans les 'commandeitem'
    plats_populaires = Plat.objects.annotate(
        nombre_ventes=Count('commandeitem')
    ).filter(nombre_ventes__gt=0).order_by('-nombre_ventes')[:3]

    # 3. SUGGESTION (Le premier du top)
    suggestion_chef = plats_populaires.first() if plats_populaires else None

    context = {
        'nb_commandes': nb_commandes,
        'recette_total': recette_total,
        'tables_occupees': 0, 
        'total_tables': 20,
        'plats_populaires': plats_populaires,
        'suggestion_chef': suggestion_chef,
    }
    
    return render(request, 'Accueil.html', context)
@login_required
def modifier_mot_de_passe(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Mot de passe mis à jour !')
            return redirect('Accueil')
        else:
            # Au lieu de render un template, on renvoie les erreurs via messages
            for error in form.non_field_errors():
                messages.error(request, error)
            for field in form:
                for error in field.errors:
                    messages.error(request, f"{field.label}: {error}")
            return redirect('Accueil') # On revient sur l'accueil
    
    return redirect('Accueil') # Si accès via GET, on redirige aussi


# =========================================================
# ADMINISTRATION
# =========================================================

# ============================================================
# ADMIN PAGE
# ===========================================================
@login_required(login_url="login")
def admin_page(request):
    # ───── Sécurité ─────
    # Vérifie si l'utilisateur est superutilisateur ou a le rôle admin
    if not request.user.is_superuser and getattr(request.user, 'role', None) != "admin":
        messages.error(request, "Accès refusé.")
        return redirect("Accueil")

    # ===================== POST =====================
    if request.method == "POST":

        # ───────── AJOUT UTILISATEUR ─────────
        if "ajouter_utilisateur" in request.POST:
            identifiant = request.POST.get("identifiant", "").strip()
            password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip()
            # RÉCUPÉRATION DES NOUVEAUX CHAMPS
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
                    first_name=first_name,  # Enregistrement du prénom
                    last_name=last_name,    # Enregistrement du nom
                    email=email,            # Enregistrement de l'email
                    is_active=True,
                    is_staff=(role == "admin")
                )
                user.set_password(password)
                user.save()
                messages.success(request, f"Utilisateur « {identifiant} » créé avec succès.")

        # ───────── MODIFIER UTILISATEUR ─────────
        elif "modifier_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user = get_object_or_404(CustomUser, id=user_id)

            identifiant = request.POST.get("identifiant", "").strip()
            password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip()
            # MISE À JOUR DES CHAMPS
            user.first_name = request.POST.get("first_name", "").strip()
            user.last_name = request.POST.get("last_name", "").strip()
            user.email = request.POST.get("email", "").strip()

            if CustomUser.objects.filter(identifiant=identifiant).exclude(id=user.id).exists():
                messages.error(request, "Cet identifiant est déjà utilisé par un autre compte.")
            else:
                user.identifiant = identifiant
                user.role = role
                user.is_staff = (role == "admin")

                if password: # On ne change le MDP que s'il est saisi
                    user.set_password(password)

                user.save()
                messages.success(request, f"Compte « {identifiant} » mis à jour.")

        # ───────── SUPPRIMER UTILISATEUR ─────────
        elif "supprimer_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user_to_del = get_object_or_404(CustomUser, id=user_id)

            if user_to_del == request.user:
                messages.error(request, "Action impossible : vous utilisez actuellement ce compte.")
            else:
                user_to_del.delete()
                messages.success(request, "Utilisateur supprimé.")

        # ───────── CRÉER TABLE + TABLETTE ─────────
        elif "creer_tablette" in request.POST:
            numero = request.POST.get("numero_table")
            places = request.POST.get("nombre_places")
            ident_tab = request.POST.get("identifiant_tablette")
            pass_tab = request.POST.get("password_tablette")

            if not all([numero, places, ident_tab, pass_tab]):
                messages.error(request, "Tous les champs pour la table et la tablette sont requis.")
            elif TableRestaurant.objects.filter(numero_table=numero).exists():
                messages.error(request, f"La table n°{numero} existe déjà.")
            elif CustomUser.objects.filter(identifiant=ident_tab).exists():
                messages.error(request, "L'identifiant de la tablette est déjà pris.")
            else:
                # 1. Créer le compte utilisateur "tablette"
                user_tab = CustomUser(
                    identifiant=ident_tab,
                    role="tablette",
                    is_active=True
                )
                user_tab.set_password(pass_tab)
                user_tab.save()

                # 2. Créer la table physique
                table = TableRestaurant.objects.create(
                    numero_table=numero,
                    nombre_places=int(places)
                )

                # 3. Lier les deux via le modèle Tablette
                Tablette.objects.create(
                    user=user_tab,
                    table=table
                )

                messages.success(request, f"Table {numero} et tablette {ident_tab} activées.")

        # ───────── SUPPRIMER TABLE ─────────
        elif "supprimer_table" in request.POST:
            table_id = request.POST.get("table_id")
            table_to_del = get_object_or_404(TableRestaurant, id=table_id)

            # Supprimer la tablette liée et son compte utilisateur
            tab_liee = Tablette.objects.filter(table=table_to_del).first()
            if tab_liee and tab_liee.user:
                tab_liee.user.delete() 
            
            table_to_del.delete()
            messages.success(request, "Table et compte tablette associé supprimés.")
        # ───────── GÉNÉRER QR CODE ─────────
        # ───────── GÉNÉRER QR CODE ─────────
        # ───────── GÉNÉRER QR CODE ─────────
        elif "generer_qr" in request.POST:
            import qrcode
            from io import BytesIO
            from django.http import HttpResponse
            from django.urls import reverse # N'oublie pas cet import en haut !

            table_id = request.POST.get("table_id")
            table = get_object_or_404(TableRestaurant, id=table_id)
            tab_info = Tablette.objects.filter(table=table).first()
            
            if tab_info and tab_info.user:
                # 1. On prépare l'URL
                base_url = request.build_absolute_uri(reverse('login'))
                url = f"{base_url}?u={tab_info.user.identifiant}&p=12345cd"
                
                # 2. ON CRÉE L'OBJET QR D'ABORD (C'est ce qui manquait !)
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                
                # 3. Maintenant on peut ajouter les données
                qr.add_data(url)
                qr.make(fit=True)

                # 4. On génère l'image
                img = qr.make_image(fill_color="black", back_color="white")
                
                buf = BytesIO()
                img.save(buf)
                
                return HttpResponse(buf.getvalue(), content_type="image/png")
            else:
                messages.error(request, "Aucune tablette liée à cette table.")
        # 🔁 Redirection vers la même page pour éviter le renvoi de formulaire au rafraîchissement
        return redirect("controle_general") # Remplace par "controle_general" si c'est le nom exact de ton URL

    # ===================== GET =====================
    utilisateurs = CustomUser.objects.all().order_by("role", "identifiant")

    tables_data = []
    for t in TableRestaurant.objects.all().order_by("numero_table"):
        tab_info = Tablette.objects.filter(table=t).first()
        tables_data.append({
            "id": t.id,
            "numero": t.numero_table,
            "nombre_places": t.nombre_places,
            "user_tablette": tab_info.user if tab_info else None,
            "active": tab_info.active if tab_info else False,
        })

    return render(request, "admin/admin.html", {
        "utilisateurs": utilisateurs,
        "tables": tables_data,
    })
@login_required
def supprimer_commande_compta(request, commande_id):
    """ Supprime une commande de la liste (si erreur du serveur par exemple) """
    if request.user.role in ['admin', 'comptable']:
        commande = get_object_or_404(Commande, id=commande_id)
        commande.delete()
        messages.success(request, "La commande a été supprimée de la liste.")
    return redirect('comptable_index')
@login_required
def supprimer_depense(request, depense_id):
    """ Supprime une dépense et rend l'argent à la caisse """
    if request.user.role in ['admin', 'comptable']:
        depense = get_object_or_404(Depense, id=depense_id)
        
        # Optionnel : Rendre l'argent à la caisse si on annule la dépense
        caisse = Caisse.objects.get(id=1)
        caisse.solde_actuel += depense.montant
        caisse.save()
        
        depense.delete()
        messages.success(request, "Dépense annulée. Le montant a été réintégré au solde.")
    return redirect('comptable_index')

# ============================================================
# CONTROLE GENERAL
# ============================================================
@login_required
def controle_general(request):
    return render(request, "admin/admin.html")

import csv
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from gestion.models import Commande, Tablette,Paiement
from django.utils import timezone
@login_required
def export_commande_data(request, commande_id=None):
    user = request.user
    
    # On récupère la commande (uniquement si payée)
    try:
        if getattr(user, 'role', None) == 'tablette':
            tablette = Tablette.objects.get(user=user)
            commande = Commande.objects.get(id=commande_id, tablette=tablette)
        else:
            commande = Commande.objects.get(id=commande_id)
            
        if commande.statut != 'en_attente':
            return HttpResponseForbidden("Le reçu ne peut être généré que pour les commandes payées.")
            
    except (Tablette.DoesNotExist, Commande.DoesNotExist):
        return HttpResponseForbidden("Commande introuvable.")

    # --- CRÉATION DU PETIT REÇU (FORMAT TEXTE) ---
    response = HttpResponse(content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="Recu_{commande.id}.txt"'

    # Construction du contenu du ticket
    lignes = []
    lignes.append("      MON RESTAURANT       ")
    lignes.append("---------------------------")
    lignes.append(f"Ticket No: {commande.id}")
    lignes.append(f"Table    : {commande.tablette.table.numero_table}")
    lignes.append(f"Date     : {commande.date.strftime('%d/%m/%Y %H:%M')}")
    lignes.append("---------------------------")
    lignes.append(f"{'Article':<15} {'Qté':<3} {'Prix':>7}")
    
    for item in commande.items.all():
        nom_plat = item.plat.nom[:15] # On coupe le nom si trop long
        lignes.append(f"{nom_plat:<15} {item.quantite:<3} {item.plat.prix_unitaire:>7}")

    lignes.append("---------------------------")
    lignes.append(f"TOTAL:           {commande.total:>7} FG")
    lignes.append("---------------------------")
    lignes.append("      MERCI DE VOTRE       ")
    lignes.append("         VISITE !          ")
    lignes.append("\n\n") # Espaces pour la découpe du papier

    response.write("\n".join(lignes))
    return response