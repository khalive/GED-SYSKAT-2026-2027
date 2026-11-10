from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

class Permission(models.Model):
    """Droit unitaire : une action sur une ressource (ex. consulter + document)."""

    code = models.CharField(max_length=100, unique=True)
    ressource = models.CharField(max_length=100)
    action = models.CharField(max_length=50)

    class Meta:
        ordering = ["ressource", "action"]
        verbose_name = "permission métier"
        verbose_name_plural = "permissions métier"

    def __str__(self):
        return self.code

class Role(models.Model):
    """Groupe de permissions attribué aux utilisateurs."""

    code = models.CharField(max_length=50, unique=True)
    libelle = models.CharField(max_length=100)
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name="roles"
    )

    class Meta:
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class Utilisateur(AbstractUser):
    """Compte de connexion de toute personne (personnel, ancien étudiant, externe)."""

    class TypeUtilisateur(models.TextChoices):
        ADMINISTRATEUR = "administrateur", "Administrateur"
        ARCHIVISTE = "archiviste", "Archiviste"
        OPERATEUR = "operateur", "Opérateur de numérisation"
        CONTROLEUR = "controleur", "Contrôleur qualité"
        AUDITEUR = "auditeur", "Auditeur"
        SCOLARITE = "scolarite", "Agent de scolarité"
        FINANCIER = "financier", "Agent financier"
        DIRECTION = "direction", "Direction"
        ANCIEN_ETUDIANT = "ancien_etudiant", "Ancien étudiant"
        EXTERNE = "externe", "Utilisateur externe"

    class Langue(models.TextChoices):
        FRANCAIS = "fr", "Français"
        ARABE = "ar", "العربية"

    email = models.EmailField("adresse e-mail", unique=True)
    type_utilisateur = models.CharField(
        max_length=20,
        choices=TypeUtilisateur.choices,
        default=TypeUtilisateur.EXTERNE,
    )
    telephone = models.CharField(max_length=20, blank=True)
    langue = models.CharField(
        max_length=2, choices=Langue.choices, default=Langue.FRANCAIS
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="utilisateurs")

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    def a_role(self, code):
        """Vrai si l'utilisateur possède le rôle indiqué."""
        return self.roles.filter(code=code).exists()

    def a_permission(self, code):
        """Vrai si l'un des rôles de l'utilisateur accorde la permission."""
        if self.is_superuser:
            return True
        return Permission.objects.filter(
            code=code, roles__utilisateurs=self
        ).exists()


class AncienEtudiant(models.Model):
    """Profil complémentaire d'un utilisateur de type ancien étudiant."""

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profil_etudiant",
    )
    matricule = models.CharField(max_length=30, unique=True)
    cni = models.CharField("numéro CNI", max_length=30, unique=True)
    date_naissance = models.DateField()
    annee_promotion = models.PositiveSmallIntegerField()
    filiere = models.CharField(max_length=100)

    class Meta:
        verbose_name = "ancien étudiant"
        verbose_name_plural = "anciens étudiants"

    def __str__(self):
        return f"{self.matricule} - {self.utilisateur}"


class JournalAudit(models.Model):
    """Trace de chaque action importante (qui, quoi, quand, depuis quelle IP)."""

    class Action(models.TextChoices):
        CONNEXION = "connexion", "Connexion"
        DECONNEXION = "deconnexion", "Déconnexion"
        CONSULTATION = "consultation", "Consultation"
        CREATION = "creation", "Création"
        MODIFICATION = "modification", "Modification"
        SUPPRESSION = "suppression", "Suppression"
        TELECHARGEMENT = "telechargement", "Téléchargement"
        VALIDATION = "validation", "Validation"
        EXPORT = "export", "Export"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions_audit",
    )
    date_action = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    entite_cible = models.CharField(max_length=100, blank=True)
    id_cible = models.PositiveBigIntegerField(null=True, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date_action"]
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        indexes = [
            models.Index(fields=["entite_cible", "id_cible"]),
            models.Index(fields=["-date_action"]),
        ]

    def __str__(self):
        return f"{self.date_action:%d/%m/%Y %H:%M} - {self.utilisateur} - {self.action}"