# =========================================================
# Fichier : models.py
# Rôle : Définit tous les modèles de la base de données pour le restaurant
# Bibliothèques utilisées :
# - django.db.models : pour créer les modèles et champs de la BD
# - django.conf.settings : pour lier les modèles à l'utilisateur personnalisé
# - django.contrib.auth.models : pour créer un utilisateur personnalisé
# =========================================================

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager

# =========================================================
# Gestion des utilisateurs personnalisés
# ---------------------------------------------------------
# CustomUser permet d'utiliser "identifiant" au lieu de username
# et d'ajouter un champ "role" pour gérer les permissions
# =========================================================
class CustomUserManager(BaseUserManager):
    """
    Manager pour créer des utilisateurs et super-utilisateurs
    """
    def create_user(self, identifiant, password=None, **extra_fields):
        if not identifiant:
            raise ValueError("L'identifiant est obligatoire")
        user = self.model(identifiant=identifiant, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, identifiant, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(identifiant, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Modèle utilisateur personnalisé
    - identifiant : identifiant unique de connexion
    - role : admin, serveur, cuisinier, comptable, tablette
    """
    username = None  # On supprime le username standard
    email = None     # Email optionnel

    identifiant = models.CharField(max_length=20, unique=True)

    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('serveur', 'Serveur'),
        ('cuisinier', 'Cuisinier'),
        ('comptable', 'Comptable'),
        ('tablette', 'Tablette'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    USERNAME_FIELD = 'identifiant'  # identifiant pour la connexion
    REQUIRED_FIELDS = []

    objects = CustomUserManager()  # Utilisation du manager personnalisé

    def __str__(self):
        return self.identifiant


# =========================================================
# Gestion des tables du restaurant
# =========================================================
class TableRestaurant(models.Model):
    """
    Modèle représentant une table physique du restaurant
    - numero_table : numéro unique de la table
    - nombre_places : capacité de la table
    - is_occupied : si la table est actuellement occupée
    """
    numero_table = models.PositiveIntegerField(unique=True)
    nombre_places = models.PositiveIntegerField()
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        status = "Occupée" if self.is_occupied else "Libre"
        return f"Table {self.numero_table} ({status})"


# =========================================================
# Tablette liée à une table
# =========================================================
class Tablette(models.Model):
    """
    Modèle représentant une tablette physique
    - user : compte utilisateur associé
    - table : table associée
    - active : indique si la tablette est activée
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'tablette'}
    )
    table = models.OneToOneField(
        TableRestaurant,
        on_delete=models.CASCADE
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tablette {self.user.identifiant} - Table {self.table.numero_table}"


# =========================================================
# Gestion des plats
# =========================================================
class Plat(models.Model):
    """
    Modèle représentant un plat du menu
    - nom : nom du plat
    - prix_unitaire : prix du plat
    - image : photo du plat
    - disponible : disponibilité dans le menu
    """
    nom = models.CharField(max_length=100)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='plats/', blank=True, null=True)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


# =========================================================
# Gestion du panier (lié à la tablette)
# =========================================================
class PanierItem(models.Model):
    """
    Modèle représentant un item dans le panier
    - tablette : la tablette qui commande
    - plat : le plat choisi
    - quantite : quantité commandée
    """
    tablette = models.ForeignKey(Tablette, on_delete=models.CASCADE)
    plat = models.ForeignKey(Plat, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)

    def montant(self):
        """
        Retourne le prix total de cet item
        """
        return self.quantite * self.plat.prix_unitaire

    def __str__(self):
        return f"{self.plat.nom} x {self.quantite}"


# =========================================================
# Gestion des commandes
# =========================================================
class Commande(models.Model):
    """
    Modèle représentant une commande complète
    - tablette : tablette qui passe la commande
    - total : montant total
    - date : date de la commande
    - valide : statut de validation
    """
    tablette = models.ForeignKey(Tablette, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField(auto_now_add=True)
    valide = models.BooleanField(default=False)

    def __str__(self):
        return f"Commande #{self.id} - Table {self.tablette.table.numero_table}"


# =========================================================
# Gestion de la caisse
# =========================================================
class Caisse(models.Model):
    """
    Modèle représentant la caisse
    - solde_actuel : montant actuel
    """
    solde_actuel = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    def __str__(self):
        return f"Caisse - Solde: {self.solde_actuel} FG"


# =========================================================
# Gestion des dépenses
# =========================================================
class Depense(models.Model):
    """
    Modèle représentant une dépense
    - date : date de la dépense
    - description : description de la dépense
    - montant : montant dépensé
    - categorie : type de dépense
    """
    date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=10, decimal_places=2)

    CATEGORIES = (
        ('Achat', 'Achat'),
        ('Salaire', 'Salaire'),
        ('Facture', 'Facture'),
        ('Autre', 'Autre'),
    )
    categorie = models.CharField(max_length=20, choices=CATEGORIES, default='Autre')

    def __str__(self):
        return f"{self.date.date()} - {self.categorie} : {self.montant} FG"


# =========================================================
# Gestion des paiements
# =========================================================
class Paiement(models.Model):
    """
    Modèle représentant un paiement
    - commande : commande payée
    - montant : montant payé
    - date : date du paiement
    - mode : mode de paiement
    """
    commande = models.OneToOneField(
        Commande,
        on_delete=models.CASCADE,
        related_name='paiement'
    )
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    MODE_CHOICES = (
        ('cash', 'Espèces'),
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    def __str__(self):
        return f"Paiement {self.montant} ({self.get_mode_display()})"


# =========================================================
# Gestion du menu (optionnel)
# =========================================================
class MenuItem(models.Model):
    """
    Modèle représentant un item du menu
    - nom : nom du plat
    - description : description
    - prix : prix
    - image : image
    """
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix = models.DecimalField(max_digits=6, decimal_places=2)
    image = models.ImageField(upload_to='plats/', blank=True, null=True)

    def __str__(self):
        return self.nom

  
