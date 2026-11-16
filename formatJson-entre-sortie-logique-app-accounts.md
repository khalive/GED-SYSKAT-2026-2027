# Analyse fonctionnelle et technique des 5 API REST de l’application Accounts

## Périmètre et sources

Cette analyse s’appuie sur les routes, vues, serializers, modèles, réglages et appels Angular présents dans le projet :

- Backend : `backend/apps/accounts/urls.py`, `views.py`, `serializers.py`, `models.py`, `audit.py`, `password_reset.py`.
- Configuration : `backend/config/urls.py`, `backend/config/settings/base.py`.
- Frontend : `frontend/src/app/core/services/`, `core/models/`, `core/interceptors/auth.interceptor.ts`, et les vues de gestion correspondantes.
- Tests : `backend/apps/accounts/tests.py`.

Swagger UI est configuré sur `/api/docs/` et le schéma OpenAPI sur `/api/schema/`. Les descriptions d’opérations sont déclarées notamment avec `extend_schema`. Cette analyse reflète le code et les tests du dépôt; le schéma effectivement servi par une instance en fonctionnement peut être vérifié sur `/api/docs/`.

Les exemples de jetons, d’identifiants et d’adresses IP sont illustratifs. Les réponses d’erreur non personnalisées peuvent varier selon la version et la langue configurée de Django REST Framework/SimpleJWT.

## Vue d’ensemble et autorisations

Les routes API commencent par `/api`. Sauf indication contraire, les routes protégées exigent un jeton JWT dans `Authorization: Bearer <access>`. La politique générale de DRF est `IsAuthenticated`, mais les endpoints publics la remplacent explicitement par `AllowAny`.

Pour les comptes administratifs, les rôles, les permissions et l’audit, le contrôle backend exige que l’utilisateur ait `is_staff=True` ou soit superutilisateur. Un rôle métier seul ne suffit pas.

Les listes d’utilisateurs et d’audit utilisent la pagination DRF globale, soit **20 résultats par page**. Les listes de rôles et de permissions utilisent une pagination dédiée, **100 par défaut**, avec `page_size` plafonné à 200.

## 1. API Authentification

### Cycle de vie des jetons JWT

1. `POST /api/auth/login/` vérifie le nom d’utilisateur et le mot de passe, puis retourne un jeton `access`, un jeton `refresh` et le profil.
2. Angular stocke les deux jetons dans `localStorage` sous les clés `ged.access` et `ged.refresh`, puis envoie l’access dans l’en-tête `Authorization`.
3. L’access expire après **30 minutes**. Le refresh expire après **1 jour**.
4. Si une requête protégée obtient une réponse 401, l’intercepteur Angular tente `/api/auth/refresh/`, puis réessaie la requête avec le nouvel access.
5. Le renouvellement retourne seulement un nouvel access : la rotation des refresh n’est pas activée par la configuration montrée.
6. Logout invalide le refresh fourni. Les accès étant des JWT, l’invalidation du refresh ne révoque pas immédiatement un access déjà émis : il peut rester valide jusqu’à son expiration. Angular efface toutefois les jetons stockés.
7. Le changement ou la réinitialisation du mot de passe révoque les refresh tokens enregistrés. Le code ne révoque pas immédiatement les access déjà émis.

### Connexion — `POST /api/auth/login/`

**Accès :** public. Limite configurée : 20 tentatives par minute.

**Corps requis :**

```json
{
  "username": "amina",
  "password": "MotDePasseExemple!"
}
```

Les deux champs sont des chaînes. La connexion échoue si les identifiants sont erronés ou si le compte est inactif. Le compte doit donc avoir été activé après inscription.

**Succès : 200**

```json
{
  "access": "<jeton-access>",
  "refresh": "<jeton-refresh>",
  "user": {
    "id": 12,
    "username": "amina",
    "email": "amina@example.org",
    "first_name": "Amina",
    "last_name": "Diallo",
    "type_utilisateur": "archiviste",
    "telephone": "",
    "langue": "fr",
    "roles": [
      { "id": 3, "code": "archiviste", "libelle": "Archiviste" }
    ],
    "permissions": ["document.consulter"],
    "profil_etudiant": null,
    "is_staff": false
  }
}
```

`permissions` contient les codes de permissions associés aux rôles; pour un superutilisateur, le serializer retourne les permissions du catalogue. `is_staff` reflète le statut staff ou superutilisateur.

**Erreurs :** identifiants incorrects ou compte inactif : **401** avec une erreur SimpleJWT; trop de tentatives : **429**. Le test confirme les statuts, mais le texte d’erreur n’est pas personnalisé par cette vue.

**Parcours Angular :** l’utilisateur soumet le formulaire de connexion; Angular envoie le JSON, stocke les jetons et le profil, puis redirige vers l’écran demandé ou l’accueil.


### Inscription externe — `POST /api/auth/register/`

**Accès :** public. Limite configurée : 5 demandes par heure.

**Corps requis :**

```json
{
  "username": "amina",
  "email": "amina@example.org",
  "first_name": "Amina",
  "last_name": "Diallo",
  "password": "UnePhraseDePasse!2026"
}
```

Tous les champs sont requis. Les longueurs maximales des chaînes username/prénom/nom sont 150 caractères. L’adresse doit être valide et unique sans tenir compte de la casse. Le mot de passe est soumis aux validateurs Django configurés : similarité avec les attributs du compte, longueur minimale, liste de mots de passe courants et rejet d’un mot de passe entièrement numérique.

Le backend crée un compte de type `externe`, **inactif**, sans rôle et sans jetons de connexion. Il enregistre une entrée d’audit `creation` avec `evenement: inscription_en_attente`.

**Succès : 202**

```json
{
  "detail": "Votre demande de création de compte a été reçue. Elle sera activée après vérification par l'administration."
}
```

**Erreurs :** données invalides ou username/e-mail déjà utilisé : **400**; limite dépassée : **429**. Ce endpoint n’envoie pas de courriel de vérification. La première connexion n’est possible qu’après activation.

### Renouvellement d’access — `POST /api/auth/refresh/`

**Accès :** public avec un refresh valide.

**Corps requis :**

```json
{ "refresh": "<jeton-refresh>" }
```

**Succès : 200**

```json
{ "access": "<nouveau-jeton-access>" }
```

La réponse n’inclut pas un nouveau refresh dans la configuration présente. Jeton manquant ou invalide : généralement **400** pour un champ manquant ou **401** pour un token rejeté par SimpleJWT. Cette opération n’est pas inscrite à l’audit.

### Déconnexion — `POST /api/auth/logout/`

**Accès :** utilisateur authentifié; le refresh envoyé doit appartenir à cet utilisateur.

**Corps requis :**

```json
{ "refresh": "<jeton-refresh>" }
```

Le backend vérifie la propriété du refresh, le place en liste noire et journalise `deconnexion`.

**Succès : 204**, sans corps JSON.

**Erreurs :** refresh invalide/expiré ou appartenant à un autre compte : **400**; absence d’authentification : **401**. La réponse de propriété étrangère est du type :

```json
{ "refresh": ["Ce jeton n'appartient pas à votre compte."] }
```

### Consulter son profil — `GET /api/auth/me/`

**Accès :** utilisateur authentifié. Aucun corps JSON.

**Succès : 200** — même objet `user` que dans la réponse de connexion, sans les jetons. Il inclut rôles, permissions, `is_staff` et un profil étudiant ou `null`. Sans access valide : **401**.

### Modifier son profil — `PATCH /api/auth/me/`

**Accès :** utilisateur authentifié. Les champs modifiables sont uniquement `first_name`, `last_name`, `telephone` et `langue`. Tous sont facultatifs en PATCH.

```json
{
  "first_name": "Amina",
  "telephone": "+222 45 00 00 00",
  "langue": "ar"
}
```

Le téléphone est limité à 20 caractères; `langue` accepte `fr` ou `ar`. L’e-mail, le username, le type et les rôles ne sont pas modifiables par cet endpoint. Le backend retourne le profil complet mis à jour en **200**, et journalise les noms de champs modifiés. Un champ invalide donne **400**; sans authentification : **401**. `PUT` n’est pas implémenté par cette vue.

### Changer son mot de passe — `POST /api/auth/change-password/`

**Accès :** utilisateur authentifié.

**Corps requis :**

```json
{
  "ancien_mot_de_passe": "AncienMotDePasse!",
  "nouveau_mot_de_passe": "NouveauMotDePasse!2026"
}
```

Les deux champs sont requis. L’ancien mot de passe doit correspondre au compte; le nouveau est validé par les validateurs Django. Le backend change le mot de passe, révoque les refresh tokens connus et journalise l’opération.

**Succès : 204**, sans corps. Ancien mot de passe incorrect ou nouveau invalide : **400**; non authentifié : **401**.

### Demander une réinitialisation — `POST /api/auth/password-reset/`

**Accès :** public. Limite : 5 demandes par heure.

**Corps requis :**

```json
{ "email": "amina@example.org" }
```

Si un compte actif correspondant existe, le backend envoie un lien frontend contenant `uid` et un token signé par Django. Le lien expire après `PASSWORD_RESET_TIMEOUT`, **3600 secondes par défaut**. La réponse est volontairement identique pour un e-mail inconnu, inactif ou connu afin de ne pas révéler l’existence du compte.

**Succès : 200**

```json
{
  "detail": "Si un compte actif correspond à cette adresse, un e-mail contenant un lien de réinitialisation vient d'être envoyé."
}
```

E-mail mal formé : **400**; limite dépassée : **429**. Les erreurs SMTP explicitement interceptées sont consignées côté serveur mais ne changent pas la réponse client. Si l’envoi échoue, l’utilisateur peut donc recevoir un succès sans recevoir le courriel.

### Confirmer la réinitialisation — `POST /api/auth/password-reset/confirm/`

**Accès :** public.

**Corps requis :**

```json
{
  "uid": "<identifiant-encode>",
  "token": "<token-reinitialisation>",
  "nouveau_mot_de_passe": "NouveauMotDePasse!2026"
}
```

Les trois champs sont requis. Le compte doit exister et être actif; le token doit être valide et non expiré. La validation du nouveau mot de passe suit les validateurs Django. Le token devient inutilisable après le changement de mot de passe; les refresh tokens du compte sont révoqués.

**Succès : 204**, sans corps. UID/token invalide ou expiré, compte inactif, ou mot de passe rejeté : **400**; limite dépassée : **429**.

## 2. API Audit

### Consulter le journal — `GET /api/journal-audit/`

**Accès :** `is_staff` ou superutilisateur. Aucun corps JSON. Le résultat est paginé et trié par date décroissante par défaut.

Paramètres de requête pris en charge :

- `action` : choix parmi `connexion`, `deconnexion`, `consultation`, `creation`, `modification`, `suppression`, `telechargement`, `validation`, `export`.
- `entite_cible` : recherche partielle insensible à la casse.
- `utilisateur` : identifiant numérique du compte.
- `depuis`, `jusqua` : bornes ISO datetime inclusives.
- `search` : recherche sur username, entité ou adresse IP.
- `ordering` : `date_action`, `action` ou `entite_cible`, avec préfixe `-` pour inverser.
- `page` : numéro de page, 20 résultats par défaut.

**Succès : 200**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 81,
      "date_action": "2026-11-15T16:00:00Z",
      "action": "modification",
      "entite_cible": "Utilisateur",
      "id_cible": 12,
      "adresse_ip": "192.0.2.10",
      "details": { "champs": ["langue"] },
      "utilisateur_id": 4,
      "utilisateur_username": "admin"
    }
  ]
}
```

`details` est un JSON variable. `utilisateur_id` et `utilisateur_username` peuvent être `null`. Les champs sont en lecture seule. Sans authentification : **401**; authentifié mais non staff : **403**. Paramètre de filtre invalide : **400** selon le filtre concerné.

### Détail — `GET /api/journal-audit/{id}/`

Même autorisation et format de ligne que dans `results`; aucun corps. Succès **200**, identifiant inexistant **404**. Les opérations d’écriture ne sont pas exposées : les tests confirment un **405** sur DELETE.

### Ce qui est effectivement journalisé

Il n’y a pas de middleware ou de signal général qui audite toutes les requêtes. Les vues appellent explicitement la fonction `journaliser` pour les actions suivantes :

- inscription externe et inscription d’ancien étudiant;
- connexion et déconnexion;
- modification du profil utilisateur, changement et réinitialisation du mot de passe;
- création, modification et désactivation de comptes;
- création, modification et suppression de rôles ou permissions;
- modification du profil étudiant.

Le refresh, les consultations de profils, les consultations d’audit et les recherches/listes ne sont pas journalisés par ces appels. Les échecs de connexion ne semblent pas journalisés non plus. Les actions « consultation », « téléchargement », « validation » et « export » existent dans le modèle, mais le code `accounts` consulté ne montre pas leur enregistrement.

Le journal conserve l’utilisateur, l’action, la date, l’adresse IP, la cible et un objet `details`. Il ne conserve pas systématiquement d’instantané des anciennes et nouvelles valeurs : les modifications enregistrent généralement les noms de champs, pas leurs valeurs avant/après. L’adresse IP peut provenir de `X-Forwarded-For` ou de l’adresse directe; l’usage de l’en-tête proxy dépend de la configuration de déploiement.

## 3. API Comptes

### Liste — `GET /api/utilisateurs/`

**Accès :** `is_staff` ou superutilisateur. Aucun corps. Paramètres : `search` (username, e-mail, prénom, nom), `is_active`, `type_utilisateur`, `roles`, `ordering` (username, e-mail, date_joined, last_login, type_utilisateur), `page`. Pagination : 20 par défaut.

**Succès : 200**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 12,
      "username": "amina",
      "email": "amina@example.org",
      "first_name": "Amina",
      "last_name": "Diallo",
      "type_utilisateur": "archiviste",
      "telephone": "",
      "langue": "fr",
      "is_active": true,
      "roles": [{ "id": 3, "code": "archiviste", "libelle": "Archiviste" }],
      "profil_etudiant": null,
      "date_joined": "2026-09-10T09:00:00Z",
      "last_login": "2026-11-15T15:00:00Z"
    }
  ]
}
```

Les champs `password`, `is_staff` et `is_superuser` ne sont pas retournés. Non authentifié : **401**; compte authentifié non staff : **403**.

### Consulter un compte — `GET /api/utilisateurs/{id}/`

**Accès :** identique à la liste. Aucun corps. Succès **200** avec la même structure que l’objet listé; ID absent : **404**.

### Créer un compte — `POST /api/utilisateurs/`

**Accès :** `is_staff` ou superutilisateur. `username`, `email` et `password` sont requis à la création. Les autres champs disponibles incluent `first_name`, `last_name`, `type_utilisateur`, `telephone`, `langue`, `is_active` et `role_ids`.

```json
{
  "username": "amina",
  "email": "amina@example.org",
  "first_name": "Amina",
  "last_name": "Diallo",
  "type_utilisateur": "archiviste",
  "telephone": "+222 45 00 00 00",
  "langue": "fr",
  "is_active": false,
  "role_ids": [3],
  "password": "MotDePasseSolide!2026"
}
```

`role_ids` est une liste d’identifiants de rôles existants. `type_utilisateur` doit appartenir aux choix définis par le modèle : `administrateur`, `archiviste`, `operateur`, `controleur`, `auditeur`, `scolarite`, `financier`, `direction`, `ancien_etudiant`, `externe`. Le username et l’e-mail doivent être uniques sans distinction de casse; le mot de passe est validé par Django. La création d’un compte `ancien_etudiant` sans profil étudiant existant est refusée.

Sans `is_active` fourni, le serializer crée le compte inactif; les rôles sont facultatifs. Le backend ne reçoit pas de champ permettant de définir `is_staff` ou `is_superuser`.

**Succès : 201**, avec l’objet de compte ci-dessus, sans le mot de passe. Doublon, champ invalide, rôle inconnu ou ancien étudiant sans profil : **400**.

### Modifier un compte — `PATCH /api/utilisateurs/{id}/` ou `PUT /api/utilisateurs/{id}/`

**Accès :** `is_staff` ou superutilisateur. PATCH n’exige que les champs modifiés; les champs modifiables sont ceux du serializer de gestion, dont username, e-mail, type, téléphone, langue, état actif, rôles et éventuellement mot de passe.

```json
{
  "is_active": true,
  "role_ids": [3, 5]
}
```

Cette requête réactive le compte et remplace son ensemble de rôles par les rôles listés. Pour remplacer un mot de passe, transmettre `password`; il ne sera jamais renvoyé. Un administrateur ne peut pas désactiver son propre compte. Succès **200**, données invalides ou tentative d’auto-désactivation **400**, compte absent **404**.

### Supprimer ou désactiver — `DELETE /api/utilisateurs/{id}/`

**Accès :** `is_staff` ou superutilisateur. Aucun corps. Malgré le nom HTTP DELETE, le backend **ne supprime pas** la ligne : il met `is_active` à `false` et journalise une modification.

Succès **204**, sans corps. Auto-désactivation interdite : **400**; compte absent : **404**. Réactivation possible par PATCH avec `{"is_active": true}`.

### Rôles disponibles pour un formulaire — `GET /api/utilisateurs/roles/`

**Accès :** `is_staff` ou superutilisateur. Aucun corps. Succès **200** avec une liste non paginée :

```json
[
  { "id": 3, "code": "archiviste", "libelle": "Archiviste" }
]
```

Cette route est distincte de `GET /api/roles/`, qui est la gestion paginée des rôles.

## 4. API Rôles

### Liste et création — `/api/roles/`

**Accès :** `is_staff` ou superutilisateur.

`GET` ne prend pas de corps; paramètres `search` (code/libellé), `ordering` (code/libellé), `page` et `page_size` (jusqu’à 200). Succès **200**, format paginé :

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 3,
      "code": "archiviste",
      "libelle": "Archiviste",
      "permissions": [
        {
          "id": 7,
          "code": "document.consulter",
          "ressource": "document",
          "action": "consulter"
        }
      ]
    }
  ]
}
```

`POST` nécessite `code` et `libelle`; `permission_ids` est facultatif :

```json
{
  "code": "archiviste",
  "libelle": "Archiviste",
  "permission_ids": [7]
}
```

`code` est limité à 50 caractères et unique; `libelle` à 100 caractères. Succès **201** avec le rôle et ses permissions imbriquées; validation ou code dupliqué : **400**. Les créations sont auditées.

### Détail, modification et suppression — `/api/roles/{id}/`

`GET` retourne un objet rôle avec ses permissions : **200**, ou **404** si absent.

`PATCH`/`PUT` modifie le rôle; un PATCH peut inclure `permission_ids` pour remplacer les permissions associées (liste vide pour les retirer). Succès **200**, validation invalide **400**.

`DELETE` supprime le rôle et ses associations de permissions/utilisateurs via les relations Django : **204**. Les trois opérations exigent `is_staff` ou superutilisateur; les changements sont audités.

### Affecter un rôle à un compte

Il n’existe pas de route dédiée `/roles/{id}/affectation`. L’affectation se fait par la gestion d’un compte, avec `PATCH /api/utilisateurs/{id}/` et un champ `role_ids`, par exemple `{"role_ids":[3]}`.

## 5. API Permissions

### Catalogue et création — `/api/permissions/`

**Accès :** `is_staff` ou superutilisateur.

`GET` accepte `search` (code, ressource, action), `ordering` (code, ressource, action), `page` et `page_size` (max. 200). Succès **200**, page de ce type :

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "code": "document.consulter",
      "ressource": "document",
      "action": "consulter"
    }
  ]
}
```

`POST` exige les trois champs :

```json
{
  "code": "document.consulter",
  "ressource": "document",
  "action": "consulter"
}
```

`code` est unique et limité à 100 caractères; `ressource` à 100; `action` à 50. Succès **201** avec l’objet créé; validation ou doublon : **400**. Les créations sont auditées.

### Détail, modification et suppression — `/api/permissions/{id}/`

`GET` retourne une permission (**200**, ou **404**). `PATCH`/`PUT` modifie `code`, `ressource` et/ou `action` (**200**, ou **400** en cas de validation invalide). `DELETE` supprime la permission (**204**). Accès réservé aux comptes staff/superutilisateurs. Les changements sont audités.

### Portée réelle des permissions

Le modèle relie les utilisateurs aux rôles, puis les rôles aux permissions. Le profil de connexion expose une liste `permissions`; il n’existe pas de relation directe utilisateur-permission dans le modèle. `a_permission(code)` sait vérifier si un rôle confère un code, et retourne vrai pour un superutilisateur.

Cependant, dans le code examiné, les endpoints de gestion vérifient `is_staff`/`is_superuser` via `StaffAccountPermission`; je n’ai pas trouvé d’utilisation de `a_permission()` pour protéger les autres endpoints métier. Le frontend possède aussi un helper `hasPermission`, mais une vérification d’interface n’équivaut pas à un contrôle backend. Il faut donc distinguer **permissions affichées/associées** et **contrôle effectif des accès API** : ce dernier n’est pas démontré par les vues `accounts` consultées.

## Routes supplémentaires à ne pas confondre avec les cinq catégories

Le projet expose également des routes « anciens étudiants », documentées séparément dans Swagger :

- `POST /api/anciens-etudiants/inscription/` : inscription publique avec profil étudiant, crée un compte inactif et son profil; **202** si accepté, **400** si données invalides, **429** si limité.
- `GET` et `PATCH /api/anciens-etudiants/me/` : profil de l’ancien étudiant connecté; **200**, **404** si aucun profil n’est associé. Le PATCH accepte `matricule`, `cni`, `date_naissance`, `annee_promotion`, `filiere`; les dates futures sont rejetées, l’année de promotion doit être entre 1950 et 2100 et ne peut pas être future.

## Tableau récapitulatif

| API | Endpoint | Méthode HTTP | Request JSON | Response JSON | Code HTTP de succès | Autorisation |
|---|---|---|---|---|---:|---|
| Authentification | `/api/auth/login/` | POST | `username`, `password` | `access`, `refresh`, `user` | 200 | Public |
| Authentification | `/api/auth/register/` | POST | username, email, prénom, nom, password | `detail` | 202 | Public |
| Authentification | `/api/auth/refresh/` | POST | `refresh` | `access` | 200 | Refresh valide |
| Authentification | `/api/auth/logout/` | POST | `refresh` | Aucun | 204 | Authentifié; refresh du même compte |
| Authentification | `/api/auth/me/` | GET | Aucun | Profil utilisateur | 200 | Authentifié |
| Authentification | `/api/auth/me/` | PATCH | Champs profil modifiables | Profil utilisateur mis à jour | 200 | Authentifié |
| Authentification | `/api/auth/change-password/` | POST | Ancien et nouveau mot de passe | Aucun | 204 | Authentifié |
| Authentification | `/api/auth/password-reset/` | POST | `email` | `detail` générique | 200 | Public |
| Authentification | `/api/auth/password-reset/confirm/` | POST | `uid`, `token`, nouveau mot de passe | Aucun | 204 | Public avec lien valide |
| Audit | `/api/journal-audit/` | GET | Aucun; filtres en query string | Page `count/next/previous/results` | 200 | Staff/superutilisateur |
| Audit | `/api/journal-audit/{id}/` | GET | Aucun | Ligne d’audit | 200 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/` | GET | Aucun; recherche/filtres en query string | Page de comptes | 200 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/` | POST | Champs compte + password; `role_ids` facultatif | Compte créé | 201 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/{id}/` | GET | Aucun | Compte | 200 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/{id}/` | PATCH/PUT | Champs de compte modifiables | Compte modifié | 200 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/{id}/` | DELETE | Aucun | Aucun | 204 | Staff/superutilisateur |
| Comptes | `/api/utilisateurs/roles/` | GET | Aucun | Liste de rôles simples | 200 | Staff/superutilisateur |
| Rôles | `/api/roles/` | GET | Aucun; search/order/page | Page de rôles avec permissions | 200 | Staff/superutilisateur |
| Rôles | `/api/roles/` | POST | `code`, `libelle`, `permission_ids` facultatif | Rôle créé | 201 | Staff/superutilisateur |
| Rôles | `/api/roles/{id}/` | GET | Aucun | Rôle avec permissions | 200 | Staff/superutilisateur |
| Rôles | `/api/roles/{id}/` | PATCH/PUT | `code`, `libelle`, `permission_ids` | Rôle modifié | 200 | Staff/superutilisateur |
| Rôles | `/api/roles/{id}/` | DELETE | Aucun | Aucun | 204 | Staff/superutilisateur |
| Permissions | `/api/permissions/` | GET | Aucun; search/order/page | Page de permissions | 200 | Staff/superutilisateur |
| Permissions | `/api/permissions/` | POST | `code`, `ressource`, `action` | Permission créée | 201 | Staff/superutilisateur |
| Permissions | `/api/permissions/{id}/` | GET | Aucun | Permission | 200 | Staff/superutilisateur |
| Permissions | `/api/permissions/{id}/` | PATCH/PUT | `code`, `ressource`, `action` | Permission modifiée | 200 | Staff/superutilisateur |
| Permissions | `/api/permissions/{id}/` | DELETE | Aucun | Aucun | 204 | Staff/superutilisateur |

## Erreurs courantes et limites confirmées

- Les erreurs de validation DRF sont généralement **400** et structurées par champ; les identifiants invalides de login donnent **401**.
- Un utilisateur non authentifié obtient normalement **401**; un utilisateur authentifié sans statut staff obtient **403** pour comptes, rôles, permissions et audit.
- Un identifiant d’objet absent donne généralement **404**; les écritures sur le journal d’audit donnent **405**.
- Les codes uniques du modèle sont validés en **400**; aucune réponse **409** dédiée n’est définie.
- **429** est explicitement prévu pour login, inscriptions et réinitialisations limitées en débit.
- Les erreurs serveur inattendues peuvent produire un **500**, mais aucune réponse métier spécifique **500** n’est définie pour ces endpoints.
- Le journal d’audit est consultable en lecture seule via API; son ajout/modification/suppression n’est pas exposé par ces routes.

## Annexe — Jeu de données pour préparer les tests dans Django Admin

### Django Admin et Swagger sont deux outils différents

Django Admin sert à créer ou vérifier les données persistantes (comptes, rôles et permissions). Il ne permet pas de « remplir » un endpoint REST : pour tester les endpoints, envoyer leurs méthodes, URLs et corps JSON depuis Swagger UI (`/api/docs/`). Pour les routes protégées, utiliser **Authorize** dans Swagger et renseigner `Bearer <access>`.

L’accès à `/admin/` nécessite déjà un superutilisateur. Si aucun n’existe, le créer avec la commande Django `createsuperuser`, puis se connecter à l’administration. Ne pas saisir un mot de passe en clair directement dans la base de données : passer par le formulaire utilisateur Django, qui applique le mécanisme de hachage du mot de passe.

Les valeurs et mots de passe ci-dessous sont réservés aux essais en développement. Ne pas les réutiliser en production. Les identifiants générés par la base ne sont pas prédéterminés : relever les `id` retournés par l’API ou affichés dans Django Admin.

### Données de préparation à saisir dans `/admin/`

#### 1. Créer des permissions métier

Dans **Accounts > Permissions**, ajouter deux entrées :

| Code | Ressource | Action |
|---|---|---|
| `document.consulter` | `document` | `consulter` |
| `document.exporter` | `document` | `exporter` |

Le code doit être unique. Ces objets alimentent le catalogue renvoyé par `/api/permissions/`.

#### 2. Créer un rôle et lui associer des permissions

Dans **Accounts > Roles**, ajouter :

| Code | Libellé | Permissions associées |
|---|---|---|
| `api-archiviste` | `Archiviste de test` | `document.consulter` |

Pour choisir les permissions, utiliser le champ de relation multiple du formulaire. L’association est lue par l’API du rôle et sera aussi visible dans le profil des comptes auxquels ce rôle est affecté.

#### 3. Préparer un compte administrateur pour les API protégées

Dans **Accounts > Utilisateurs**, créer ou vérifier un compte de test, par exemple :

| Champ | Valeur d’essai |
|---|---|
| `username` | `api.admin` |
| `email` | `api.admin@example.org` |
| `first_name` | `Admin` |
| `last_name` | `API` |
| `type_utilisateur` | `administrateur` |
| `telephone` | `+222 45 00 00 01` |
| `langue` | `fr` |
| `is_active` | activé |
| `is_staff` | activé |
| `is_superuser` | désactivé si un accès staff simple suffit |
| `roles` | facultatif |
| Mot de passe | définir un mot de passe de test par le formulaire Django |

`is_staff` (ou `is_superuser`) est nécessaire pour les endpoints de gestion, rôles, permissions et audit. Un rôle métier comme `api-archiviste` ne donne pas cette autorisation administrative.

#### 4. Préparer un compte utilisateur ordinaire

Créer un second utilisateur de test :

| Champ | Valeur d’essai |
|---|---|
| `username` | `api.archiviste` |
| `email` | `api.archiviste@example.org` |
| `first_name` | `Amina` |
| `last_name` | `Archiviste` |
| `type_utilisateur` | `archiviste` |
| `telephone` | `+222 45 00 00 02` |
| `langue` | `fr` |
| `is_active` | activé |
| `is_staff` | désactivé |
| `roles` | `api-archiviste` |
| Mot de passe | définir un mot de passe de test par le formulaire Django |

Ce compte sert à tester login, profil, changement de mot de passe et les refus **403** sur les routes réservées au staff. Son rôle devrait apparaître dans `/api/auth/me/`; sa permission associée devrait apparaître dans `permissions`.

#### 5. Journal d’audit

Ne pas tenter d’ajouter manuellement une entrée dans **Accounts > Journal d’audit** : l’administration est configurée en lecture seule et refuse l’ajout, la modification et la suppression. Les entrées sont créées par les opérations API qui appellent explicitement la fonction de journalisation.

### Exemples de requêtes Swagger à effectuer après la préparation

Dans les exemples ci-dessous, remplacer `{{access}}`, `{{refresh}}` et les identifiants `{{..._id}}` par les valeurs réelles retournées lors des appels. Pour les requêtes protégées, envoyer `Authorization: Bearer {{access}}`.

#### API 1 — Authentification

1. **Login — `POST /api/auth/login/`**  
   Utiliser le compte actif `api.archiviste` :

   ```json
   {
     "username": "api.archiviste",
     "password": "<mot-de-passe-défini-dans-Django-Admin>"
   }
   ```

   Conserver `access` et `refresh` de la réponse. Le compte doit être actif.

2. **Register — `POST /api/auth/register/`**  
   Utiliser un username et un e-mail encore inutilisés :

   ```json
   {
     "username": "api.externe.test",
     "email": "api.externe.test@example.org",
     "first_name": "Externe",
     "last_name": "Test",
     "password": "E7!vQp-49#Nuage"
   }
   ```

   Attendu : **202** et compte inactif. Pour le connecter ensuite, retrouver le compte dans Django Admin et activer `is_active`.

3. **Refresh — `POST /api/auth/refresh/`**

   ```json
   { "refresh": "{{refresh}}" }
   ```

   Attendu : **200** avec un nouveau champ `access`.

4. **Logout — `POST /api/auth/logout/`**  
   Ajouter l’en-tête Bearer du compte qui possède le refresh :

   ```json
   { "refresh": "{{refresh}}" }
   ```

   Attendu : **204** sans corps. Le refresh ne pourra ensuite plus être utilisé.

5. **Consulter son profil — `GET /api/auth/me/`**  
   Aucun corps JSON. Envoyer l’access. Avec `api.archiviste`, vérifier `roles` et `permissions`.

6. **Modifier son profil — `PATCH /api/auth/me/`**

   ```json
   {
     "first_name": "Amina-Test",
     "telephone": "+222 45 00 00 10",
     "langue": "ar"
   }
   ```

   Attendu : **200** et profil complet mis à jour.

7. **Changer le mot de passe — `POST /api/auth/change-password/`**

   ```json
   {
     "ancien_mot_de_passe": "<mot-de-passe-actuel>",
     "nouveau_mot_de_passe": "Nouveau-Api!2026"
   }
   ```

   Attendu : **204**. Le nouveau mot de passe doit respecter les validateurs configurés.

8. **Demander une réinitialisation — `POST /api/auth/password-reset/`**

   ```json
   { "email": "api.archiviste@example.org" }
   ```

   Attendu : **200** avec le message générique. En développement, le backend utilise par défaut le backend e-mail console : consulter la console du serveur pour récupérer le lien généré.

9. **Confirmer la réinitialisation — `POST /api/auth/password-reset/confirm/`**  
   Copier `uid` et `token` depuis le lien reçu, puis envoyer :

   ```json
   {
     "uid": "<uid-copié-du-lien>",
     "token": "<token-copié-du-lien>",
     "nouveau_mot_de_passe": "Nouveau-Api!2026"
   }
   ```

   Attendu : **204**; le lien ne peut ensuite plus servir.

#### API 2 — Audit

1. **Lister et filtrer — `GET /api/journal-audit/`**  
   Se connecter avec `api.admin`, puis envoyer l’access. Exemple de paramètres :

   ```text
   /api/journal-audit/?action=connexion&search=api.archiviste&page=1
   ```

   Aucun corps JSON. Attendu : **200** avec `count`, `next`, `previous` et `results`. Pour tester les dates, ajouter par exemple `depuis=2026-11-01T00:00:00Z&jusqua=2026-11-30T23:59:59Z`.

2. **Consulter une entrée — `GET /api/journal-audit/{{audit_id}}/`**  
   Prendre un `id` présent dans `results`; aucun corps JSON. Attendu : **200**. Le `DELETE` sur cette ressource doit être refusé (**405**).

Pour obtenir des lignes récentes, effectuer d’abord un login, une modification de profil ou une modification administrative : ces opérations sont parmi celles qui écrivent effectivement une entrée d’audit.

#### API 3 — Comptes

Utiliser le Bearer de `api.admin` pour tous ces appels.

1. **Lister — `GET /api/utilisateurs/`**  
   Aucun corps. Exemple de filtres :

   ```text
   /api/utilisateurs/?search=api.archiviste&is_active=true&type_utilisateur=archiviste&page=1
   ```

2. **Créer — `POST /api/utilisateurs/`**

   ```json
   {
     "username": "api.nouvel.utilisateur",
     "email": "api.nouvel.utilisateur@example.org",
     "first_name": "Nouveau",
     "last_name": "Compte",
     "type_utilisateur": "externe",
     "telephone": "+222 45 00 00 11",
     "langue": "fr",
     "is_active": false,
     "role_ids": [3],
     "password": "Nouveau-Compte!2026"
   }
   ```

   Remplacer `3` par l’identifiant numérique réel du rôle. Si aucun rôle n’est souhaité, envoyer `"role_ids": []`. Attendu : **201**; le password ne sera pas retourné.

3. **Consulter — `GET /api/utilisateurs/{{user_id}}/`**  
   Utiliser un `id` de compte retourné par la liste ou la création. Aucun corps; attendu **200**.

4. **Modifier/réactiver — `PATCH /api/utilisateurs/{{user_id}}/`**

   ```json
   {
     "is_active": true,
     "role_ids": [3],
     "telephone": "+222 45 00 00 12"
   }
   ```

   Remplacer `3` par l’identifiant numérique réel du rôle. Attendu : **200**. L’omission de `role_ids` ne demande pas de changer les rôles; une liste vide les retire tous.

5. **Désactiver — `DELETE /api/utilisateurs/{{user_id}}/`**  
   Aucun corps. Attendu : **204**; le compte est conservé en base et rendu inactif. Ne pas utiliser l’ID du compte actuellement connecté : l’auto-désactivation est rejetée.

6. **Lister les rôles sélectionnables — `GET /api/utilisateurs/roles/`**  
   Aucun corps. Attendu : **200** avec une liste non paginée de `{id, code, libelle}`.

#### API 4 — Rôles

Ces opérations exigent le Bearer de `api.admin`.

1. **Lister — `GET /api/roles/?search=api-archiviste&page=1&page_size=100`**  
   Aucun corps. Attendu : **200** paginé.

2. **Créer — `POST /api/roles/`**  
   Pour tester la création via l’API, employer un code jamais utilisé (ne pas réutiliser `api-archiviste` s’il a déjà été créé dans Admin) :

   ```json
   {
     "code": "api-role-temporaire",
     "libelle": "Rôle temporaire de test",
     "permission_ids": [7]
   }
   ```

   Attendu : **201** avec `permissions` en lecture dans la réponse.

3. **Consulter — `GET /api/roles/{{role_id}}/`**  
   Aucun corps; attendu **200** avec les permissions associées.

4. **Modifier — `PATCH /api/roles/{{role_id}}/`**

   ```json
   {
     "libelle": "Rôle temporaire modifié",
     "permission_ids": [7]
   }
   ```

   Attendu : **200**. L’API remplace la relation par les IDs transmis.

5. **Supprimer — `DELETE /api/roles/{{role_id}}/`**  
   Aucun corps; attendu **204**. Pour préserver le jeu de données Admin, utiliser un rôle temporaire créé uniquement pour le test.

#### API 5 — Permissions

Ces opérations exigent également le Bearer de `api.admin`.

1. **Lister — `GET /api/permissions/?search=document&page=1&page_size=100`**  
   Aucun corps; attendu **200** paginé.

2. **Créer — `POST /api/permissions/`**  
   Utiliser un code inédit pour éviter le doublon :

   ```json
   {
     "code": "api.temporaire.consulter",
     "ressource": "api_temporaire",
     "action": "consulter"
   }
   ```

   Attendu : **201** avec l’objet créé.

3. **Consulter — `GET /api/permissions/{{permission_id}}/`**  
   Aucun corps; attendu **200**.

4. **Modifier — `PATCH /api/permissions/{{permission_id}}/`**

   ```json
   {
     "code": "api.temporaire.modifier",
     "ressource": "api_temporaire",
     "action": "modifier"
   }
   ```

   Attendu : **200**. Choisir un code non utilisé.

5. **Supprimer — `DELETE /api/permissions/{{permission_id}}/`**  
   Aucun corps; attendu **204**. Utiliser une permission temporaire afin de ne pas enlever une permission utilisée par le jeu de test.

### Notes de remise en état des données de test

- Les opérations de création, modification et désactivation produisent des lignes d’audit; elles ne se suppriment pas depuis l’API.
- `DELETE /api/utilisateurs/{id}/` ne supprime pas le compte; remettre `is_active=true` par PATCH ou Django Admin si le test doit être rejoué.
- Une permission utilisée par un rôle peut être supprimée par l’API, mais cela change le jeu de données du rôle. Réserver les suppressions à des enregistrements temporaires.
- Les noms d’utilisateur, e-mails, codes de rôles et codes de permissions doivent rester uniques. Pour répéter les tests de POST, choisir de nouvelles valeurs ou supprimer/réutiliser uniquement les données temporaires.