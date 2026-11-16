import re
from datetime import datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase

from .models import AncienEtudiant, JournalAudit, Permission, Role, Utilisateur
from apps.conservation.models import BordereauElimination, LigneBordereau
from apps.documents.models import Document, Dossier, TypeDocument
from apps.workflow.models import DemandeDuplicata, DocumentGenere

MDP = "MotDePasse123!"


class AuthAPITests(APITestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username="fatima", email="fatima@eng.mr", password=MDP,
            type_utilisateur="archiviste",
        )
        perm = Permission.objects.create(
            code="document.consulter", ressource="document", action="consulter"
        )
        role, _ = Role.objects.get_or_create(
            code="archiviste", defaults={"libelle": "Archiviste"}
        )
        role.permissions.add(perm)
        self.user.roles.add(role)

    def login(self, mdp=MDP):
        return self.client.post(
            reverse("auth-login"), {"username": "fatima", "password": mdp}, format="json"
        )

    def authentifier(self):
        token = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_login_ok_retourne_jetons_et_permissions(self):
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)
        self.assertEqual(
            r.data["user"]["permissions"],
            [
                "conservation.gerer",
                "document.consulter",
                "documents.classer",
                "eliminations.etablir",
                "eliminations.executer",
                "emplacements.gerer",
            ],
        )

    def test_login_mauvais_mot_de_passe(self):
        self.assertEqual(self.login("faux").status_code, 401)

    def test_login_compte_desactive(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 401)

    def test_login_est_journalise(self):
        self.login()
        self.assertTrue(
            JournalAudit.objects.filter(utilisateur=self.user, action="connexion").exists()
        )

    def test_me_exige_authentification(self):
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    def test_me_retourne_le_profil(self):
        self.authentifier()
        r = self.client.get(reverse("auth-me"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["username"], "fatima")
        self.assertIsNone(r.data["profil_etudiant"])

    def test_changer_la_langue(self):
        self.authentifier()
        r = self.client.patch(reverse("auth-me"), {"langue": "ar"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["langue"], "ar")

    def test_changement_mot_de_passe_ancien_faux(self):
        self.authentifier()
        r = self.client.post(
            reverse("auth-change-password"),
            {"ancien_mot_de_passe": "faux", "nouveau_mot_de_passe": "NouveauMdp456!"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_changement_mot_de_passe_ok(self):
        refresh = self.login().data["refresh"]
        self.authentifier()
        r = self.client.post(
            reverse("auth-change-password"),
            {"ancien_mot_de_passe": MDP, "nouveau_mot_de_passe": "NouveauMdp456!"},
            format="json",
        )
        self.assertEqual(r.status_code, 204)
        self.client.credentials()
        self.assertEqual(self.login("NouveauMdp456!").status_code, 200)
        self.assertEqual(
            self.client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json").status_code,
            401,
        )

    def test_logout_invalide_le_refresh(self):
        refresh = self.login().data["refresh"]
        self.authentifier()
        r = self.client.post(reverse("auth-logout"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 204)
        self.client.credentials()
        r = self.client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_logout_ne_revoque_pas_le_refresh_d_un_autre_compte(self):
        autre = Utilisateur.objects.create_user(
            username="autre-compte",
            email="autre-compte@example.org",
            password=MDP,
        )
        refresh_autre = self.client.post(
            reverse("auth-login"),
            {"username": autre.username, "password": MDP},
            format="json",
        ).data["refresh"]
        self.authentifier()

        reponse = self.client.post(
            reverse("auth-logout"),
            {"refresh": refresh_autre},
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.client.credentials()
        self.assertEqual(
            self.client.post(
                reverse("auth-refresh"),
                {"refresh": refresh_autre},
                format="json",
            ).status_code,
            200,
        )


class InscriptionAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_inscription_cree_un_compte_inactif_sans_role(self):
        reponse = self.client.post(
            reverse("auth-register"),
            {
                "username": "nadia-test",
                "email": "nadia@example.org",
                "first_name": "Nadia",
                "last_name": "Test",
                "password": "S3cur!tyRaven_94",
            },
            format="json",
        )

        self.assertEqual(reponse.status_code, 202)
        self.assertNotIn("access", reponse.data)
        utilisateur = Utilisateur.objects.get(username="nadia-test")
        self.assertFalse(utilisateur.is_active)
        self.assertEqual(utilisateur.type_utilisateur, Utilisateur.TypeUtilisateur.EXTERNE)
        self.assertEqual(
            list(utilisateur.roles.values_list("code", flat=True)), ["externe"]
        )
        self.assertTrue(utilisateur.check_password("S3cur!tyRaven_94"))
        self.assertTrue(
            JournalAudit.objects.filter(
                utilisateur=utilisateur,
                details__evenement="inscription_en_attente",
            ).exists()
        )
        connexion = self.client.post(
            reverse("auth-login"),
            {"username": "nadia-test", "password": "S3cur!tyRaven_94"},
            format="json",
        )
        self.assertEqual(connexion.status_code, 401)

    def test_inscription_refuse_un_mot_de_passe_faible(self):
        reponse = self.client.post(
            reverse("auth-register"),
            {
                "username": "nadia-test",
                "email": "nadia@example.org",
                "first_name": "Nadia",
                "last_name": "Test",
                "password": "123",
            },
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("password", reponse.data)
        self.assertFalse(Utilisateur.objects.filter(username="nadia-test").exists())


class PasswordResetAPITests(APITestCase):
    NOUVEAU = "NouveauMdp456!"

    def setUp(self):
        cache.clear()  # remet à zéro les compteurs de limitation
        self.user = Utilisateur.objects.create_user(
            username="karim", email="karim@eng.mr", password=MDP,
            type_utilisateur="scolarite",
        )

    def demander(self, email):
        return self.client.post(reverse("auth-password-reset"), {"email": email}, format="json")

    def confirmer(self, uid, token, mdp=None):
        return self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "nouveau_mot_de_passe": mdp or self.NOUVEAU},
            format="json",
        )

    def jetons(self):
        self.user.refresh_from_db()
        return (
            urlsafe_base64_encode(force_bytes(self.user.pk)),
            default_token_generator.make_token(self.user),
        )

    def connexion(self, mdp):
        return self.client.post(
            reverse("auth-login"), {"username": "karim", "password": mdp}, format="json"
        )

    # --- Demande ---
    def test_demande_envoie_un_email_avec_lien(self):
        r = self.demander("karim@eng.mr")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["karim@eng.mr"])
        corps = mail.outbox[0].body
        lien = re.search(r"http\S+reinitialiser-mot-de-passe\?\S+", corps).group(0)
        self.assertTrue(lien.startswith(settings.FRONTEND_URL.rstrip("/")))
        self.assertIn("uid=", lien)
        self.assertIn("&token=", lien)
        self.assertNotIn("&amp;", corps)

    def test_email_inconnu_meme_reponse_et_aucun_email(self):
        inconnu = self.demander("inconnu@eng.mr")
        self.assertEqual(len(mail.outbox), 0)
        connu = self.demander("karim@eng.mr")
        self.assertEqual(inconnu.status_code, connu.status_code)
        self.assertEqual(inconnu.data, connu.data)

    def test_compte_desactive_ne_recoit_rien(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.demander("karim@eng.mr").status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_mal_forme(self):
        self.assertEqual(self.demander("pas-un-email").status_code, 400)

    def test_limitation_du_debit(self):
        for _ in range(5):
            self.assertEqual(self.demander("inconnu@eng.mr").status_code, 200)
        self.assertEqual(self.demander("inconnu@eng.mr").status_code, 429)

    # --- Confirmation ---
    def test_confirmation_ok(self):
        uid, token = self.jetons()
        self.assertEqual(self.confirmer(uid, token).status_code, 204)
        self.assertEqual(self.connexion(self.NOUVEAU).status_code, 200)
        self.assertEqual(self.connexion(MDP).status_code, 401)

    def test_jeton_a_usage_unique(self):
        uid, token = self.jetons()
        self.assertEqual(self.confirmer(uid, token).status_code, 204)
        self.assertEqual(self.confirmer(uid, token, "AutreMdp789!").status_code, 400)

    def test_jeton_invalide(self):
        uid, _ = self.jetons()
        r = self.confirmer(uid, "jeton-bidon")
        self.assertEqual(r.status_code, 400)
        self.assertIn("token", r.data)

    def test_jeton_expire(self):
        uid, token = self.jetons()
        maintenant = datetime.now()
        with patch.object(
            default_token_generator,
            "_now",
            return_value=maintenant + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1),
        ):
            r = self.confirmer(uid, token)
        self.assertEqual(r.status_code, 400)
        self.assertIn("token", r.data)

    def test_uid_invalide(self):
        _, token = self.jetons()
        r = self.confirmer("xx", token)
        self.assertEqual(r.status_code, 400)
        self.assertIn("token", r.data)

    def test_mot_de_passe_trop_faible(self):
        uid, token = self.jetons()
        r = self.confirmer(uid, token, "123")
        self.assertEqual(r.status_code, 400)
        self.assertIn("nouveau_mot_de_passe", r.data)
        self.assertEqual(self.connexion(MDP).status_code, 200)  # inchangé

    def test_les_refresh_tokens_sont_revoques(self):
        refresh = self.connexion(MDP).data["refresh"]
        uid, token = self.jetons()
        self.assertEqual(self.confirmer(uid, token).status_code, 204)
        r = self.client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_confirmation_est_journalisee(self):
        uid, token = self.jetons()
        self.confirmer(uid, token)
        self.assertTrue(
            JournalAudit.objects.filter(
                utilisateur=self.user, details__evenement="mot_de_passe_reinitialise"
            ).exists()
        )


class UtilisateurManagementAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = Utilisateur.objects.create_user(
            username="admin-api",
            email="admin-api@example.org",
            password=MDP,
            is_staff=True,
        )
        self.user = Utilisateur.objects.create_user(
            username="lecteur",
            email="lecteur@example.org",
            password=MDP,
            first_name="Lea",
            last_name="Lectrice",
        )
        self.role, _ = Role.objects.get_or_create(
            code="archiviste", defaults={"libelle": "Archiviste"}
        )

    def authentifier(self, utilisateur):
        reponse = self.client.post(
            reverse("auth-login"),
            {"username": utilisateur.username, "password": MDP},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {reponse.data['access']}")

    def test_api_reservee_aux_administrateurs(self):
        self.assertEqual(self.client.get(reverse("utilisateur-list")).status_code, 401)

        self.authentifier(self.user)
        self.assertEqual(self.client.get(reverse("utilisateur-list")).status_code, 403)

    def test_admin_peut_rechercher_et_consulter_les_comptes(self):
        self.authentifier(self.admin)
        liste = self.client.get(reverse("utilisateur-list"), {"search": "lectrice"})
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(liste.data["count"], 1)
        self.assertEqual(liste.data["results"][0]["id"], self.user.pk)

        detail = self.client.get(reverse("utilisateur-detail", args=[self.user.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["email"], "lecteur@example.org")
        self.assertIsNone(detail.data["profil_etudiant"])

    def test_admin_cree_un_compte_sans_role_privilegie_par_defaut(self):
        self.authentifier(self.admin)
        reponse = self.client.post(
            reverse("utilisateur-list"),
            {
                "username": "nouveau",
                "email": "nouveau@example.org",
                "first_name": "Nouvel",
                "last_name": "Utilisateur",
                "password": "S3cure-Account-2026!",
                "role_ids": [self.role.pk],
            },
            format="json",
        )

        self.assertEqual(reponse.status_code, 201)
        utilisateur = Utilisateur.objects.get(username="nouveau")
        self.assertFalse(utilisateur.is_active)
        self.assertTrue(utilisateur.roles.filter(pk=self.role.pk).exists())
        self.assertNotIn("is_staff", reponse.data)
        self.assertNotIn("is_superuser", reponse.data)
        self.assertTrue(
            JournalAudit.objects.filter(
                entite_cible="Utilisateur",
                id_cible=utilisateur.pk,
                action=JournalAudit.Action.CREATION,
            ).exists()
        )

    def test_admin_ne_cree_pas_un_ancien_etudiant_sans_profil(self):
        self.authentifier(self.admin)
        response = self.client.post(
            reverse("utilisateur-list"),
            {
                "username": "ancien-incomplet",
                "email": "ancien-incomplet@example.org",
                "password": "S3cure-Account-2026!",
                "type_utilisateur": Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("type_utilisateur", response.data)
        self.assertFalse(Utilisateur.objects.filter(username="ancien-incomplet").exists())

    def test_admin_modifie_et_desactive_sans_supprimer(self):
        self.authentifier(self.admin)
        detail_url = reverse("utilisateur-detail", args=[self.user.pk])
        reponse = self.client.patch(
            detail_url,
            {"is_active": False, "role_ids": [self.role.pk]},
            format="json",
        )
        self.assertEqual(reponse.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.user.roles.filter(pk=self.role.pk).exists())

        suppression = self.client.delete(detail_url)
        self.assertEqual(suppression.status_code, 204)
        self.assertTrue(Utilisateur.objects.filter(pk=self.user.pk).exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_admin_ne_peut_pas_desactiver_son_propre_compte(self):
        self.authentifier(self.admin)
        reponse = self.client.patch(
            reverse("utilisateur-detail", args=[self.admin.pk]),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(reponse.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        suppression = self.client.delete(reverse("utilisateur-detail", args=[self.admin.pk]))
        self.assertEqual(suppression.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class RolesPermissionsAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = Utilisateur.objects.create_user(
            username="admin-rbac",
            email="admin-rbac@example.org",
            password=MDP,
            is_staff=True,
        )
        self.user = Utilisateur.objects.create_user(
            username="user-rbac",
            email="user-rbac@example.org",
            password=MDP,
        )

    def authentifier(self, utilisateur):
        response = self.client.post(
            reverse("auth-login"),
            {"username": utilisateur.username, "password": MDP},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_api_roles_et_permissions_reservees_aux_administrateurs(self):
        self.authentifier(self.user)
        self.assertEqual(self.client.get(reverse("role-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("permission-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("journal-audit-list")).status_code, 403)

    def test_administrateur_cree_permission_et_role_associe(self):
        self.authentifier(self.admin)
        permission = self.client.post(
            reverse("permission-list"),
            {"code": "document.exporter", "ressource": "document", "action": "exporter"},
            format="json",
        )
        self.assertEqual(permission.status_code, 201)

        role = self.client.post(
            reverse("role-list"),
            {
                "code": "gestionnaire-documents",
                "libelle": "Gestionnaire de documents",
                "permission_ids": [permission.data["id"]],
            },
            format="json",
        )
        self.assertEqual(role.status_code, 201)
        self.assertEqual(role.data["permissions"][0]["code"], "document.exporter")
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.CREATION,
                entite_cible="Role",
                id_cible=role.data["id"],
            ).exists()
        )
        role_url = reverse("role-detail", args=[role.data["id"]])
        self.assertEqual(
            self.client.patch(role_url, {"libelle": "Gestion documentaire"}, format="json").status_code,
            200,
        )
        self.assertEqual(self.client.delete(role_url).status_code, 204)

        permission_url = reverse("permission-detail", args=[permission.data["id"]])
        self.assertEqual(
            self.client.patch(
                permission_url,
                {"code": "document.archiver", "action": "archiver"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(permission_url).status_code, 204)

    def test_audit_est_pagine_filtrable_et_en_lecture_seule(self):
        evenement = JournalAudit.objects.create(
            utilisateur=self.admin,
            action=JournalAudit.Action.EXPORT,
            entite_cible="Document",
            id_cible=42,
            details={"format": "csv"},
        )
        self.authentifier(self.admin)
        response = self.client.get(reverse("journal-audit-list"), {"action": "export"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row["id"] == evenement.pk for row in response.data["results"]))
        self.assertEqual(
            self.client.delete(reverse("journal-audit-detail", args=[evenement.pk])).status_code,
            405,
        )

    def test_auditeur_consulte_et_exporte_sans_acces_aux_comptes(self):
        auditeur = Utilisateur.objects.create_user(
            username="auditeur",
            email="auditeur@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.AUDITEUR,
        )
        auditeur.roles.add(Role.objects.get(code="auditeur"))
        self.authentifier(auditeur)

        self.assertEqual(self.client.get(reverse("journal-audit-list")).status_code, 200)
        self.assertEqual(self.client.post(reverse("journal-audit-list"), {}).status_code, 405)
        self.assertEqual(self.client.get(reverse("utilisateur-list")).status_code, 403)

        export = self.client.get(reverse("journal-audit-exporter"))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"date_action,action,utilisateur", b"".join(export.streaming_content))
        self.assertTrue(
            JournalAudit.objects.filter(
                utilisateur=auditeur, action=JournalAudit.Action.EXPORT
            ).exists()
        )

    def test_roles_systeme_ne_peuvent_pas_etre_supprimes_ou_renommes(self):
        self.authentifier(self.admin)
        role = Role.objects.get(code="auditeur")
        self.assertEqual(
            self.client.patch(
                reverse("role-detail", args=[role.pk]),
                {"code": "auditeur-modifie"},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(reverse("role-detail", args=[role.pk])).status_code,
            400,
        )


class AncienEtudiantAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_inscription_cree_un_compte_et_profil_en_attente(self):
        response = self.client.post(
            reverse("ancien-etudiant-inscription"),
            {
                "username": "ancien-test",
                "email": "ancien@example.org",
                "first_name": "Aminata",
                "last_name": "Test",
                "password": "S3cur!tyRaven_94",
                "matricule": "ENG-2020-001",
                "cni": "CNI-12345678",
                "date_naissance": "1998-06-15",
                "annee_promotion": 2020,
                "filiere": "Gestion",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        utilisateur = Utilisateur.objects.get(username="ancien-test")
        self.assertFalse(utilisateur.is_active)
        self.assertEqual(utilisateur.type_utilisateur, Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT)
        self.assertTrue(utilisateur.roles.filter(code="ancien_etudiant").exists())
        self.assertEqual(utilisateur.profil_etudiant.matricule, "ENG-2020-001")
        self.assertTrue(
            JournalAudit.objects.filter(
                utilisateur=utilisateur,
                entite_cible="AncienEtudiant",
                details__evenement="inscription_en_attente",
            ).exists()
        )

    def test_inscription_refuse_une_annee_de_promotion_future(self):
        response = self.client.post(
            reverse("ancien-etudiant-inscription"),
            {
                "username": "ancien-futur",
                "email": "ancien-futur@example.org",
                "first_name": "Aminata",
                "last_name": "Test",
                "password": "S3cur!tyRaven_94",
                "matricule": "ENG-FUTUR-001",
                "cni": "CNI-FUTUR-001",
                "date_naissance": "1998-06-15",
                "annee_promotion": datetime.now().year + 1,
                "filiere": "Gestion",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Utilisateur.objects.filter(username="ancien-futur").exists())

    def test_profil_est_limite_a_un_utilisateur_ancien_etudiant(self):
        user = Utilisateur.objects.create_user(
            username="profil-etudiant",
            email="profil-etudiant@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT,
        )
        AncienEtudiant.objects.create(
            utilisateur=user,
            matricule="ENG-2019-001",
            cni="CNI-20190001",
            date_naissance="1997-02-10",
            annee_promotion=2019,
            filiere="Comptabilité",
        )
        response = self.client.post(
            reverse("auth-login"),
            {"username": user.username, "password": MDP},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        profile = self.client.get(reverse("ancien-etudiant-me"))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["matricule"], "ENG-2019-001")

        updated = self.client.patch(
            reverse("ancien-etudiant-me"),
            {"filiere": "Finance"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["filiere"], "Finance")

    def test_profil_absent_retourne_404(self):
        user = Utilisateur.objects.create_user(
            username="sans-profil",
            email="sans-profil@example.org",
            password=MDP,
        )
        response = self.client.post(
            reverse("auth-login"),
            {"username": user.username, "password": MDP},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get(reverse("ancien-etudiant-me")).status_code, 404)

    def test_admin_peut_verifier_le_profil_de_la_demande(self):
        admin = Utilisateur.objects.create_user(
            username="admin-alumni",
            email="admin-alumni@example.org",
            password=MDP,
            is_staff=True,
        )
        user = Utilisateur.objects.create_user(
            username="alumni-a-verifier",
            email="alumni-a-verifier@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT,
            is_active=False,
        )
        AncienEtudiant.objects.create(
            utilisateur=user,
            matricule="ENG-2021-007",
            cni="CNI-20210007",
            date_naissance="1999-01-02",
            annee_promotion=2021,
            filiere="Finance",
        )
        login = self.client.post(
            reverse("auth-login"),
            {"username": admin.username, "password": MDP},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.get(reverse("utilisateur-detail", args=[user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profil_etudiant"]["matricule"], "ENG-2021-007")


class RBACDocumentScopeTests(APITestCase):
    def setUp(self):
        self.operateur_role = Role.objects.get(code="operateur")
        self.archiviste_role = Role.objects.get(code="archiviste")
        self.type_document = TypeDocument.objects.create(
            code="diplome-rbac", libelle="Diplôme"
        )
        self.dossier_parent = Dossier.objects.create(
            cote="RBAC-001", intitule="Dossier racine"
        )
        self.dossier = Dossier.objects.create(
            cote="RBAC-002",
            intitule="Dossier étudiant",
            parent=self.dossier_parent,
        )
        self.document = Document.objects.create(
            reference="RBAC-DOC-001",
            titre="Diplôme",
            type_document=self.type_document,
            dossier=self.dossier,
        )
        self.operateur = Utilisateur.objects.create_user(
            username="operateur-rbac",
            email="operateur-rbac@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.OPERATEUR,
        )
        self.operateur.roles.add(self.operateur_role)

    def test_acces_document_exige_permission_et_respecte_type_et_ancetres(self):
        self.assertTrue(
            self.operateur.a_acces_document(self.document, "documents.importer")
        )

        self.type_document.roles_autorises.add(self.archiviste_role)
        self.assertFalse(
            self.operateur.a_acces_document(self.document, "documents.importer")
        )
        self.type_document.roles_autorises.add(self.operateur_role)
        self.assertTrue(
            self.operateur.a_acces_document(self.document, "documents.importer")
        )

        self.dossier_parent.roles_autorises.add(self.archiviste_role)
        self.assertFalse(
            self.operateur.a_acces_document(self.document, "documents.importer")
        )

    def test_alumni_et_externe_ne_peuvent_pas_acceder_aux_archives(self):
        externe = Utilisateur.objects.create_user(
            username="externe-rbac",
            email="externe-rbac@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.EXTERNE,
        )
        externe.roles.add(Role.objects.get(code="externe"))
        self.assertFalse(
            externe.a_acces_document(
                self.document, "documents.authenticite.verifier"
            )
        )

    def test_affectation_interdit_le_cumul_numerisation_et_controle(self):
        from .serializers import GestionUtilisateurSerializer

        controleur_role = Role.objects.get(code="controleur")
        serializer = GestionUtilisateurSerializer(
            data={
                "username": "operateur-controleur",
                "email": "operateur-controleur@example.org",
                "password": MDP,
                "type_utilisateur": Utilisateur.TypeUtilisateur.OPERATEUR,
                "role_ids": [self.operateur_role.pk, controleur_role.pk],
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("role_ids", serializer.errors)

    def test_affectation_interdit_a_la_direction_de_numeriser(self):
        from .serializers import GestionUtilisateurSerializer

        direction_role = Role.objects.get(code="direction")
        serializer = GestionUtilisateurSerializer(
            data={
                "username": "direction-operateur",
                "email": "direction-operateur@example.org",
                "password": MDP,
                "type_utilisateur": Utilisateur.TypeUtilisateur.OPERATEUR,
                "role_ids": [self.operateur_role.pk, direction_role.pk],
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("role_ids", serializer.errors)

    def test_validation_et_execution_du_bordereau_respectent_les_roles(self):
        archiviste = Utilisateur.objects.create_user(
            username="archiviste-elimination",
            email="archiviste-elimination@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.ARCHIVISTE,
        )
        archiviste.roles.add(self.archiviste_role)
        bordereau = BordereauElimination.objects.create(
            numero="RBAC-ELIM-001",
            etabli_par=archiviste,
        )
        LigneBordereau.objects.create(
            bordereau=bordereau,
            document=self.document,
        )
        with self.assertRaises(PermissionDenied):
            bordereau.valider(archiviste)

        direction = Utilisateur.objects.create_user(
            username="direction-elimination",
            email="direction-elimination@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.DIRECTION,
        )
        direction.roles.add(Role.objects.get(code="direction"))
        bordereau.valider(direction)
        bordereau.executer(archiviste)
        self.document.refresh_from_db()
        self.assertEqual(self.document.statut, Document.Statut.ELIMINE)


class VerificationAuthenticiteAPITests(APITestCase):
    def test_verification_qr_publique_ne_donne_pas_acces_aux_archives(self):
        ancien = Utilisateur.objects.create_user(
            username="demandeur-qr",
            email="demandeur-qr@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.ANCIEN_ETUDIANT,
        )
        profil = AncienEtudiant.objects.create(
            utilisateur=ancien,
            matricule="QR-2020-001",
            cni="QR-CNI-001",
            date_naissance="1998-06-15",
            annee_promotion=2020,
            filiere="Gestion",
        )
        demande = DemandeDuplicata.objects.create(
            demandeur=profil,
            type_demande=DemandeDuplicata.TypeDemande.DUPLICATA_DIPLOME,
        )
        document = DocumentGenere.objects.create(
            demande=demande,
            numero_officiel="QR-ENG-2026-001",
        )
        admin = Utilisateur.objects.create_user(
            username="admin-qr",
            email="admin-qr@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.ADMINISTRATEUR,
        )
        admin.roles.add(Role.objects.get(code="administrateur"))
        with self.assertRaises(PermissionDenied):
            document.signer(admin)
        direction = Utilisateur.objects.create_user(
            username="direction-qr",
            email="direction-qr@example.org",
            password=MDP,
            type_utilisateur=Utilisateur.TypeUtilisateur.DIRECTION,
        )
        direction.roles.add(Role.objects.get(code="direction"))
        document.signer(direction)

        response = self.client.get(
            reverse("verification-authenticite", args=[document.code_qr])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["authentique"])
        self.assertEqual(response.data["numero_officiel"], "QR-ENG-2026-001")
        self.assertNotIn("demandeur", response.data)
        self.assertEqual(
            set(response.data),
            {"authentique", "numero_officiel", "date_generation", "signe"},
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "verification-authenticite",
                    args=["00000000-0000-0000-0000-000000000000"],
                )
            ).status_code,
            404,
        )