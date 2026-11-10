from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class RegleConservation(models.Model):
    """Durée de conservation et sort final d'un type de document."""

    class SortFinal(models.TextChoices):
        CONSERVER = "conserver", "Conserver définitivement"
        ELIMINER = "eliminer", "Éliminer"
        VERSER = "verser", "Verser aux archives nationales"

    type_document = models.OneToOneField(
        "documents.TypeDocument",
        on_delete=models.CASCADE,
        related_name="regle_conservation",
    )
    libelle = models.CharField("libellé", max_length=150)
    duree_annees = models.PositiveSmallIntegerField(
        "durée (années)",
        null=True,
        blank=True,
        help_text="Laisser vide pour une conservation définitive.",
    )
    sort_final = models.CharField(
        max_length=10, choices=SortFinal.choices, default=SortFinal.CONSERVER
    )

    class Meta:
        verbose_name = "règle de conservation"
        verbose_name_plural = "règles de conservation"

    def __str__(self):
        return f"{self.type_document} : {self.libelle}"


class EmplacementPhysique(models.Model):
    """Localisation de l'original papier (salle, rayon, boîte) et son état."""

    class Etat(models.TextChoices):
        BON = "bon", "Bon"
        MOYEN = "moyen", "Moyen"
        DEGRADE = "degrade", "Dégradé"
        CRITIQUE = "critique", "Critique"

    salle = models.CharField(max_length=50)
    rayon = models.CharField(max_length=50)
    boite = models.CharField("boîte", max_length=50)
    etat = models.CharField(max_length=10, choices=Etat.choices, default=Etat.BON)

    class Meta:
        ordering = ["salle", "rayon", "boite"]
        verbose_name = "emplacement physique"
        verbose_name_plural = "emplacements physiques"
        constraints = [
            models.UniqueConstraint(
                fields=["salle", "rayon", "boite"], name="emplacement_unique"
            )
        ]

    def __str__(self):
        return f"Salle {self.salle} / Rayon {self.rayon} / Boîte {self.boite}"


class BordereauElimination(models.Model):
    """Demande formelle d'élimination de documents arrivés à échéance."""

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"
        EXECUTE = "execute", "Exécuté"

    numero = models.CharField("numéro", max_length=30, unique=True)
    date_creation = models.DateField(default=timezone.localdate)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON, db_index=True
    )
    etabli_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bordereaux_etablis",
    )

    class Meta:
        ordering = ["-date_creation", "numero"]
        verbose_name = "bordereau d'élimination"
        verbose_name_plural = "bordereaux d'élimination"

    def __str__(self):
        return f"Bordereau {self.numero}"

    def valider(self):
        if self.statut != self.Statut.BROUILLON:
            raise ValueError("Seul un bordereau en brouillon peut être validé.")
        if not self.lignes.exists():
            raise ValueError("Un bordereau doit contenir au moins un document.")
        self.statut = self.Statut.VALIDE
        self.save(update_fields=["statut"])

    def rejeter(self):
        if self.statut != self.Statut.BROUILLON:
            raise ValueError("Seul un bordereau en brouillon peut être rejeté.")
        self.statut = self.Statut.REJETE
        self.save(update_fields=["statut"])

    @transaction.atomic
    def executer(self):
        """Marque tous les documents du bordereau comme éliminés."""
        from apps.documents.models import Document

        if self.statut != self.Statut.VALIDE:
            raise ValueError("Le bordereau doit être validé avant exécution.")
        ids = self.lignes.values_list("document_id", flat=True)
        Document.objects.filter(pk__in=ids).update(statut=Document.Statut.ELIMINE)
        self.statut = self.Statut.EXECUTE
        self.save(update_fields=["statut"])


class LigneBordereau(models.Model):
    """Un document concerné par un bordereau d'élimination."""

    bordereau = models.ForeignKey(
        BordereauElimination, on_delete=models.CASCADE, related_name="lignes"
    )
    document = models.ForeignKey(
        "documents.Document", on_delete=models.PROTECT, related_name="lignes_bordereau"
    )
    observation = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name = "ligne de bordereau"
        verbose_name_plural = "lignes de bordereau"
        constraints = [
            models.UniqueConstraint(
                fields=["bordereau", "document"], name="document_unique_par_bordereau"
            )
        ]

    def __str__(self):
        return f"{self.bordereau} : {self.document.reference}"