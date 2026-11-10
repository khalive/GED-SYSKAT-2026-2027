import logging
import smtplib

from django.core.mail import BadHeaderError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .audit import journaliser
from .models import JournalAudit, Utilisateur
from .password_reset import envoyer_lien_reinitialisation, invalider_refresh_tokens
from .serializers import (
    ChangePasswordSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MessageSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfilUpdateSerializer,
    UtilisateurSerializer,
)

logger = logging.getLogger(__name__)

TAG = ["Authentification"]

MESSAGE_GENERIQUE = (
    "Si un compte actif correspond à cette adresse, un e-mail contenant "
    "un lien de réinitialisation vient d'être envoyé."
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
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
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
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        request.user.save(update_fields=["password"])
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