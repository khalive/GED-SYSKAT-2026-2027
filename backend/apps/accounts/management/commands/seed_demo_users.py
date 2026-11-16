import secrets
import string
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.accounts.models import AncienEtudiant, Role, Utilisateur


UTILISATEURS_DEMO = (
    ("ged-demo-administrateur", "Administrateur Démo", "administrateur", ("administrateur",), None),
    ("ged-demo-auditeur", "Auditeur Démo", "auditeur", ("auditeur",), None),
    ("ged-demo-direction", "Direction Démo", "direction", ("direction",), None),
    ("ged-demo-archiviste", "Archiviste Démo", "archiviste", ("archiviste",), None),
    ("ged-demo-operateur", "Opérateur Démo", "operateur", ("operateur",), None),
    ("ged-demo-controleur", "Contrôleur Démo", "controleur", ("controleur",), None),
    ("ged-demo-scolarite", "Scolarité Démo", "scolarite", ("scolarite",), None),
    ("ged-demo-financier", "Financier Démo", "financier", ("financier",), None),
    (
        "ged-demo-ancien",
        "Ancien Étudiant Démo",
        "ancien_etudiant",
        ("ancien_etudiant",),
        {
            "matricule": "GED-DEMO-ALUMNI-001",
            "cni": "GED-DEMO-CNI-001",
            "date_naissance": date(2000, 1, 1),
            "annee_promotion": 2022,
            "filiere": "Gestion",
        },
    ),
    ("ged-demo-externe", "Externe Démo", "externe", ("externe",), None),
    (
        "ged-demo-superadmin",
        "Super administrateur Démo",
        "externe",
        ("externe", "super_administrateur"),
        None,
    ),
    ("ged-demo-rh", "Agent RH Démo", "externe", ("externe", "agent_rh"), None),
    ("ged-demo-enseignant", "Enseignant Démo", "externe", ("externe", "enseignant"), None),
    (
        "ged-demo-visiteur",
        "Visiteur Démo",
        "externe",
        ("externe", "visiteur_lecture_seule"),
        None,
    ),
)


def nouveau_mot_de_passe():
    alphabet = string.ascii_letters + string.digits + "-_@"
    suffixe = "".join(secrets.choice(alphabet) for _ in range(24))
    return f"Gd9!{suffixe}"


class Command(BaseCommand):
    help = "Crée des comptes GED de démonstration pour tester les accès en développement."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirme explicitement la création ou la réinitialisation des comptes démo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Commande refusée : les comptes de démonstration ne sont créés "
                "qu'avec DEBUG=True."
            )
        if not options["confirm"]:
            raise CommandError("Relancez avec --confirm pour autoriser l'insertion.")

        model_user = get_user_model()
        if model_user is not Utilisateur:
            raise CommandError("Le modèle utilisateur configuré n'est pas celui de la GED.")

        role_codes = {
            code
            for _, _, _, codes, _ in UTILISATEURS_DEMO
            for code in codes
        }
        roles = {
            role.code: role
            for role in Role.objects.filter(code__in=role_codes)
        }
        missing_roles = role_codes - roles.keys()
        if missing_roles:
            raise CommandError(
                "Rôles manquants; appliquez les migrations avant le seed : "
                + ", ".join(sorted(missing_roles))
            )

        password = nouveau_mot_de_passe()
        crees = 0
        actualises = 0
        try:
            for username, nom, type_utilisateur, codes_roles, profil in UTILISATEURS_DEMO:
                email = f"{username}@example.test"
                user = Utilisateur.objects.filter(username__iexact=username).first()
                if user is not None:
                    if user.email.casefold() != email.casefold():
                        raise CommandError(
                            f"Le compte {username} existe avec une autre adresse e-mail; "
                            "aucune modification n'a été effectuée."
                        )
                    if user.type_utilisateur != type_utilisateur:
                        raise CommandError(
                            f"Le compte {username} a un type différent; "
                            "aucune modification n'a été effectuée."
                        )
                    actualises += 1
                else:
                    if Utilisateur.objects.filter(email__iexact=email).exists():
                        raise CommandError(
                            f"L'adresse {email} est déjà utilisée; "
                            "aucune modification n'a été effectuée."
                        )
                    user = Utilisateur(
                        username=username,
                        email=email,
                        first_name=nom,
                        type_utilisateur=type_utilisateur,
                    )
                    crees += 1

                user.first_name = nom
                user.last_name = "GED"
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                user.set_password(password)
                user.save()
                user.roles.set([roles[code] for code in codes_roles])

                if profil is not None:
                    self._creer_profil_etudiant(user, profil)
        except IntegrityError as exc:
            raise CommandError(
                "Insertion annulée : une donnée unique de compte ou de profil est déjà utilisée."
            ) from exc

        self.stdout.write(self.style.SUCCESS(
            f"{crees} compte(s) créé(s), {actualises} compte(s) démo réinitialisé(s)."
        ))
        self.stdout.write(f"Mot de passe commun à cette exécution : {password}")
        self.stdout.write("Identifiants :")
        for username, _, _, _, _ in UTILISATEURS_DEMO:
            self.stdout.write(f"  {username}")
        self.stdout.write(
            "Les comptes sont actifs; changez ce mot de passe après vos essais."
        )

    @staticmethod
    def _creer_profil_etudiant(user, donnees):
        profil = AncienEtudiant.objects.filter(utilisateur=user).first()
        if profil is not None:
            if any(getattr(profil, champ) != valeur for champ, valeur in donnees.items()):
                raise CommandError(
                    "Le profil associé au compte GED de démonstration a été modifié; "
                    "aucune modification n'a été effectuée."
                )
            return

        for champ in ("matricule", "cni"):
            valeur = donnees[champ]
            if AncienEtudiant.objects.filter(**{champ: valeur}).exists():
                raise CommandError(
                    f"La valeur de démonstration {champ} est déjà utilisée; "
                    "aucune modification n'a été effectuée."
                )
        AncienEtudiant.objects.create(utilisateur=user, **donnees)
