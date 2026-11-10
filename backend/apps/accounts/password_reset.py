from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def lien_reinitialisation(user):
    """Lien frontend à usage unique, signé par le générateur de jetons Django."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"uid": uid, "token": token})
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/reinitialiser-mot-de-passe?{query}"


def envoyer_lien_reinitialisation(user):
    """Envoie le lien. Lève une exception si le serveur de messagerie échoue."""
    corps = render_to_string(
        "accounts/password_reset_email.txt",
        {"user": user, "lien": lien_reinitialisation(user)},
    )
    send_mail(
        subject="Réinitialisation de votre mot de passe - GED ENG",
        message=corps,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def invalider_refresh_tokens(user):
    """Révoque les jetons de rafraîchissement encore valides après un nouveau mot de passe."""
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)