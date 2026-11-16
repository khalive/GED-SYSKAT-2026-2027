# GED ENG

Application de gestion électronique des documents de l'École Nationale de Gestion.
Ce dépôt contient une API Django REST et un client Angular.

## Profils et règles d'accès mis en place

L'authentification est basée sur les rôles (RBAC) : les permissions sont attachées à
des rôles, puis les rôles aux comptes. Les permissions ne sont pas attribuées directement
aux utilisateurs. La migration `accounts.0004_profils_et_permissions_initiaux` crée ou
complète le catalogue des 10 rôles correspondant à `Utilisateur.type_utilisateur` et
les 4 rôles facultatifs. Les comptes existants et les inscriptions obtiennent le rôle
correspondant à leur type; un administrateur peut ensuite attribuer d'autres rôles.
Le Django Admin masque les permissions individuelles et les groupes Django; il affiche
les rôles en lecture seule. Les changements RBAC passent par l'API/écran dédiés.

| Profil | Droits configurés |
| --- | --- |
| Administrateur | Comptes, rôles, permissions, types de documents, plan de classement, sauvegardes, supervision et audit. Aucun droit de signature officielle. |
| Auditeur | Consultation et export CSV du journal d'audit; aucune écriture dans les comptes ou le journal. |
| Direction | Validation des demandes et éliminations, signature des documents officiels, tableau de bord. Aucun droit de numérisation. |
| Archiviste | Classement, règles de conservation, emplacements papier et établissement des bordereaux d'élimination. |
| Opérateur de numérisation | Création des lots, import, métadonnées et correction OCR. Aucun droit de suppression ou de contrôle qualité. |
| Contrôleur qualité | Contrôle, validation et rejet des lots; pas de droit de numérisation. |
| Agent de scolarité | Consultation des dossiers étudiants, vérification des duplicata et génération de documents officiels. |
| Agent financier | Vérification des paiements et consultation des documents financiers. |
| Ancien étudiant | Demandes, suivi et téléchargement de ses documents livrés; pas d'accès aux archives générales. |
| Utilisateur externe | Vérification publique d'authenticité par code QR uniquement; aucun accès aux archives. |
| Super administrateur (facultatif) | Paramètres techniques, sauvegardes et supervision; distinct de l'administration fonctionnelle. |
| Agent RH (facultatif) | Consultation et gestion des dossiers du personnel. |
| Enseignant (facultatif) | Consultation des procès-verbaux de notes. |
| Visiteur en lecture seule (facultatif) | Consultation des seuls documents publics. |
                                             
Les quatre rôles facultatifs ne sont pas ajoutés à `Utilisateur.type_utilisateur` : ils
restent des rôles RBAC, comme prévu par le schéma à 25 tables. Les permissions initiales
sont définies par la migration; l'administration peut les faire évoluer dans l'écran
« Rôles & permissions ». Les rôles système ne peuvent pas être renommés ni supprimés.
La validation des affectations interdit de cumuler les tâches de numérisation et de
contrôle qualité, d'établissement et validation d'élimination, ainsi que l'administration
technique avec la signature et la validation d'élimination.

La portée des droits est affinée par rôle : `TypeDocument.roles_autorises` est utilisé
pour restreindre les types, et `Dossier.roles_autorises` permet les restrictions sur un
dossier et ses parents. Une liste vide n'ajoute pas de restriction à ce niveau. Le helper
`Utilisateur.a_acces_document()` exige aussi la permission métier; les comptes anciens
étudiants et externes ne peuvent pas l'utiliser pour ouvrir les archives. Chaque accès
aux écrans/API sensibles existants, ainsi que l'export et la vérification QR, est tracé.

L'audit est disponible aux profils administrateur et auditeur; l'API est en lecture seule
et l'export CSV respecte les filtres de recherche. La route publique
`GET /api/verification/{code_qr}/` ne retourne que l'état d'authenticité, le numéro
officiel, la date de génération et l'état de signature, sans information sur le demandeur.
Les guards Angular et la navigation masquent également les écrans sans permission, mais
les permissions du backend restent la protection effective.

**Limite fonctionnelle actuelle :** les applications `documents`, `digitization`,
`conservation`, `workflow` et `core` contiennent les modèles métier, mais ne déclarent
pas encore d'API CRUD ou de parcours UI pour les lots, dossiers, documents, paiements,
demandes, bordereaux, tableau de bord, sauvegardes ou paramètres. Le catalogue prépare
leurs droits et les helpers de portée, mais leurs opérations ne sont pas exécutables dans
cette livraison tant que leurs endpoints ne sont pas créés et reliés à ces permissions.

## Avancement

| API | État |
| --- | --- |
| Authentification | Implémentée : JWT, profil, changement/réinitialisation de mot de passe, inscription externe contrôlée. |
| Utilisateurs | Implémentée : CRUD administratif sans suppression définitive, recherche, filtres et pagination. |
| Rôles et permissions | Implémentée : gestion administrative des rôles et du catalogue de permissions. |
| Anciens étudiants | Implémentée : demande d'inscription en attente et profil personnel protégé. |
| Journal d'audit | Implémentée : consultation paginée en lecture seule pour administrateur/auditeur et export CSV. |

Les parcours d'authentification, de comptes, de rôles, d'anciens étudiants et d'audit
sont raccordés au frontend; la vérification QR est une API publique backend. Les
résultats des tests récents sont récapitulés plus bas.

## Architecture

- `backend/apps/accounts/` : modèle de compte, rôles, permissions, audit et endpoints
  d'authentification, de gestion des comptes, des anciens étudiants et de l'audit.
- `backend/config/` : configuration Django, base de données, middleware et routes.
- `frontend/src/app/core/` : services HTTP, modèles, interceptor, guards et layout.
- `frontend/src/app/features/auth/` : écrans de connexion, inscription et réinitialisation.
- `frontend/src/app/features/profil/` : consultation et modification du compte personnel.

Le projet inclut également les applications Django `core`, `documents`, `digitization`,
`conservation` et `workflow`. Leurs API ne sont pas déclarées terminées dans cette étape.

## Dépendances déclarées

- Backend : Django 5.2.19, Django REST Framework 3.18.3, SimpleJWT 5.5.1,
  drf-spectacular 0.30.0 et django-filter 26.2 (`backend/requirements/base.txt`).
- Frontend : Angular 21.2, TypeScript 5.9, RxJS 7.8 et Vitest 4
  (`frontend/package.json` et `frontend/package-lock.json`).

## Configuration et lancement

### Comptes de démonstration

Sur une base PostgreSQL locale/de développement uniquement, avec `DEBUG=True`, appliquer
les migrations puis lancer depuis `backend` :

```powershell
python manage.py migrate
python manage.py seed_demo_users --confirm
```

La commande crée 14 comptes actifs (les 10 types principaux et 4 rôles facultatifs),
avec des rôles dédiés et un profil étudiant de démonstration. Elle affiche les 14
identifiants et génère un mot de passe aléatoire commun; ce mot de passe n'est pas
conservé dans le dépôt. Une nouvelle exécution réinitialise ces comptes et génère un
nouveau mot de passe. Ne jamais utiliser ces comptes sur une base de production.

### Backend

1. Depuis `backend`, créer un environnement virtuel et installer les dépendances :

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements\base.txt
   Copy-Item .env.example .env
   ```

2. Renseigner dans `.env` la clé Django, les paramètres PostgreSQL et les hôtes autorisés.
   Le backend est configuré pour PostgreSQL.
3. Pour le SMTP, configurer `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`,
   `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` ou `EMAIL_USE_SSL`,
   `EMAIL_TIMEOUT` et `DEFAULT_FROM_EMAIL`. Sans backend SMTP explicite, Django utilise
   le backend console configuré dans `base.py`.
4. Appliquer les migrations et démarrer :

   ```powershell
   python manage.py migrate
   python manage.py runserver
   ```

### Frontend

Depuis `frontend` :

```powershell
npm ci
npm start
```

Le serveur Angular écoute sur `http://localhost:4200` et utilise `proxy.conf.json`
pour transmettre `/api` à Django sur `http://127.0.0.1:8000`.

## API Authentification

Les routes sont préfixées par `/api`. Les routes protégées exigent un jeton d'accès
JWT dans l'en-tête `Authorization: Bearer <access>`.

| Méthode | Endpoint | Accès | Résultat |
| --- | --- | --- | --- |
| POST | `/api/auth/register/` | Public | 202 ; crée un compte externe inactif, à valider par l'administration |
| POST | `/api/auth/login/` | Public | Jetons `access` et `refresh`, profil utilisateur |
| POST | `/api/auth/refresh/` | Public avec refresh valide | Nouveau jeton d'accès |
| POST | `/api/auth/logout/` | Authentifié | 204 ; invalide uniquement le refresh appartenant à ce compte |
| GET | `/api/auth/me/` | Authentifié | Profil, rôles, permissions et profil étudiant éventuel |
| PATCH | `/api/auth/me/` | Authentifié | Modifie prénom, nom, téléphone ou langue (`fr`/`ar`) |
| POST | `/api/auth/change-password/` | Authentifié | 204 ; vérifie l'ancien et valide le nouveau mot de passe |
| POST | `/api/auth/password-reset/` | Public | Réponse générique 200 ; envoie un lien si le compte actif existe |
| POST | `/api/auth/password-reset/confirm/` | Public | 204 si le lien est valide ; 400 pour lien invalide/expiré ou mot de passe rejeté |

L'inscription reçoit `username`, `email`, `first_name`, `last_name` et `password`.
Elle attribue le rôle de base « Utilisateur externe », sans permission d'accès aux archives,
et ne crée pas de session ; un administrateur doit activer
le compte via Django Admin avant sa première connexion. Les inscriptions sont limitées
à 5 par heure et par adresse IP. L'inscription n'envoie pas de courriel de vérification.

La demande de réinitialisation reçoit `{ "email": "..." }`. La confirmation reçoit
`{ "uid": "...", "token": "...", "nouveau_mot_de_passe": "..." }`. Les réponses de
demande restent identiques pour les adresses inconnues afin de limiter l'énumération.
La demande est limitée à 5 par heure et par adresse IP ; la connexion à 20 par minute.

L'authentification s'appuie sur SimpleJWT : jeton d'accès de 30 minutes et refresh d'un
jour. Le lien de réinitialisation utilise le générateur signé de Django et expire après
`PASSWORD_RESET_TIMEOUT` (valeur par défaut : 3600 secondes). Il devient inutilisable
après changement de mot de passe ; les refresh tokens du compte sont révoqués lors d'une
réinitialisation ou d'un changement de mot de passe.
La durée n'est pas prolongée implicitement.

## API Utilisateurs

Toutes les routes ci-dessous exigent la permission `utilisateurs.gerer`; les comptes
`is_staff` historiques sans rôle et les superutilisateurs restent compatibles.
La liste est paginée (20 résultats par défaut) et accepte `search`, `type_utilisateur`,
`is_active` et les paramètres d'ordre exposés par l'API.

| Méthode | Endpoint | Résultat |
| --- | --- | --- |
| GET | `/api/utilisateurs/` | Liste filtrable et paginée |
| POST | `/api/utilisateurs/` | Crée un compte ; inactif par défaut et sans privilège administrateur |
| GET | `/api/utilisateurs/{id}/` | Consulte un compte et, pour un alumni, son parcours déclaré |
| PATCH / PUT | `/api/utilisateurs/{id}/` | Modifie un compte, ses rôles ou son état actif |
| DELETE | `/api/utilisateurs/{id}/` | Désactive le compte sans effacer son historique |
| GET | `/api/utilisateurs/roles/` | Rôles disponibles pour l'affectation |

La suppression est réversible : `DELETE` désactive le compte et conserve son historique.
Un administrateur peut le réactiver avec `PATCH`; l'auto-désactivation est interdite.
Le mot de passe peut être défini à la création ou remplacé par un administrateur ; il
n'est jamais renvoyé dans les réponses.

## API Rôles et permissions

La gestion des rôles et permissions exige les permissions GED correspondantes
(`roles.gerer` et `permissions.gerer`). Les comptes `is_staff` historiques sans rôle
et les superutilisateurs restent compatibles.
Les listes sont paginées (100 résultats par défaut, `page_size` plafonné à 200),
recherchables et triables. Un rôle retourne ses permissions associées et accepte
`permission_ids` en écriture.

| Méthode | Endpoint | Résultat |
| --- | --- | --- |
| GET / POST | `/api/roles/` | Liste des rôles / crée un rôle |
| GET / PATCH / PUT / DELETE | `/api/roles/{id}/` | Consulte, modifie ou supprime un rôle |
| GET / POST | `/api/permissions/` | Liste du catalogue / crée une permission |
| GET / PATCH / PUT / DELETE | `/api/permissions/{id}/` | Consulte, modifie ou supprime une permission |

Les créations, modifications et suppressions sont inscrites au journal d'audit.

## API Anciens étudiants

| Méthode | Endpoint | Accès et résultat |
| --- | --- | --- |
| POST | `/api/anciens-etudiants/inscription/` | Public, limité en débit ; crée un compte inactif et son profil étudiant |
| GET | `/api/anciens-etudiants/me/` | Authentifié ; consulte son propre profil étudiant |
| PATCH | `/api/anciens-etudiants/me/` | Authentifié ; met à jour son propre profil étudiant |

La demande exige les informations de compte et de parcours (matricule, CNI, date de
naissance, année de promotion et filière). Elle ne crée pas de session ; l'activation
reste réservée à l'administration. Un utilisateur sans profil étudiant ne peut pas
consulter ou modifier ce dernier.

## API Journal d'audit

| Méthode | Endpoint | Accès et résultat |
| --- | --- | --- |
| GET | `/api/journal-audit/` | Administrateur ou auditeur ; liste paginée, triable et filtrable |
| GET | `/api/journal-audit/{id}/` | Administrateur ou auditeur ; détail en lecture seule |
| GET | `/api/journal-audit/export/` | Administrateur ou auditeur avec `audit.exporter` ; export CSV filtré |

Filtres disponibles : `action`, `entite_cible`, `utilisateur`, `depuis`, `jusqua`.
La recherche textuelle porte sur l'identifiant utilisateur, l'entité et l'adresse IP.
Les opérations de création, modification et suppression ne sont pas exposées.

## Vérification publique

| Méthode | Endpoint | Accès et résultat |
| --- | --- | --- |
| GET | `/api/verification/{code_qr}/` | Public ; vérifie le document officiel sans révéler l'identité ni les archives |

## OpenAPI / Swagger

Une fois le backend démarré :

- Schéma OpenAPI : `http://localhost:8000/api/schema/`
- Swagger UI : `http://localhost:8000/api/docs/`

Les opérations d'authentification sont regroupées sous le tag « Authentification ».
Les API de gestion, d'anciens étudiants et d'audit ont leurs tags OpenAPI dédiés.

## Interface

Le frontend comprend les écrans de connexion, inscription, réinitialisation et profil,
une interface d'administration des utilisateurs, rôles et permissions, le parcours de
demande/profil ancien étudiant et le journal d'audit. Les écrans de gestion proposent
recherche, pagination, états de chargement/erreur, confirmations de suppression et
notification des opérations. Le layout partagé prend en charge les thèmes clair et sombre.

## Vérification

- `manage.py check` : réussi.
- `manage.py makemigrations --check --dry-run` : aucune migration manquante.
- Suite Django complète sur SQLite de test : 48 tests réussis.
- `npm test -- --watch=false` : 6 tests frontend réussis.
- `npm run build` : réussi; Angular signale des avertissements de budget SCSS sur certains écrans.

Le SMTP réel et le parcours navigateur complet ne sont pas validés. Les tests doivent
être lancés sur une base de test, jamais contre la base de production. Sans backend SMTP
explicite, Django utilise le backend console configuré dans `base.py`.
