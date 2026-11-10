from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase
import re
from django.conf import settings
from .models import JournalAudit, Permission, Role, Utilisateur

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
        role = Role.objects.create(code="archiviste", libelle="Archiviste")
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
        self.assertEqual(r.data["user"]["permissions"], ["document.consulter"])

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
        self.authentifier()
        r = self.client.post(
            reverse("auth-change-password"),
            {"ancien_mot_de_passe": MDP, "nouveau_mot_de_passe": "NouveauMdp456!"},
            format="json",
        )
        self.assertEqual(r.status_code, 204)
        self.client.credentials()
        self.assertEqual(self.login("NouveauMdp456!").status_code, 200)

    def test_logout_invalide_le_refresh(self):
        refresh = self.login().data["refresh"]
        self.authentifier()
        r = self.client.post(reverse("auth-logout"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 204)
        self.client.credentials()
        r = self.client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 401)


class PasswordResetAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = Utilisateur.objects.create_user(
            username="fatima", email="fatima@eng.mr", password=MDP,
            first_name="Fatima", type_utilisateur="archiviste",
        )

    def test_demande_envoie_un_lien(self):
        r = self.client.post(
            reverse("auth-password-reset"), {"email": "Fatima@eng.mr"}, format="json"
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reinitialiser-mot-de-passe", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["fatima@eng.mr"])

    def test_email_inconnu_ne_revele_rien(self):
        r = self.client.post(
            reverse("auth-password-reset"), {"email": "inconnu@eng.mr"}, format="json"
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(len(mail.outbox), 0)

    def test_compte_inactif_ne_recoit_pas_de_lien(self):
        self.user.is_active = False
        self.user.save()
        r = self.client.post(
            reverse("auth-password-reset"), {"email": "fatima@eng.mr"}, format="json"
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirmation_change_le_mot_de_passe_et_invalide_le_jeton(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        payload = {"uid": uid, "token": token, "nouveau_mot_de_passe": "NouveauMdp456!"}
        r = self.client.post(reverse("auth-password-reset-confirm"), payload, format="json")
        self.assertEqual(r.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauMdp456!"))
        r = self.client.post(reverse("auth-password-reset-confirm"), payload, format="json")
        self.assertEqual(r.status_code, 400)

    def test_lien_invalide(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        r = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": "jeton-faux", "nouveau_mot_de_passe": "NouveauMdp456!"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("token", r.data)

    def test_mot_de_passe_trop_faible(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        r = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "nouveau_mot_de_passe": "123"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

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