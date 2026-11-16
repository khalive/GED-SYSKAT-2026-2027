from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    InscriptionView,
    InscriptionAncienEtudiantView,
    JournalAuditViewSet,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    PermissionViewSet,
    ProfilAncienEtudiantView,
    RoleViewSet,
    UtilisateurViewSet,
    VerificationAuthenticiteView,
)

router = DefaultRouter()
router.register("utilisateurs", UtilisateurViewSet, basename="utilisateur")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("journal-audit", JournalAuditViewSet, basename="journal-audit")

urlpatterns = [
    path("auth/register/", InscriptionView.as_view(), name="auth-register"),
    path(
        "anciens-etudiants/inscription/",
        InscriptionAncienEtudiantView.as_view(),
        name="ancien-etudiant-inscription",
    ),
    path(
        "anciens-etudiants/me/",
        ProfilAncienEtudiantView.as_view(),
        name="ancien-etudiant-me",
    ),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "verification/<uuid:code_qr>/",
        VerificationAuthenticiteView.as_view(),
        name="verification-authenticite",
    ),
] + router.urls