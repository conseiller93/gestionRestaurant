"""from django.shortcuts import render ,redirect
from django.contrib.auth.decorators import login_required
from .models import Plat 
from .models import TableRestaurant
from .forms import TableRestaurantForm   
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import CustomUser
from django.contrib.auth import logout
import re
from django.core.exceptions import PermissionDenied
# views.py
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("identifiant")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Redirection selon le rôle
            if user.is_superuser:
                return redirect('/admin/')  # admin
            elif user.groups.filter(name='Managers').exists():
                return redirect('manager_dashboard')  # Exemple pour managers
            elif user.groups.filter(name='Clients').exists():
                return redirect('client_dashboard')   # Exemple pour clients
            else:
                return redirect('home')  # Utilisateur normal

        else:
            # Login incorrect
            return render(request, "login.html", {
                "error": "Identifiant ou mot de passe incorrect",
                "identifiant": username
            })

    # GET
    return render(request, "login.html")"""

from django.shortcuts import get_object_or_404, render, redirect,get_list_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import user_passes_test

from gestion.models import Commande, PanierItem, Plat, TableRestaurant, Tablette, MenuItem
from django.db.models import Sum
from .models import Paiement, Caisse
from django.http import HttpResponseForbidden
from .models import Commande, Paiement, Caisse, Depense,CustomUser
from .forms import PlatForm
from django.contrib import messages

# ================= LOGIN =================
def login_view(request):
    identifiant = ''

    if request.method == "POST":
        identifiant = request.POST.get("identifiant")
        password = request.POST.get("password")

        user = authenticate(request, identifiant=identifiant, password=password)

        if user:
            login(request, user)
            return redirect('Accueil')

        return render(request, 'login.html', {
            'error': 'Identifiant ou mot de passe incorrect',
            'identifiant': identifiant
        })

    if request.user.is_authenticated:
        return redirect('Accueil')

    return render(request, 'login.html', {'identifiant': identifiant})


# ================= LOGOUT =================
def logout_view(request):
    logout(request)
    return redirect('login')


# ================= ROLE DECORATOR =================
def role_required(*roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role not in roles:
                raise PermissionDenied

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@login_required(login_url='login')
@role_required('serveur')
def serveur_index(request):
    return render(request, 'serveur/index.html')
@login_required(login_url='login')
def table_index(request):
    tables = TableRestaurant.objects.all()
    return render(request, 'tables/index.html', {'tables': tables})


@login_required(login_url='login')
@role_required('cuisinier','tablette')
def cuisinier_index(request):
    plats = Plat.objects.all()
    return render(request, 'cuisinier/index.html', {'plats': plats})



   



@login_required(login_url='login')
@role_required('comptable')
def comptable(request):
    return render(request, 'comptable/index.html')


@login_required(login_url='login')
def Accueil(request):
    return render(request, 'Accueil.html')

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_superuser)
def admin_page(request):
    return render(request, 'admin/admin.html')
from django.shortcuts import get_object_or_404, redirect

@login_required
def ajouter_au_panier(request, plat_id):
    if request.method != "POST":
        return redirect('tablette_index')

    tablette_id = request.session.get('tablette_id')

    if not tablette_id:
        # aucune tablette active → on force le choix d'une table
        return redirect('table_index')

    tablette = get_object_or_404(Tablette, id=tablette_id)
    plat = get_object_or_404(Plat, id=plat_id)

    quantite = int(request.POST.get('quantite', 1))
    quantite = max(1, min(quantite, 10))

    panier_item, created = PanierItem.objects.get_or_create(
        tablette=tablette,
        plat=plat
    )
    panier_item.quantite = quantite
    panier_item.save()

    return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))

@login_required
def supprimer_du_panier(request, panier_item_id):
    item = get_object_or_404(PanierItem, id=panier_item_id)
    item.delete()
    return redirect('voir_panier')  # redirige vers la page du panier

@login_required
def consulter_panier(request):
    tablette = get_object_or_404(Tablette, user=request.user)
    items = PanierItem.objects.filter(tablette=tablette)
    total = sum(item.montant() for item in items)
    return render(request, 'tablette/listes_plats.html', {'items': items, 'total': total})
@login_required
def modifier_panier(request, item_id):
    tablette = get_object_or_404(Tablette, user=request.user)
    item = get_object_or_404(PanierItem, id=item_id, tablette=tablette)

    if 'quantite' in request.POST:
        quantite = int(request.POST['quantite'])
        if quantite <= 0:
            item.delete()
        else:
            item.quantite = max(1, min(quantite, 10))
            item.save()
    elif 'supprimer' in request.POST:
        item.delete()

    return redirect('consulter_panier')
@login_required
def valider_panier(request):
    tablette = get_object_or_404(Tablette, user=request.user)

    # ⚠️ ATTENTION : ton PanierItem utilise user, pas tablette
    items = PanierItem.objects.filter(user=request.user)

    if not items.exists():
        return redirect('liste_plats')

    total = sum(item.montant() for item in items)

    # ✅ commande NON payée
    commande = Commande.objects.create(
        user=request.user,
        tablette=tablette,
        total=total,
        valide=False   # 🔥 IMPORTANT
    )

    # Copier les items dans CommandeItems
    for item in items:
        CommandeItems.objects.create(
            commande=commande,
            plat=item.plat,
            quantite=item.quantite
        )

    # Vider le panier
    items.delete()

    return render(
        request,
        'tablette/validation_command.html',
        {'commande': commande}
    )

def voir_menu(request):
    items = MenuItem.objects.all()  # récupère tous les plats
    return render(request, 'tablette/listes_plats.html', {'items': items})
    
def payer_commande(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    commande.valide = True
    commande.save()
    return redirect('comptable_index')


@login_required
def comptable_index(request):
    depenses = Depense.objects.all().order_by('-date')
    erreur_depense = None
    # 🔒 Restriction : uniquement comptable
    if not request.user.role == 'comptable' and not request.user.is_superuser:
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.")

    # 💰 Caisse unique
    caisse, _ = Caisse.objects.get_or_create(id=1)

    # 📜 Historique paiements
    paiements = Paiement.objects.select_related('commande').order_by('-date')

    # 📦 Commandes validées mais NON payées
    commandes_a_payer = Commande.objects.filter(valide=True).exclude(paiement__isnull=False)

    # ➕ Enregistrer un paiement
    if request.method == "POST" and 'payer_commande' in request.POST:
        commande_id = request.POST.get('commande')
        mode = request.POST.get('mode')

        commande = get_object_or_404(Commande, id=commande_id)

        # Sécurité : éviter double paiement
        if hasattr(commande, 'paiement'):
            return redirect('comptable')

        Paiement.objects.create(
            commande=commande,
            montant=commande.total,
            mode=mode
        )

        caisse.solde_actuel += commande.total
        caisse.save()
        return redirect('comptable')
# ➖ Enregistrer une dépense
    if request.method == "POST" and 'ajouter_depense' in request.POST:
        description = request.POST.get('description', '').strip()
        montant = request.POST.get('montant', '').strip()
        categorie = request.POST.get('categorie', '').strip()

        if not description or not montant or not categorie:
            erreur_depense = "Tous les champs sont obligatoires."
        else:       
            try:
                montant_val = float(montant)
                if montant_val > caisse.solde_actuel:
                    erreur_depense = "Solde insuffisant."
                else:
                    Depense.objects.create(
                        description=description,
                        montant=montant_val,
                        categorie=categorie,
                        utilisateur=request.user
                    )
                    caisse.solde_actuel -= montant_val
                    caisse.save()
                    return redirect('comptable')
            except ValueError:
                erreur_depense = "Le montant doit être un nombre."

    context = {
        'paiements': paiements,
        'depenses': depenses,
        'commandes_a_payer': commandes_a_payer,
        'solde': caisse.solde_actuel,
        'erreur_depense': erreur_depense
}

    return render(request, 'comptable/index.html', context)

def consulter_panier(request):
    # On récupère la tablette de l'utilisateur connecté
    tablette = get_object_or_404(Tablette, user=request.user)

    # On récupère les PanierItem qui appartiennent à cette tablette et qui ne sont pas encore commandés
    panier_items = PanierItem.objects.filter(user=request.user)

    # Calcul du total
    total = sum(item.montant() for item in panier_items)

    return render(request, 'tablette/panier.html', {
        'tablette': tablette,
        'PanierItems': panier_items,  # passe à la template
        'total': total,
    })
def table_admin(request):
    tables = TableRestaurant.objects.all()
    return render(request, 'tables/index.html', {'tables': tables})
def caisse(request):
    caisse, _ = Caisse.objects.get_or_create(id=1)
    depenses = Depense.objects.all().order_by('-date')
    return render(request), 'comptable/caisse.html', {
        'solde': caisse.solde_actuel,
        'depenses': depenses
    }
# gestion/views.py

@login_required
def ajouter_plat(request):
    if request.user.role not in ('admin', 'cuisinier'):
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.")
    if request.method == 'POST':
        form = PlatForm(request.POST, request.FILES)  # important pour l'image !
        if form.is_valid():
            form.save()
        return redirect('cuisinier_index')  # revenir à la page du menu
    else:
        form = PlatForm()
    
    return render(request, 'cuisinier/index.html', {'form': form})
def admin_cuisinier(user):
    return user.role in ('admin', 'cuisinier')
        
@login_required
def modifier_plat(request, plat_id):
    if not admin_cuisinier(request.user):
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.") 
    plat = get_object_or_404(Plat, id=plat_id)
    
    if request.method == 'POST':
        form = PlatForm(request.POST, request.FILES, instance=plat)
        if form.is_valid():
            form.save()
            return redirect('cuisinier_index')
    else:
        form = PlatForm(instance=plat)
    
    return render(request, 'cuisinier/ajplast.html', {'form': form, 'plat': plat})  
@login_required
def supprimer_plat(request, plat_id):
    # Vérifie si l'utilisateur est admin
    if request.user.role != 'admin':
        return HttpResponseForbidden("Vous n'avez pas la permission de supprimer ce plat.")

    plat = get_object_or_404(Plat, id=plat_id)
    plat.delete()
    return redirect('cuisinier_index')
# =================Gestion Admin Utilisateurs =================
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CustomUser, TableRestaurant, Tablette

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, TableRestaurant, Tablette

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, TableRestaurant, Tablette

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import CustomUser, TableRestaurant, Tablette


@login_required
def admin_page(request):
    # Sécurité : admin uniquement
    if request.user.role != 'admin':
        messages.error(request, "Accès refusé.")
        return redirect('cuisinier_index')

    if request.method == "POST":

        # ================= AJOUT UTILISATEUR =================
        if "ajouter_utilisateur" in request.POST:
            identifiant = request.POST.get("username")
            password = request.POST.get("password")
            role = request.POST.get("role")

            if not identifiant or not password:
                messages.error(request, "Identifiant et mot de passe obligatoires.")
            elif CustomUser.objects.filter(identifiant=identifiant).exists():
                messages.error(request, "Cet identifiant existe déjà.")
            else:
                user = CustomUser(identifiant=identifiant, role=role)
                user.set_password(password)
                user.save()
                messages.success(request, f"Utilisateur {identifiant} ajouté avec succès.")

        # ================= MODIFIER UTILISATEUR =================
        elif "modifier_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user = get_object_or_404(CustomUser, id=user_id)

            identifiant = request.POST.get("username")
            password = request.POST.get("password")
            role = request.POST.get("role")

            if CustomUser.objects.filter(identifiant=identifiant).exclude(id=user_id).exists():
                messages.error(request, "Cet identifiant est déjà utilisé.")
            else:
                user.identifiant = identifiant
                user.role = role
                if password:
                    user.set_password(password)
                user.save()
                messages.success(request, f"Utilisateur {identifiant} modifié.")

        # ================= SUPPRIMER UTILISATEUR =================
        elif "supprimer_utilisateur" in request.POST:
            user_id = request.POST.get("user_id")
            user = get_object_or_404(CustomUser, id=user_id)
            identifiant = user.identifiant
            user.delete()
            messages.success(request, f"L'utilisateur {identifiant} a été supprimé.")

        # ================= CRÉER TABLE + TABLETTE (FORMULAIRE UNIQUE) =================
        elif "creer_table_tablette" in request.POST:
            numero = request.POST.get("numero")
            identifiant = request.POST.get("identifiant")
            password = request.POST.get("password")
            nombre_places = request.POST.get("nombre_places")

            if not all([numero, identifiant, password, nombre_places]):
                messages.error(request, "Tous les champs sont obligatoires.")
            elif CustomUser.objects.filter(identifiant=identifiant).exists():
                messages.error(request, "Cet identifiant tablette existe déjà.")
            else:
                try:
                    nombre_places = int(nombre_places)
                except ValueError:
                    messages.error(request, "Le nombre de places doit être un nombre.")
                else:
                    # Utilisateur tablette
                    user_tablette = CustomUser(
                        identifiant=identifiant,
                        role="tablette"
                    )
                    user_tablette.set_password(password)
                    user_tablette.save()

                    # Table
                    table = TableRestaurant.objects.create(
                        numero_table=numero,
                        nombre_places=nombre_places
                    )

                    # Tablette ACTIVE
                    Tablette.objects.create(
                        user=user_tablette,
                        table=table,
                        active=True
                    )

                    messages.success(
                        request,
                        f"Table {numero} et tablette {identifiant} créées et activées."
                    )

    # ================= CONTEXTE =================

    utilisateurs = CustomUser.objects.all()

    tables = []
    for table in TableRestaurant.objects.all():
        tablette = Tablette.objects.filter(table=table).first()
        tables.append({
            "id": table.id,
            "numero": table.numero_table,
            "nombre_places": table.nombre_places,
            "user_tablette": tablette.user if tablette else None,
            "active": tablette.active if tablette else False
        })

    return render(
        request,
        "admin/admin.html",
        {
            "utilisateurs": utilisateurs,
            "tables": tables
        }
    )



@login_required(login_url='login')
@role_required('tablette')
def tablette_index(request):
    return render(request,"tablette/index.html")
def Commande_index(request):
    return render(request,"commande/index.html")
from django.shortcuts import get_object_or_404
@login_required(login_url='login')
@role_required('tablette')
def visioner_menu(request):
    return(request,"gestion/menu.html")
@login_required
@role_required('tablette')
def ajouter_au_panier(request, plat_id):
    # 1️⃣ Vérifier que la tablette est active pour cet utilisateur
    tablette = get_object_or_404(
        Tablette,
        user=request.user,
        active=True
    )

    # 2️⃣ Récupérer le plat
    plat = get_object_or_404(Plat, id=plat_id)

    # 3️⃣ Quantité sécurisée
    quantite = int(request.POST.get('quantite', 1))
    quantite = max(1, min(quantite, 10))

    # 4️⃣ Ajouter / mettre à jour le panier
    panier_item, _ = PanierItem.objects.get_or_create(
        user=request.user,
        plat=plat
    )
    panier_item.quantite = quantite
    panier_item.save()

    # 5️⃣ Retour à la page précédente
    return redirect(request.META.get('HTTP_REFERER', 'tablette_index'))
@login_required
@role_required('tablette')
def tablette_login(request):
    # L'utilisateur est déjà connecté
    user = request.user

    # Désactiver ancienne tablette si elle existe
    Tablette.objects.filter(user=user, active=True).update(active=False)

    # Créer une nouvelle tablette active
    tablette = Tablette.objects.create(user=user, active=True)

    return redirect('tablette_index')
from django.db.models.signals import post_save
from django.dispatch import receiver

@login_required
@role_required('admin')
def creer_table_tablette(request):
    if request.method == 'POST':
        form = TableTabletteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Table et tablette créées avec succès")
            return redirect('admin_page')
    else:
        form = TableTabletteForm()

    return render(request, 'admin/creer_table_tablette.html', {'form': form})
@login_required
@role_required('admin')
def toggle_tablette(request, tablette_id):
    tablette = get_object_or_404(Tablette, id=tablette_id)
    tablette.active = not tablette.active
    tablette.save()
    return redirect('admin_page')



    





# Create your views here.
