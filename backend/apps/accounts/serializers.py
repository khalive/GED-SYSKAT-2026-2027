import binascii

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AncienEtudiant, Permission, Role, Utilisateur


class RoleSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "code", "libelle")


class ProfilEtudiantSerializer(serializers.ModelSerializer):
    class Meta:
        model = AncienEtudiant
        fields = ("matricule", "cni", "date_naissance", "annee_promotion", "filiere")


class UtilisateurSerializer(serializers.ModelSerializer):
    """Profil complet de l'utilisateur connecté."""

    roles = RoleSimpleSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    profil_etudiant = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "type_utilisateur", "telephone", "langue",
            "roles", "permissions", "profil_etudiant",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, obj):
        if obj.is_superuser:
            codes = Permission.objects.values_list("code", flat=True)
        else:
            codes = Permission.objects.filter(roles__utilisateurs=obj).values_list(
                "code", flat=True
            )
        return sorted(set(codes))

    @extend_schema_field(ProfilEtudiantSerializer(allow_null=True))
    def get_profil_etudiant(self, obj):
        try:
            return ProfilEtudiantSerializer(obj.profil_etudiant).data
        except ObjectDoesNotExist:
            return None


class ProfilUpdateSerializer(serializers.ModelSerializer):
    """Champs que l'utilisateur peut modifier lui-même."""

    class Meta:
        model = Utilisateur
        fields = ("first_name", "last_name", "telephone", "langue")


class LoginSerializer(TokenObtainPairSerializer):
    """Ajoute le profil utilisateur à la réponse de connexion."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UtilisateurSerializer(self.user).data
        return data


class LoginResponseSerializer(serializers.Serializer):
    """Sert uniquement à documenter la réponse de /login/ dans Swagger."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UtilisateurSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(write_only=True)

    def validate_ancien_mot_de_passe(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value

    def validate_nouveau_mot_de_passe(self, value):
        validate_password(value, self.context["request"].user)
        return value


class MessageSerializer(serializers.Serializer):
    """Réponse générique, utilisée pour la documentation Swagger."""

    detail = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    nouveau_mot_de_passe = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self._utilisateur(attrs["uid"])
        if (
                user is None
                or not user.is_active
                or not default_token_generator.check_token(user, attrs["token"])
        ):
            raise serializers.ValidationError(
                {"token": ["Lien invalide ou expiré. Demandez un nouveau lien."]}
            )
        try:
            validate_password(attrs["nouveau_mot_de_passe"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"nouveau_mot_de_passe": list(exc.messages)}
            )
        attrs["user"] = user
        return attrs

    @staticmethod
    def _utilisateur(uid):
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            return Utilisateur.objects.get(pk=pk)
        except (
                TypeError,
                ValueError,
                OverflowError,
                binascii.Error,
                Utilisateur.DoesNotExist,
        ):
            return None