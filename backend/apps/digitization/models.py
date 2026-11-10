from django.conf import settings
from django.db import models
from django.utils import timezone


class LotNumerisation(models.Model):
    """Lot de documents numérisés ensemble, avec suivi de progression."""

    class Statut(models.TextChoices):
        CREE = "cree", "Créé"
        EN_COURS = "en_cours", "En cours"
        EN_CONTROLE = "en_controle", "En contrôle"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"

    numero_lot = models.CharField("numéro de lot", max_length=30, unique=True)
    operateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lots_realises",
    )
    date_debut = models.DateField(default=timezone.localdate)
    nb_documents_prevus = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.CREE, db_index=True
    )

    class Meta:
        ordering = ["-date_debut", "numero_lot"]
        verbose_name = "lot de numérisation"
        verbose_name_plural = "lots de numérisation"

    def __str__(self):
        return f"Lot {self.numero_lot}"

    @property
    def nb_documents_importes(self):
        return self.documents.count()

    def calculer_progression(self):
        """Pourcentage de documents importés par rapport au prévu (0 à 100)."""
        if not self.nb_documents_prevus:
            return 0.0
        pourcentage = self.nb_documents_importes / self.nb_documents_prevus * 100
        return round(min(pourcentage, 100.0), 1)


class ControleQualite(models.Model):
    """Contrôle d'un lot par un contrôleur, avec décision."""

    class Decision(models.TextChoices):
        CONFORME = "conforme", "Conforme"
        A_REPRENDRE = "a_reprendre", "À reprendre"
        REJETE = "rejete", "Rejeté"

    lot = models.ForeignKey(
        LotNumerisation, on_delete=models.CASCADE, related_name="controles"
    )
    controleur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="controles_effectues",
    )
    date_controle = models.DateTimeField(auto_now_add=True)
    taux_conformite = models.FloatField(
        help_text="Pourcentage de documents conformes dans l'échantillon (0 à 100)."
    )
    decision = models.CharField(max_length=15, choices=Decision.choices)
    commentaire = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_controle"]
        verbose_name = "contrôle qualité"
        verbose_name_plural = "contrôles qualité"

    def __str__(self):
        return f"{self.lot} - {self.get_decision_display()}"


class TacheOCR(models.Model):
    """Traitement OCR asynchrone d'un document."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ECHEC = "echec", "Échec"

    class Langue(models.TextChoices):
        FRANCAIS = "fra", "Français"
        ARABE = "ara", "Arabe"
        BILINGUE = "ara+fra", "Arabe + Français"

    document = models.ForeignKey(
        "documents.Document", on_delete=models.CASCADE, related_name="taches_ocr"
    )
    langue = models.CharField(
        max_length=10, choices=Langue.choices, default=Langue.BILINGUE
    )
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True
    )
    confiance = models.FloatField(null=True, blank=True)
    debut = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)
    erreur = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "tâche OCR"
        verbose_name_plural = "tâches OCR"

    def __str__(self):
        return f"OCR {self.document.reference} ({self.get_statut_display()})"

    def lancer(self):
        self.statut = self.Statut.EN_COURS
        self.debut = timezone.now()
        self.erreur = ""
        self.save(update_fields=["statut", "debut", "erreur"])

    def terminer(self, confiance):
        self.statut = self.Statut.TERMINEE
        self.confiance = confiance
        self.fin = timezone.now()
        self.save(update_fields=["statut", "confiance", "fin"])

    def echouer(self, message):
        self.statut = self.Statut.ECHEC
        self.erreur = message
        self.fin = timezone.now()
        self.save(update_fields=["statut", "erreur", "fin"])

    def relancer(self):
        self.statut = self.Statut.EN_ATTENTE
        self.save(update_fields=["statut"])