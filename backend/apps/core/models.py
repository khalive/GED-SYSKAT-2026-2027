from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """Message destiné à un utilisateur (e-mail, SMS ou interne)."""

    class Canal(models.TextChoices):
        EMAIL = "email", "E-mail"
        SMS = "sms", "SMS"
        INTERNE = "interne", "Dans l'application"

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    canal = models.CharField(max_length=10, choices=Canal.choices, default=Canal.INTERNE)
    sujet = models.CharField(max_length=200)
    message = models.TextField()
    lue = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.sujet} -> {self.destinataire}"

    def envoyer(self):
        """Enregistre l'envoi. L'envoi réel (SMTP, SMS) sera branché plus tard."""
        self.date_envoi = timezone.now()
        self.save(update_fields=["date_envoi"])

    def marquer_lue(self):
        self.lue = True
        self.save(update_fields=["lue"])


class Sauvegarde(models.Model):
    """Registre des sauvegardes du système."""

    class TypeSauvegarde(models.TextChoices):
        COMPLETE = "complete", "Complète"
        BASE_DONNEES = "base_donnees", "Base de données"
        FICHIERS = "fichiers", "Fichiers"

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ECHEC = "echec", "Échec"

    type = models.CharField(max_length=15, choices=TypeSauvegarde.choices)
    date = models.DateTimeField(default=timezone.now)
    emplacement = models.CharField(max_length=300, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS
    )
    verifiee = models.BooleanField(default=False)
    lancee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sauvegardes",
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Sauvegarde {self.get_type_display()} du {self.date:%d/%m/%Y %H:%M}"

    def restaurer(self):
        """La restauration réelle (pg_restore + copie des fichiers) viendra à l'étape déploiement."""
        raise NotImplementedError("Restauration à implémenter à l'étape de déploiement.")