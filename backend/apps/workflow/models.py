import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

from apps.accounts.models import Utilisateur


def generer_numero_demande():
    return f"DUP-{timezone.now():%Y}-{uuid.uuid4().hex[:6].upper()}"


class DemandeDuplicata(models.Model):
    """Demande d'un ancien étudiant (duplicata, relevé, attestation)."""

    class TypeDemande(models.TextChoices):
        DUPLICATA_DIPLOME = "duplicata_diplome", "Duplicata de diplôme"
        RELEVE_NOTES = "releve_notes", "Relevé de notes"
        ATTESTATION_SCOLARITE = "attestation_scolarite", "Attestation de scolarité"
        ATTESTATION_REUSSITE = "attestation_reussite", "Attestation de réussite"
        COPIE_CERTIFIEE = "copie_certifiee", "Copie certifiée conforme"

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        SOUMISE = "soumise", "Soumise"
        EN_VERIFICATION = "en_verification", "En vérification"
        PAIEMENT_EN_ATTENTE = "paiement_en_attente", "Paiement en attente"
        EN_VALIDATION = "en_validation", "En validation"
        ACCEPTEE = "acceptee", "Acceptée"
        REJETEE = "rejetee", "Rejetée"
        LIVREE = "livree", "Livrée"
        ANNULEE = "annulee", "Annulée"

    numero_demande = models.CharField(
        max_length=30, unique=True, default=generer_numero_demande, editable=False
    )
    demandeur = models.ForeignKey(
        "accounts.AncienEtudiant",
        on_delete=models.PROTECT,
        related_name="demandes",
    )
    type_demande = models.CharField(max_length=25, choices=TypeDemande.choices)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON, db_index=True
    )
    motif = models.TextField(blank=True)
    date_depot = models.DateTimeField(null=True, blank=True)
    document_original = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandes",
        help_text="Original retrouvé dans les archives.",
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = "demande de duplicata"
        verbose_name_plural = "demandes de duplicata"

    def __str__(self):
        return f"{self.numero_demande} ({self.get_statut_display()})"

    def soumettre(self):
        if self.statut != self.Statut.BROUILLON:
            raise ValueError("Seul un brouillon peut être soumis.")
        self.statut = self.Statut.SOUMISE
        self.date_depot = timezone.now()
        self.save(update_fields=["statut", "date_depot"])

    def changer_statut(self, nouveau_statut):
        if nouveau_statut not in self.Statut.values:
            raise ValueError(f"Statut inconnu : {nouveau_statut}")
        self.statut = nouveau_statut
        self.save(update_fields=["statut"])


class PieceJustificative(models.Model):
    """Pièce jointe à la demande (CNI, reçu, déclaration de perte)."""

    class TypePiece(models.TextChoices):
        CNI = "cni", "Carte nationale d'identité"
        RECU_PAIEMENT = "recu_paiement", "Reçu de paiement"
        DECLARATION_PERTE = "declaration_perte", "Déclaration de perte"
        AUTRE = "autre", "Autre"

    demande = models.ForeignKey(
        DemandeDuplicata, on_delete=models.CASCADE, related_name="pieces"
    )
    type_piece = models.CharField(max_length=20, choices=TypePiece.choices)
    fichier = models.FileField(upload_to="pieces/")
    verifiee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "pièce justificative"
        verbose_name_plural = "pièces justificatives"

    def __str__(self):
        return f"{self.get_type_piece_display()} - {self.demande.numero_demande}"


class EtapeWorkflow(models.Model):
    """Étape de validation d'une demande (vérification, paiement, direction)."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"

    demande = models.ForeignKey(
        DemandeDuplicata, on_delete=models.CASCADE, related_name="etapes"
    )
    ordre = models.PositiveSmallIntegerField()
    role_requis = models.CharField(
        max_length=20, choices=Utilisateur.TypeUtilisateur.choices
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    assignee_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapes_assignees",
    )
    date_action = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        ordering = ["demande", "ordre"]
        verbose_name = "étape de workflow"
        verbose_name_plural = "étapes de workflow"
        constraints = [
            models.UniqueConstraint(
                fields=["demande", "ordre"], name="etape_unique_par_demande"
            )
        ]

    def __str__(self):
        return f"{self.demande.numero_demande} - étape {self.ordre}"

    def _cloturer(self, utilisateur, statut, commentaire=""):
        if not utilisateur.a_role(self.role_requis):
            raise PermissionDenied(
                f"Le rôle {self.role_requis} est requis pour traiter cette étape."
            )
        if self.role_requis == Utilisateur.TypeUtilisateur.DIRECTION and utilisateur.a_role(
            "administrateur"
        ):
            raise PermissionDenied(
                "L'administration technique ne peut pas traiter les étapes réservées à la Direction."
            )
        if self.statut != self.Statut.EN_ATTENTE:
            raise ValueError("Cette étape a déjà été traitée.")
        self.statut = statut
        self.assignee_a = utilisateur
        self.date_action = timezone.now()
        self.commentaire = commentaire
        self.save()

    def approuver(self, utilisateur, commentaire=""):
        self._cloturer(utilisateur, self.Statut.APPROUVEE, commentaire)

    def rejeter(self, utilisateur, motif):
        self._cloturer(utilisateur, self.Statut.REJETEE, motif)


class Paiement(models.Model):
    """Règlement des frais d'une demande."""

    class Mode(models.TextChoices):
        ESPECES = "especes", "Espèces"
        VIREMENT = "virement", "Virement"
        MOBILE_MONEY = "mobile_money", "Mobile money"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDE = "valide", "Validé"
        REFUSE = "refuse", "Refusé"

    demande = models.OneToOneField(
        DemandeDuplicata, on_delete=models.CASCADE, related_name="paiement"
    )
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=15, choices=Mode.choices)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    numero_recu = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.demande.numero_demande} - {self.montant} MRU"

    def verifier(self):
        """Un paiement est valide s'il est confirmé et possède un numéro de reçu."""
        return self.statut == self.Statut.VALIDE and bool(self.numero_recu)


class DocumentGenere(models.Model):
    """Document officiel produit, avec code de vérification (QR) et signature."""

    demande = models.OneToOneField(
        DemandeDuplicata, on_delete=models.PROTECT, related_name="document_genere"
    )
    numero_officiel = models.CharField(max_length=40, unique=True)
    code_qr = models.UUIDField(
        "code de vérification", default=uuid.uuid4, unique=True, editable=False
    )
    fichier = models.FileField(upload_to="generes/", blank=True)
    signe = models.BooleanField(default=False)
    signe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_signes",
    )
    date_generation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "document généré"
        verbose_name_plural = "documents générés"

    def __str__(self):
        return self.numero_officiel

    def signer(self, utilisateur):
        if (
            not utilisateur.a_role("direction")
            or utilisateur.a_role("administrateur")
        ):
            raise PermissionDenied(
                "Seule la Direction peut signer un document officiel."
            )
        self.signe = True
        self.signe_par = utilisateur
        self.save(update_fields=["signe", "signe_par"])

    def verifier_authenticite(self):
        """Authentique si le document est signé par un utilisateur identifié."""
        return self.signe and self.signe_par_id is not None