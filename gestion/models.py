from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager

# =========================================================
# Gestion des utilisateurs personnalisés
# =========================================================
class CustomUserManager(BaseUserManager):
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
        extra_fields.setdefault('role', 'admin')
        return self.create_user(identifiant, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None 
    email = models.EmailField(blank=True, null=True) 
    identifiant = models.CharField(max_length=20, unique=True)

    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('serveur', 'Serveur'),
        ('cuisinier', 'Cuisinier'),
        ('comptable', 'Comptable'),
        ('tablette', 'Tablette'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    USERNAME_FIELD = 'identifiant'
    REQUIRED_FIELDS = [] 

    objects = CustomUserManager()

    def __str__(self):
        return str(self.identifiant)

# =========================================================
# Table du restaurant
# =========================================================
class TableRestaurant(models.Model):
    numero_table = models.PositiveIntegerField(unique=True)
    nombre_places = models.PositiveIntegerField()
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"Table {self.numero_table}"

# =========================================================
# Tablette liée à une table
# =========================================================
class Tablette(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'tablette'}
    )
    table = models.OneToOneField(TableRestaurant, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Stocké en clair uniquement pour générer les QR Codes (usage physique interne)
    qr_password = models.CharField(
        max_length=128, blank=True, null=True,
        help_text="Mot de passe en clair pour les QR Codes"
    )

    def __str__(self):
        return f"Tablette : {self.user.identifiant} (Table {self.table.numero_table})"

# =========================================================
# Plat du menu
# =========================================================
class Plat(models.Model):
    nom = models.CharField(max_length=100)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='plats/', blank=True, null=True)
    quantite_disponible = models.PositiveIntegerField(default=0) 
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nom}"

# =========================================================
# Panier
# =========================================================
class PanierItem(models.Model):
    tablette = models.ForeignKey(Tablette, on_delete=models.CASCADE, related_name='items')
    plat = models.ForeignKey(Plat, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('tablette', 'plat')

    def montant(self):
        return self.quantite * self.plat.prix_unitaire

    def __str__(self):
        return f"{self.plat.nom} x {self.quantite}"

# =========================================================
# Commande
# =========================================================
class Commande(models.Model):
    STATUT_CHOICES = (
        ('en_attente', 'En attente'),
        ('servie', 'Servie'),
        ('payee', 'Payée'),
    )

    tablette = models.ForeignKey(Tablette, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date = models.DateTimeField(auto_now_add=True)
    
    serveur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='commandes_servies')
    comptable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements_confirmes')

    def __str__(self):
        try:
            return f"Commande #{self.id} (Table {self.tablette.table.numero_table})"
        except:
            return f"Commande #{self.id}"

# =========================================================
# Items d'une commande
# =========================================================
class CommandeItem(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='items')
    plat = models.ForeignKey(Plat, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)

    def montant(self):
        return self.quantite * self.prix_unitaire

    def __str__(self):
        return f"{self.plat.nom if self.plat else 'Plat'} x {self.quantite}"

# =========================================================
# Caisse
# =========================================================
class Caisse(models.Model):
    solde_actuel = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = "Caisse"

    def __str__(self):
        return f"Solde : {self.solde_actuel} FG"

# =========================================================
# Dépense
# =========================================================
class Depense(models.Model):
    CATEGORIES = (
        ('Achat', 'Achat'),
        ('Salaire', 'Salaire'),
        ('Facture', 'Facture'),
        ('Autre', 'Autre'),
    )

    date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    categorie = models.CharField(max_length=20, choices=CATEGORIES, default='Autre')
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="depenses")

    def __str__(self):
        return f"{self.description} ({self.montant} FG)"

# =========================================================
# Paiement
# =========================================================
class Paiement(models.Model):
    MODE_CHOICES = (('cash', 'Espèces'),)
    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name='paiement')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='cash')

    def __str__(self):
        return f"Paiement #{self.id} ({self.montant} FG)"
  
