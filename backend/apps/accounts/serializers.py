import binascii

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AncienEtudiant, JournalAudit, Permission, Role, Utilisateur
from .password_reset import invalider_refresh_tokens

ROLE_SYSTEME_CODES = {
    "administrateur",
    "auditeur",
    "direction",
    "archiviste",
    "operateur",
    "controleur",
    "scolarite",
    "financier",
    "ancien_etudiant",
    "externe",
    "super_administrateur",
    "agent_rh",
    "enseignant",
    "visiteur_lecture_seule",
}


def valider_separation_taches(codes):
    conflits = (
        (
            "eliminations.etablir",
            {"eliminations.valider"},
            "L'établissement et la validation d'une élimination doivent rester séparés.",
        ),
        (
            "utilisateurs.gerer",
            {"documents.signer", "eliminations.valider"},
            "L'administration technique ne peut pas signer ni valider une élimination.",
        ),
        (
            "documents.signer",
            {
                "lots.creer",
                "documents.importer",
                "documents.metadonnees_saisir",
                "ocr.corriger",
            },
            "La Direction ne peut pas exercer les tâches de numérisation.",
        ),
        (
            "lots.creer",
            {"lots.controle", "lots.valider", "lots.rejeter"},
            "La numérisation et le contrôle qualité doivent rester séparés.",
        ),
        (
            "documents.importer",
            {"lots.controle", "lots.valider", "lots.rejeter"},
            "La numérisation et le contrôle qualité doivent rester séparés.",
        ),
        (
            "documents.metadonnees_saisir",
            {"lots.controle", "lots.valider", "lots.rejeter"},
            "La numérisation et le contrôle qualité doivent rester séparés.",
        ),
        (
            "ocr.corriger",
            {"lots.controle", "lots.valider", "lots.rejeter"},
            "La numérisation et le contrôle qualité doivent rester séparés.",
        ),
    )
    for droit_etablissement, droits_validation, message in conflits:
        if droit_etablissement in codes and codes.intersection(droits_validation):
            raise serializers.ValidationError(message)


def attribuer_role_type(utilisateur):
    role = Role.objects.filter(code=utilisateur.type_utilisateur).first()
    if role is not None:
        utilisateur.roles.add(role)


def valider_date_naissance(value):
    if value > timezone.localdate():
        raise serializers.ValidationError("La date de naissance ne peut pas être future.")
    return value


def valider_annee_promotion(value):
    if value > timezone.localdate().year:
        raise serializers.ValidationError("L’année de promotion ne peut pas être future.")
    return value


class RoleSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "code", "libelle")


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "ressource", "action")
        read_only_fields = ("id",)


class RoleGestionSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        required=False,
        source="permissions",
        write_only=True,
    )

    class Meta:
        model = Role
        fields = ("id", "code", "libelle", "permissions", "permission_ids")
        read_only_fields = ("id",)

    def validate_code(self, value):
        if self.instance and self.instance.code in ROLE_SYSTEME_CODES:
            if value != self.instance.code:
                raise serializers.ValidationError(
                    "Le code d'un rôle système ne peut pas être modifié."
                )
        return value

    def validate(self, attrs):
        permissions = attrs.get(
            "permissions",
            self.instance.permissions.all() if self.instance is not None else [],
        )
        permission_codes = {permission.code for permission in permissions}
        valider_separation_taches(permission_codes)
        if self.instance is not None:
            for utilisateur in self.instance.utilisateurs.prefetch_related(
                "roles__permissions"
            ):
                autres_codes = set(
                    Permission.objects.filter(roles__utilisateurs=utilisateur)
                    .exclude(roles=self.instance)
                    .values_list("code", flat=True)
                )
                try:
                    valider_separation_taches(autres_codes | permission_codes)
                except serializers.ValidationError as exc:
                    raise serializers.ValidationError(
                        {"permission_ids": exc.detail}
                    )
        return attrs


class ProfilEtudiantSerializer(serializers.ModelSerializer):
    class Meta:
        model = AncienEtudiant
        fields = ("matricule", "cni", "date_naissance", "annee_promotion", "filiere")

    def validate_date_naissance(self, value):
        return valider_date_naissance(value)

    def validate_annee_promotion(self, value):
        return valider_annee_promotion(value)


class JournalAuditSerializer(serializers.ModelSerializer):
    utilisateur_id = serializers.IntegerField(read_only=True, allow_null=True)
    utilisateur_username = serializers.CharField(
        source="utilisateur.username", read_only=True, allow_null=True
    )

    class Meta:
        model = JournalAudit
        fields = (
            "id", "date_action", "action", "entite_cible", "id_cible",
            "adresse_ip", "details", "utilisateur_id", "utilisateur_username",
        )
        read_only_fields = fields


class InscriptionAncienEtudiantSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    telephone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    matricule = serializers.CharField(max_length=30)
    cni = serializers.CharField(max_length=30)
    date_naissance = serializers.DateField()
    annee_promotion = serializers.IntegerField(min_value=1950, max_value=2100)
    filiere = serializers.CharField(max_length=100)

    def validate_username(self, value):
        if Utilisateur.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return value

    def validate_email(self, value):
        if Utilisateur.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return value

    def validate_matricule(self, value):
        if AncienEtudiant.objects.filter(matricule__iexact=value).exists():
            raise serializers.ValidationError("Ce matricule est déjà enregistré.")
        return value

    def validate_cni(self, value):
        if AncienEtudiant.objects.filter(cni__iexact=value).exists():
            raise serializers.ValidationError("Cette pièce d'identité est déjà enregistrée.")
        return value

    def validate_date_naissance(self, value):
        return valider_date_naissance(value)

    def validate_annee_promotion(self, value):
        return valider_annee_promotion(value)

    def validate(self, attrs):
        utilisateur = Utilisateur(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
        )
        try:
            validate_password(attrs["password"], utilisateur)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        mot_de_passe = validated_data.pop("password")
        profil_data = {
            "matricule": validated_data.pop("matricule"),
            "cni": validated_data.pop("cni"),
            "date_naissance": validated_data.pop("date_naissance"),
            "annee_promotion": validated_data.pop("annee_promotion"),
            "filiere": validated_data.pop("filiere"),
        }
        utilisateur = Utilisateur.objects.create_user(
            **validated_data,
            password=mot_de_passe,
            type_utilisateur=Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT,
            is_active=False,
        )
        attribuer_role_type(utilisateur)
        AncienEtudiant.objects.create(utilisateur=utilisateur, **profil_data)
        return utilisateur


class UtilisateurSerializer(serializers.ModelSerializer):
    """Profil complet de l'utilisateur connecté."""

    roles = RoleSimpleSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    profil_etudiant = serializers.SerializerMethodField()
    is_staff = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "type_utilisateur", "telephone", "langue",
            "roles", "permissions", "profil_etudiant", "is_staff",
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

    @extend_schema_field(serializers.BooleanField())
    def get_is_staff(self, obj):
        return obj.is_staff or obj.is_superuser

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


class GestionUtilisateurSerializer(serializers.ModelSerializer):
    """Représentation administrative d'un compte utilisateur."""

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    profil_etudiant = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False
    )
    roles = RoleSimpleSerializer(many=True, read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Role.objects.all(),
        required=False,
        source="roles",
        write_only=True,
    )

    class Meta:
        model = Utilisateur
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "type_utilisateur", "telephone", "langue", "is_active",
            "roles", "role_ids", "profil_etudiant", "password", "date_joined", "last_login",
        )
        read_only_fields = ("id", "roles", "date_joined", "last_login")

    @extend_schema_field(ProfilEtudiantSerializer(allow_null=True))
    def get_profil_etudiant(self, obj):
        try:
            return ProfilEtudiantSerializer(obj.profil_etudiant).data
        except ObjectDoesNotExist:
            return None

    def validate_username(self, value):
        utilisateurs = Utilisateur.objects.filter(username__iexact=value)
        if self.instance is not None:
            utilisateurs = utilisateurs.exclude(pk=self.instance.pk)
        if utilisateurs.exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return value

    def validate_email(self, value):
        utilisateurs = Utilisateur.objects.filter(email__iexact=value)
        if self.instance is not None:
            utilisateurs = utilisateurs.exclude(pk=self.instance.pk)
        if utilisateurs.exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return value

    def validate(self, attrs):
        type_utilisateur = attrs.get(
            "type_utilisateur",
            self.instance.type_utilisateur if self.instance is not None else None,
        )
        if type_utilisateur == Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT and (
            self.instance is None
            or not AncienEtudiant.objects.filter(utilisateur=self.instance).exists()
        ):
            raise serializers.ValidationError(
                {
                    "type_utilisateur": [
                        "Un profil étudiant doit être créé via l'inscription dédiée."
                    ]
                }
            )

        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": ["Ce champ est obligatoire."]})

        if password:
            utilisateur = self.instance
            candidat = Utilisateur(
                username=attrs.get("username", getattr(utilisateur, "username", "")),
                email=attrs.get("email", getattr(utilisateur, "email", "")),
                first_name=attrs.get("first_name", getattr(utilisateur, "first_name", "")),
                last_name=attrs.get("last_name", getattr(utilisateur, "last_name", "")),
            )
            try:
                validate_password(password, candidat)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})

        roles = attrs.get(
            "roles",
            list(self.instance.roles.all()) if self.instance is not None else [],
        )
        if self.instance is not None and type_utilisateur != self.instance.type_utilisateur:
            ancien_role = Role.objects.filter(
                code=self.instance.type_utilisateur
            ).first()
            if ancien_role is not None:
                roles = [role for role in roles if role.pk != ancien_role.pk]
        role_type = Role.objects.filter(code=type_utilisateur).first()
        if role_type is not None and all(role.pk != role_type.pk for role in roles):
            roles.append(role_type)
        codes = set(
            Permission.objects.filter(roles__in=roles).values_list("code", flat=True)
        )
        try:
            valider_separation_taches(codes)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"role_ids": exc.detail})
        return attrs

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password")
        validated_data.setdefault("is_active", False)
        utilisateur = Utilisateur.objects.create_user(
            **validated_data,
            password=password,
        )
        utilisateur.roles.set(roles)
        attribuer_role_type(utilisateur)
        return utilisateur

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", None)
        ancien_type = instance.type_utilisateur
        roles_a_conserver = list(instance.roles.all()) if roles is None else list(roles)
        utilisateur = super().update(instance, validated_data)
        if ancien_type != utilisateur.type_utilisateur:
            ancien_role = Role.objects.filter(code=ancien_type).first()
            if ancien_role is not None:
                roles_a_conserver = [
                    role for role in roles_a_conserver if role.pk != ancien_role.pk
                ]
        role_type = Role.objects.filter(code=utilisateur.type_utilisateur).first()
        if role_type is not None and all(
            role.pk != role_type.pk for role in roles_a_conserver
        ):
            roles_a_conserver.append(role_type)
        utilisateur.roles.set(roles_a_conserver)
        if password:
            utilisateur.set_password(password)
            utilisateur.save(update_fields=["password"])
            invalider_refresh_tokens(utilisateur)
        return utilisateur


class LoginSerializer(TokenObtainPairSerializer):
    """Ajoute le profil utilisateur à la réponse de connexion."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UtilisateurSerializer(self.user).data
        return data


class InscriptionSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if Utilisateur.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return value

    def validate_email(self, value):
        if Utilisateur.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return value

    def validate(self, attrs):
        candidat = Utilisateur(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
        )
        try:
            validate_password(attrs["password"], candidat)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        utilisateur = Utilisateur.objects.create_user(
            **validated_data,
            password=password,
            type_utilisateur=Utilisateur.TypeUtilisateur.EXTERNE,
            is_active=False,
        )
        attribuer_role_type(utilisateur)
        return utilisateur


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