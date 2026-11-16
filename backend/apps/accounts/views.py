import csv
import json
import logging
import smtplib

from django.http import StreamingHttpResponse
from django_filters import rest_framework as django_filters
from django.core.mail import BadHeaderError
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .audit import journaliser
from .models import AncienEtudiant, JournalAudit, Permission, Role, Utilisateur
from .password_reset import envoyer_lien_reinitialisation, invalider_refresh_tokens
from .serializers import (
    ChangePasswordSerializer,
    GestionUtilisateurSerializer,
    InscriptionAncienEtudiantSerializer,
    InscriptionSerializer,
    JournalAuditSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MessageSerializer,
    PermissionSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfilEtudiantSerializer,
    ProfilUpdateSerializer,
    RoleGestionSerializer,
    RoleSimpleSerializer,
    UtilisateurSerializer,
    ROLE_SYSTEME_CODES,
)
from apps.workflow.models import DocumentGenere

logger = logging.getLogger(__name__)

TAG = ["Authentification"]

MESSAGE_GENERIQUE = (
    "Si un compte actif correspond à cette adresse, un e-mail contenant "
    "un lien de réinitialisation vient d'être envoyé."
)
MESSAGE_INSCRIPTION = (
    "Votre demande de création de compte a été reçue. "
    "Elle sera activée après vérification par l'administration."
)


class InscriptionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    @extend_schema(
        tags=TAG,
        summary="Demander la création d'un compte",
        description=(
            "Crée un compte externe inactif, sans rôle attribué. "
            "Un administrateur doit l'activer avant toute connexion."
        ),
        request=InscriptionSerializer,
        responses={
            202: MessageSerializer,
            400: OpenApiResponse(description="Identifiant, adresse ou mot de passe invalide"),
            429: OpenApiResponse(description="Trop de demandes"),
        },
        auth=[],
    )
    @transaction.atomic
    def post(self, request):
        serializer = InscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        journaliser(
            request,
            JournalAudit.Action.CREATION,
            utilisateur=user,
            entite="Utilisateur",
            id_cible=user.pk,
            details={"evenement": "inscription_en_attente"},
        )
        return Response(
            {"detail": MESSAGE_INSCRIPTION},
            status=status.HTTP_202_ACCEPTED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        tags=TAG,
        summary="Se connecter",
        description="Retourne un jeton d'accès (30 min), un jeton de rafraîchissement (1 jour) "
                    "et le profil de l'utilisateur. La connexion est inscrite au journal d'audit.",
        responses={
            200: LoginResponseSerializer,
            401: OpenApiResponse(description="Identifiants invalides ou compte désactivé"),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        journaliser(request, JournalAudit.Action.CONNEXION, utilisateur=serializer.user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=TAG,
    summary="Renouveler le jeton d'accès",
    description="Échange un jeton de rafraîchissement valide contre un nouveau jeton d'accès.",
)
class RefreshView(TokenRefreshView):
    pass


class LogoutView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Se déconnecter",
        description="Invalide le jeton de rafraîchissement fourni.",
        request=LogoutSerializer,
        responses={
            204: OpenApiResponse(description="Déconnexion effectuée"),
            400: OpenApiResponse(description="Jeton invalide ou expiré"),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            jeton = RefreshToken(serializer.validated_data["refresh"])
            if str(jeton["user_id"]) != str(request.user.pk):
                return Response(
                    {"refresh": ["Ce jeton n'appartient pas à votre compte."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            jeton.blacklist()
        except TokenError:
            return Response(
                {"refresh": ["Jeton invalide ou expiré."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        journaliser(request, JournalAudit.Action.DECONNEXION)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Consulter mon profil",
        description="Profil de l'utilisateur connecté, avec ses rôles, ses permissions "
                    "et, pour un ancien étudiant, son profil étudiant.",
        responses=UtilisateurSerializer,
    )
    def get(self, request):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Utilisateur", id_cible=request.user.pk,
            details={"vue": "profil_personnel"},
        )
        return Response(UtilisateurSerializer(request.user).data)

    @extend_schema(
        tags=TAG,
        summary="Modifier mon profil (dont la langue FR/AR)",
        request=ProfilUpdateSerializer,
        responses={
            200: UtilisateurSerializer,
            400: OpenApiResponse(description="Données invalides"),
        },
    )
    @transaction.atomic
    def patch(self, request):
        serializer = ProfilUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        journaliser(
            request, JournalAudit.Action.MODIFICATION,
            entite="Utilisateur", id_cible=request.user.pk,
            details={"champs": list(serializer.validated_data)},
        )
        return Response(UtilisateurSerializer(request.user).data)


class ChangePasswordView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Changer mon mot de passe",
        request=ChangePasswordSerializer,
        responses={
            204: OpenApiResponse(description="Mot de passe modifié"),
            400: OpenApiResponse(description="Ancien mot de passe faux ou nouveau trop faible"),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        request.user.save(update_fields=["password"])
        invalider_refresh_tokens(request.user)
        journaliser(
            request, JournalAudit.Action.MODIFICATION,
            entite="Utilisateur", id_cible=request.user.pk,
            details={"champ": "mot_de_passe"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    """Demande de lien. La réponse est identique que le compte existe ou non."""

    permission_classes = [AllowAny]
    authentication_classes = []  # un jeton expiré dans l'en-tête ne doit pas bloquer l'appel
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=TAG,
        summary="Demander la réinitialisation du mot de passe",
        description="Envoie un e-mail contenant un lien à usage unique, valable 1 heure par défaut. "
                    "La réponse est **toujours la même** (200), que l'adresse corresponde ou non à un compte "
                    "actif, pour ne pas révéler quelles adresses existent. Limité à 5 demandes par heure et par IP.",
        request=PasswordResetRequestSerializer,
        responses={
            200: MessageSerializer,
            400: OpenApiResponse(description="Adresse e-mail mal formée"),
            429: OpenApiResponse(description="Trop de demandes"),
        },
        auth=[],
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = Utilisateur.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            try:
                envoyer_lien_reinitialisation(user)
            except (smtplib.SMTPException, BadHeaderError, OSError):
                # Erreur serveur de messagerie : on la consigne, sans la montrer au client,
                # sinon la réponse trahirait l'existence du compte.
                logger.exception("Échec d'envoi de l'e-mail de réinitialisation (user %s)", user.pk)
            else:
                journaliser(
                    request, JournalAudit.Action.MODIFICATION, utilisateur=user,
                    entite="Utilisateur", id_cible=user.pk,
                    details={"evenement": "demande_reinitialisation_mot_de_passe"},
                )
        return Response({"detail": MESSAGE_GENERIQUE}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=TAG,
        summary="Confirmer la réinitialisation du mot de passe",
        description="Définit le nouveau mot de passe à l'aide du `uid` et du `token` reçus par e-mail. "
                    "Le jeton est à usage unique : il est invalidé dès que le mot de passe change. "
                    "Tous les jetons de rafraîchissement du compte sont également révoqués.",
        request=PasswordResetConfirmSerializer,
        responses={
            204: OpenApiResponse(description="Mot de passe modifié"),
            400: OpenApiResponse(
                description="Lien invalide ou expiré (`token`) ou mot de passe trop faible "
                            "(`nouveau_mot_de_passe`)"
            ),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
        auth=[],
    )
    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        user.save(update_fields=["password"])
        invalider_refresh_tokens(user)
        journaliser(
            request, JournalAudit.Action.MODIFICATION, utilisateur=user,
            entite="Utilisateur", id_cible=user.pk,
            details={"evenement": "mot_de_passe_reinitialise"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermissionMetierRequise(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.is_staff and not user.roles.exists():
            return True
        permission_code = getattr(view, "permission_code", None)
        return bool(permission_code and user.a_permission(permission_code))


class CSVBuffer:
    def write(self, value):
        return value


def valeur_csv_securisee(value):
    texte = str(value) if value is not None else ""
    if texte.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{texte}"
    return texte


class CataloguePagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 200


@extend_schema(tags=["Rôles"])
class RoleViewSet(ModelViewSet):
    serializer_class = RoleGestionSerializer
    permission_classes = [PermissionMetierRequise]
    permission_code = "roles.gerer"
    pagination_class = CataloguePagination
    queryset = Role.objects.prefetch_related("permissions").order_by("libelle")
    search_fields = ["code", "libelle"]
    ordering_fields = ["code", "libelle"]
    ordering = ["libelle"]

    def list(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Role", details={"vue": "liste"},
        )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Role", details={"vue": "detail"},
        )
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        role = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            utilisateur=self.request.user,
            entite="Role",
            id_cible=role.pk,
            details={"code": role.code},
        )

    @transaction.atomic
    def perform_update(self, serializer):
        role = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            utilisateur=self.request.user,
            entite="Role",
            id_cible=role.pk,
            details={"champs": list(serializer.validated_data)},
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.code in ROLE_SYSTEME_CODES:
            raise ValidationError(
                {"code": ["Un rôle système ne peut pas être supprimé."]}
            )
        role_id = instance.pk
        journaliser(
            self.request,
            JournalAudit.Action.SUPPRESSION,
            utilisateur=self.request.user,
            entite="Role",
            id_cible=role_id,
            details={"code": instance.code},
        )
        instance.delete()


@extend_schema(tags=["Permissions"])
class PermissionViewSet(ModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [PermissionMetierRequise]
    permission_code = "permissions.gerer"
    pagination_class = CataloguePagination
    queryset = Permission.objects.order_by("ressource", "action")
    search_fields = ["code", "ressource", "action"]
    ordering_fields = ["code", "ressource", "action"]
    ordering = ["ressource", "action"]

    def list(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Permission", details={"vue": "liste"},
        )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Permission", details={"vue": "detail"},
        )
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        permission = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            utilisateur=self.request.user,
            entite="Permission",
            id_cible=permission.pk,
            details={"code": permission.code},
        )

    @transaction.atomic
    def perform_update(self, serializer):
        permission = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            utilisateur=self.request.user,
            entite="Permission",
            id_cible=permission.pk,
            details={"champs": list(serializer.validated_data)},
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        permission_id = instance.pk
        journaliser(
            self.request,
            JournalAudit.Action.SUPPRESSION,
            utilisateur=self.request.user,
            entite="Permission",
            id_cible=permission_id,
            details={"code": instance.code},
        )
        instance.delete()


class JournalAuditFilter(django_filters.FilterSet):
    action = django_filters.ChoiceFilter(choices=JournalAudit.Action.choices)
    entite_cible = django_filters.CharFilter(lookup_expr="icontains")
    utilisateur = django_filters.NumberFilter(field_name="utilisateur_id")
    depuis = django_filters.IsoDateTimeFilter(field_name="date_action", lookup_expr="gte")
    jusqua = django_filters.IsoDateTimeFilter(field_name="date_action", lookup_expr="lte")

    class Meta:
        model = JournalAudit
        fields = []


@extend_schema(tags=["Journal d’audit"])
class JournalAuditViewSet(ReadOnlyModelViewSet):
    serializer_class = JournalAuditSerializer
    permission_classes = [PermissionMetierRequise]
    permission_code = "audit.consulter"
    queryset = JournalAudit.objects.select_related("utilisateur").all()
    filterset_class = JournalAuditFilter
    search_fields = ["utilisateur__username", "entite_cible", "adresse_ip"]
    ordering_fields = ["date_action", "action", "entite_cible"]
    ordering = ["-date_action"]

    def get_permissions(self):
        self.permission_code = (
            "audit.exporter" if self.action == "exporter" else "audit.consulter"
        )
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="JournalAudit", details={"vue": "liste"},
        )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="JournalAudit", details={"vue": "detail"},
        )
        return super().retrieve(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["get"],
        url_path="export",
        permission_classes=[PermissionMetierRequise],
    )
    def exporter(self, request):
        journaliser(
            request, JournalAudit.Action.EXPORT,
            entite="JournalAudit", details={"format": "csv"},
        )
        lignes = self.filter_queryset(self.get_queryset()).iterator()
        writer = csv.writer(CSVBuffer())

        def generer_csv():
            yield writer.writerow(
                ["date_action", "action", "utilisateur", "entite", "id_cible", "adresse_ip", "details"]
            )
            for ligne in lignes:
                yield writer.writerow(
                    [
                        ligne.date_action.isoformat(),
                        ligne.action,
                        valeur_csv_securisee(
                            ligne.utilisateur.username if ligne.utilisateur else ""
                        ),
                        valeur_csv_securisee(ligne.entite_cible),
                        ligne.id_cible or "",
                        valeur_csv_securisee(ligne.adresse_ip),
                        valeur_csv_securisee(
                            json.dumps(ligne.details, ensure_ascii=False)
                        ),
                    ]
                )

        response = StreamingHttpResponse(
            generer_csv(),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="journal-audit.csv"'
        return response


class InscriptionAncienEtudiantView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    @extend_schema(
        tags=["Anciens étudiants"],
        summary="Déposer une demande d'inscription comme ancien étudiant",
        request=InscriptionAncienEtudiantSerializer,
        responses={
            202: MessageSerializer,
            400: OpenApiResponse(description="Données personnelles ou compte invalides"),
            429: OpenApiResponse(description="Trop de demandes"),
        },
        auth=[],
    )
    @transaction.atomic
    def post(self, request):
        serializer = InscriptionAncienEtudiantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utilisateur = serializer.save()
        journaliser(
            request,
            JournalAudit.Action.CREATION,
            utilisateur=utilisateur,
            entite="AncienEtudiant",
            id_cible=utilisateur.pk,
            details={"evenement": "inscription_en_attente"},
        )
        return Response(
            {"detail": MESSAGE_INSCRIPTION},
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(tags=["Anciens étudiants"])
class ProfilAncienEtudiantView(APIView):
    @extend_schema(
        tags=["Anciens étudiants"],
        summary="Consulter le profil étudiant connecté",
        responses=ProfilEtudiantSerializer,
    )
    def get(self, request):
        if request.user.type_utilisateur != Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT:
            raise NotFound("Aucun profil d'ancien étudiant n'est associé à ce compte.")
        profil = AncienEtudiant.objects.filter(utilisateur=request.user).first()
        if profil is None:
            raise NotFound("Aucun profil d'ancien étudiant n'est associé à ce compte.")
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="AncienEtudiant", id_cible=request.user.pk,
            details={"vue": "profil_personnel"},
        )
        return Response(ProfilEtudiantSerializer(profil).data)

    @extend_schema(
        tags=["Anciens étudiants"],
        summary="Mettre à jour le profil étudiant connecté",
        request=ProfilEtudiantSerializer,
        responses={
            200: ProfilEtudiantSerializer,
            400: OpenApiResponse(description="Données de profil invalides"),
            404: OpenApiResponse(description="Aucun profil étudiant associé au compte"),
        },
    )
    @transaction.atomic
    def patch(self, request):
        if request.user.type_utilisateur != Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT:
            raise NotFound("Aucun profil d'ancien étudiant n'est associé à ce compte.")
        profil = AncienEtudiant.objects.filter(utilisateur=request.user).first()
        if profil is None:
            raise NotFound("Aucun profil d'ancien étudiant n'est associé à ce compte.")
        serializer = ProfilEtudiantSerializer(profil, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        journaliser(
            request,
            JournalAudit.Action.MODIFICATION,
            entite="AncienEtudiant",
            id_cible=request.user.pk,
            details={"champs": list(serializer.validated_data)},
        )
        return Response(serializer.data)


@extend_schema(
    tags=["Utilisateurs"],
    summary="Gérer les comptes utilisateurs",
    description=(
        "Accès réservé aux comptes disposant de la permission `utilisateurs.gerer`. "
        "Liste paginée, recherche, création, consultation et modification. "
        "DELETE désactive le compte sans le supprimer définitivement ; l'administrateur peut le réactiver."
    ),
)
class UtilisateurViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = GestionUtilisateurSerializer
    permission_classes = [PermissionMetierRequise]
    permission_code = "utilisateurs.gerer"
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    queryset = (
        Utilisateur.objects.select_related("profil_etudiant")
        .prefetch_related("roles")
        .order_by("username")
    )
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["is_active", "type_utilisateur", "roles"]
    ordering_fields = ["username", "email", "date_joined", "last_login", "type_utilisateur"]
    ordering = ["username"]

    def list(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Utilisateur", details={"vue": "liste"},
        )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Utilisateur", details={"vue": "detail"},
        )
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=["Utilisateurs"],
        summary="Lister les rôles attribuables",
        responses=RoleSimpleSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="roles")
    def roles_disponibles(self, request):
        journaliser(
            request, JournalAudit.Action.CONSULTATION,
            entite="Role", details={"vue": "roles_attribuables"},
        )
        roles = Role.objects.order_by("libelle")
        return Response(RoleSimpleSerializer(roles, many=True).data)

    def perform_create(self, serializer):
        utilisateur = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            utilisateur=self.request.user,
            entite="Utilisateur",
            id_cible=utilisateur.pk,
            details={
                "champs": list(serializer.validated_data),
                "compte_actif": utilisateur.is_active,
            },
        )

    def perform_update(self, serializer):
        if (
            serializer.instance.pk == self.request.user.pk
            and serializer.validated_data.get("is_active") is False
        ):
            raise ValidationError({"is_active": ["Vous ne pouvez pas désactiver votre propre compte."]})

        champs = list(serializer.validated_data)
        utilisateur = serializer.save()
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            utilisateur=self.request.user,
            entite="Utilisateur",
            id_cible=utilisateur.pk,
            details={"champs": champs},
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError({"is_active": ["Vous ne pouvez pas désactiver votre propre compte."]})
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            utilisateur=self.request.user,
            entite="Utilisateur",
            id_cible=instance.pk,
            details={"evenement": "compte_desactive"},
        )


class VerificationAuthenticiteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Vérification publique"],
        summary="Vérifier l'authenticité d'un document officiel",
        description=(
            "Vérifie un code QR sans donner accès aux archives ni aux données "
            "personnelles du demandeur."
        ),
    )
    def get(self, request, code_qr):
        document = (
            DocumentGenere.objects.select_related("demande")
            .filter(code_qr=code_qr)
            .first()
        )
        if document is None:
            raise NotFound("Aucun document officiel ne correspond à ce code.")

        authentique = document.verifier_authenticite()
        journaliser(
            request,
            JournalAudit.Action.CONSULTATION,
            entite="DocumentGenere",
            id_cible=document.pk,
            details={"evenement": "verification_authenticite", "authentique": authentique},
        )
        return Response(
            {
                "authentique": authentique,
                "numero_officiel": document.numero_officiel,
                "date_generation": document.date_generation,
                "signe": document.signe,
            }
        )