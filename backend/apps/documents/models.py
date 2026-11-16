import hashlib

from django.conf import settings
from django.db import models


class Classification(models.TextChoices):
    PUBLIC = "public", "Public"
    INTERNE = "interne", "Interne"
    CONFIDENTIEL = "confidentiel", "Confidentiel"


class TypeDocument(models.Model):
    """Catégorie de document (diplôme, relevé de notes, PV...)."""

    code = models.CharField(max_length=50, unique=True)
    libelle = models.CharField("libellé (français)", max_length=150)
    libelle_ar = models.CharField("libellé (arabe)", max_length=150, blank=True)
    confidentiel = models.BooleanField(default=False)
    roles_autorises = models.ManyToManyField(
        "accounts.Role",
        blank=True,
        related_name="types_documents",
        help_text="Si vide, tous les rôles ayant la permission peuvent y accéder.",
    )

    class Meta:
        ordering = ["libelle"]
        verbose_name = "type de document"
        verbose_name_plural = "types de documents"

    def __str__(self):
        return self.libelle


class ChampMetadonnee(models.Model):
    """Champ de métadonnées exigé pour un type de document."""

    class TypeChamp(models.TextChoices):
        TEXTE = "texte", "Texte"
        NOMBRE = "nombre", "Nombre"
        DATE = "date", "Date"
        BOOLEEN = "booleen", "Oui / Non"

    type_document = models.ForeignKey(
        TypeDocument, on_delete=models.CASCADE, related_name="champs"
    )
    nom = models.CharField(max_length=100, help_text="Clé technique, ex. : mention")
    type_champ = models.CharField(
        max_length=10, choices=TypeChamp.choices, default=TypeChamp.TEXTE
    )
    obligatoire = models.BooleanField(default=False)

    class Meta:
        ordering = ["type_document", "nom"]
        verbose_name = "champ de métadonnée"
        verbose_name_plural = "champs de métadonnées"
        constraints = [
            models.UniqueConstraint(
                fields=["type_document", "nom"], name="champ_unique_par_type"
            )
        ]

    def __str__(self):
        return f"{self.type_document} : {self.nom}"


class Dossier(models.Model):
    """Conteneur hiérarchique (dossier étudiant, administratif, financier...)."""

    class TypeDossier(models.TextChoices):
        ETUDIANT = "etudiant", "Dossier étudiant"
        PERSONNEL = "personnel", "Dossier du personnel"
        ADMINISTRATIF = "administratif", "Dossier administratif"
        FINANCIER = "financier", "Dossier financier"

    cote = models.CharField(max_length=50, unique=True)
    intitule = models.CharField("intitulé", max_length=200)
    type_dossier = models.CharField(
        max_length=20, choices=TypeDossier.choices, default=TypeDossier.ADMINISTRATIF
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sous_dossiers",
    )
    roles_autorises = models.ManyToManyField(
        "accounts.Role",
        blank=True,
        related_name="dossiers",
        help_text="Si vide, le dossier hérite des restrictions du type de document et de ses parents.",
    )
    matricule = models.CharField(
        max_length=30, blank=True, db_index=True,
        help_text="Renseigné pour les dossiers étudiants.",
    )
    annee_debut = models.PositiveSmallIntegerField(null=True, blank=True)
    annee_fin = models.PositiveSmallIntegerField(null=True, blank=True)
    classification = models.CharField(
        max_length=15, choices=Classification.choices, default=Classification.INTERNE
    )

    class Meta:
        ordering = ["cote"]

    def __str__(self):
        return f"{self.cote} - {self.intitule}"

    def ajouter_document(self, document):
        document.dossier = self
        document.save(update_fields=["dossier"])


class Document(models.Model):
    """Fiche d'un document archivé (métadonnées, statut, empreinte d'intégrité)."""

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        EN_INDEXATION = "en_indexation", "En indexation"
        EN_CONTROLE = "en_controle", "En contrôle"
        VALIDE = "valide", "Validé"
        ARCHIVE = "archive", "Archivé"
        A_ELIMINER = "a_eliminer", "À éliminer"
        ELIMINE = "elimine", "Éliminé"

    class Langue(models.TextChoices):
        FRANCAIS = "fr", "Français"
        ARABE = "ar", "Arabe"
        BILINGUE = "fr-ar", "Bilingue"

    reference = models.CharField(max_length=60, unique=True)
    titre = models.CharField(max_length=250)
    titre_ar = models.CharField("titre (arabe)", max_length=250, blank=True)
    type_document = models.ForeignKey(
        TypeDocument, on_delete=models.PROTECT, related_name="documents"
    )
    dossier = models.ForeignKey(
        Dossier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    lot = models.ForeignKey(
        "digitization.LotNumerisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    emplacement = models.ForeignKey(
        "conservation.EmplacementPhysique",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        help_text="Emplacement de l'original papier.",
    )
    langue = models.CharField(
        max_length=5, choices=Langue.choices, default=Langue.FRANCAIS
    )
    annee_document = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON, db_index=True
    )
    classification = models.CharField(
        max_length=15, choices=Classification.choices, default=Classification.INTERNE
    )
    metadonnees = models.JSONField(default=dict, blank=True)
    empreinte_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="documents_crees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        indexes = [models.Index(fields=["annee_document", "statut"])]

    def __str__(self):
        return f"{self.reference} - {self.titre}"

    @property
    def version_courante(self):
        return self.versions.filter(courante=True).first()

    def verifier_integrite(self):
        """Recalcule le hash du fichier courant et le compare à l'empreinte stockée."""
        version = self.version_courante
        if version is None or not version.fichier:
            return False
        return version.calculer_empreinte() == version.empreinte_sha256


def chemin_fichier(instance, nom_fichier):
    return f"documents/{instance.document.reference}/v{instance.numero_version}/{nom_fichier}"


class VersionDocument(models.Model):
    """Version du fichier numérisé (format, PDF/A, empreinte)."""

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="versions"
    )
    numero_version = models.PositiveIntegerField(default=1)
    fichier = models.FileField(upload_to=chemin_fichier)
    format = models.CharField(max_length=10, blank=True)
    pdf_a = models.BooleanField("PDF/A", default=False)
    empreinte_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    courante = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "-numero_version"]
        verbose_name = "version de document"
        verbose_name_plural = "versions de documents"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "numero_version"], name="version_unique_par_document"
            ),
            models.UniqueConstraint(
                fields=["document"],
                condition=models.Q(courante=True),
                name="une_seule_version_courante",
            ),
        ]

    def __str__(self):
        return f"{self.document.reference} v{self.numero_version}"

    def calculer_empreinte(self):
        sha = hashlib.sha256()
        self.fichier.open("rb")
        try:
            for bloc in self.fichier.chunks():
                sha.update(bloc)
        finally:
            self.fichier.close()
        return sha.hexdigest()

    def save(self, *args, **kwargs):
        est_nouveau = self.pk is None
        if est_nouveau and self.courante:
            # une seule version courante par document
            VersionDocument.objects.filter(
                document=self.document, courante=True
            ).update(courante=False)
        if est_nouveau and self.fichier:
            self.empreinte_sha256 = self.calculer_empreinte()
            if not self.format:
                self.format = self.fichier.name.rsplit(".", 1)[-1].lower()
        super().save(*args, **kwargs)
        if est_nouveau and self.courante:
            Document.objects.filter(pk=self.document_id).update(
                empreinte_sha256=self.empreinte_sha256
            )


class Page(models.Model):
    """Page d'une version : image et texte reconnu par OCR."""

    version = models.ForeignKey(
        VersionDocument, on_delete=models.CASCADE, related_name="pages"
    )
    numero = models.PositiveIntegerField()
    image = models.ImageField(upload_to="pages/", blank=True)
    texte_ocr = models.TextField(blank=True)
    confiance_ocr = models.FloatField(null=True, blank=True)
    rotation = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ["version", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "numero"], name="page_unique_par_version"
            )
        ]

    def __str__(self):
        return f"{self.version} - page {self.numero}"