from django.db import migrations


PERMISSIONS = [
    ("utilisateurs.gerer", "utilisateurs", "gerer"),
    ("roles.gerer", "roles", "gerer"),
    ("permissions.gerer", "permissions", "gerer"),
    ("types_documents.gerer", "types_documents", "gerer"),
    ("plan_classement.gerer", "plan_classement", "gerer"),
    ("sauvegardes.gerer", "sauvegardes", "gerer"),
    ("supervision.consulter", "supervision", "consulter"),
    ("audit.consulter", "audit", "consulter"),
    ("audit.exporter", "audit", "exporter"),
    ("demandes.valider", "demandes", "valider"),
    ("documents.signer", "documents", "signer"),
    ("eliminations.valider", "eliminations", "valider"),
    ("tableau_bord.consulter", "tableau_bord", "consulter"),
    ("documents.classer", "documents", "classer"),
    ("conservation.gerer", "conservation", "gerer"),
    ("emplacements.gerer", "emplacements", "gerer"),
    ("eliminations.etablir", "eliminations", "etablir"),
    ("eliminations.executer", "eliminations", "executer"),
    ("lots.creer", "lots", "creer"),
    ("documents.importer", "documents", "importer"),
    ("documents.metadonnees_saisir", "documents", "metadonnees_saisir"),
    ("ocr.corriger", "ocr", "corriger"),
    ("lots.controle", "lots", "controle"),
    ("lots.valider", "lots", "valider"),
    ("lots.rejeter", "lots", "rejeter"),
    ("dossiers_etudiants.consulter", "dossiers_etudiants", "consulter"),
    ("duplicata.verifier", "duplicata", "verifier"),
    ("documents.generer", "documents", "generer"),
    ("paiements.verifier", "paiements", "verifier"),
    ("documents_financiers.consulter", "documents_financiers", "consulter"),
    ("demandes.creer", "demandes", "creer"),
    ("demandes.suivre", "demandes", "suivre"),
    ("documents_livres.telecharger", "documents_livres", "telecharger"),
    ("documents.authenticite.verifier", "documents.authenticite", "verifier"),
    ("systeme.parametres.gerer", "systeme.parametres", "gerer"),
    ("dossiers_personnel.consulter", "dossiers_personnel", "consulter"),
    ("dossiers_personnel.gerer", "dossiers_personnel", "gerer"),
    ("pv_notes.consulter", "pv_notes", "consulter"),
    ("documents_publics.consulter", "documents_publics", "consulter"),
]

ROLES = {
    "administrateur": (
        "Administrateur",
        (
            "utilisateurs.gerer", "roles.gerer", "permissions.gerer",
            "types_documents.gerer", "plan_classement.gerer",
            "sauvegardes.gerer", "supervision.consulter",
            "audit.consulter", "audit.exporter",
        ),
    ),
    "auditeur": ("Auditeur", ("audit.consulter", "audit.exporter")),
    "direction": (
        "Direction",
        (
            "demandes.valider", "documents.signer", "eliminations.valider",
            "tableau_bord.consulter",
        ),
    ),
    "archiviste": (
        "Archiviste",
        (
            "documents.classer", "conservation.gerer",
            "emplacements.gerer", "eliminations.etablir",
            "eliminations.executer",
        ),
    ),
    "operateur": (
        "Opérateur de numérisation",
        (
            "lots.creer", "documents.importer",
            "documents.metadonnees_saisir", "ocr.corriger",
        ),
    ),
    "controleur": (
        "Contrôleur qualité",
        ("lots.controle", "lots.valider", "lots.rejeter"),
    ),
    "scolarite": (
        "Agent de scolarité",
        (
            "dossiers_etudiants.consulter", "duplicata.verifier",
            "documents.generer",
        ),
    ),
    "financier": (
        "Agent financier",
        ("paiements.verifier", "documents_financiers.consulter"),
    ),
    "ancien_etudiant": (
        "Ancien étudiant",
        (
            "demandes.creer", "demandes.suivre",
            "documents_livres.telecharger",
        ),
    ),
    "externe": (
        "Utilisateur externe",
        ("documents.authenticite.verifier",),
    ),
    "super_administrateur": (
        "Super administrateur",
        (
            "sauvegardes.gerer", "systeme.parametres.gerer",
            "supervision.consulter",
        ),
    ),
    "agent_rh": (
        "Agent RH",
        ("dossiers_personnel.consulter", "dossiers_personnel.gerer"),
    ),
    "enseignant": ("Enseignant", ("pv_notes.consulter",)),
    "visiteur_lecture_seule": (
        "Visiteur en lecture seule",
        ("documents_publics.consulter",),
    ),
}


def creer_catalogue(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    Utilisateur = apps.get_model("accounts", "Utilisateur")
    database = schema_editor.connection.alias

    permissions = {}
    for code, ressource, action in PERMISSIONS:
        permission, _ = Permission.objects.using(database).get_or_create(
            code=code,
            defaults={"ressource": ressource, "action": action},
        )
        permissions[code] = permission

    for code, (libelle, permission_codes) in ROLES.items():
        role, _ = Role.objects.using(database).get_or_create(
            code=code,
            defaults={"libelle": libelle},
        )
        role.permissions.add(
            *[permissions[permission_code] for permission_code in permission_codes]
        )

    for utilisateur in Utilisateur.objects.using(database).all().iterator():
        if utilisateur.is_staff:
            administrateur = Role.objects.using(database).get(code="administrateur")
            utilisateur.roles.add(administrateur)
        role = Role.objects.using(database).filter(code=utilisateur.type_utilisateur).first()
        if role is not None:
            utilisateur.roles.add(role)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_journalaudit_action"),
    ]

    operations = [
        migrations.RunPython(creer_catalogue, migrations.RunPython.noop),
    ]
