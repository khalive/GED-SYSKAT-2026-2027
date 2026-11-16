# Application `accounts`

## Présentation

L’application Django `backend/apps/accounts/` gère les comptes et les profils
utilisateurs de la GED, l’authentification, les rôles et permissions, le journal
d’audit, ainsi que l’inscription des anciens étudiants. Elle expose une API REST
consommée par le frontend Angular.

Les routes de cette application sont préfixées par `/api`.

## Données principales

- **Utilisateur** : compte de connexion dérivé du modèle Django `AbstractUser`.
  Il contient notamment un identifiant, une adresse e-mail unique, un type
  d’utilisateur, un téléphone, une langue (`fr` ou `ar`) et des rôles.
- **Rôle** : profil fonctionnel auquel sont associés des droits.
- **Permission** : droit métier unitaire identifié par un code, une ressource et
  une action, par exemple `audit.consulter`.
- **AncienEtudiant** : profil complémentaire lié à un seul utilisateur, avec
  matricule, CNI, date de naissance, promotion et filière.
- **JournalAudit** : trace d’une action avec son auteur éventuel, sa date, son
  type, son entité cible, son adresse IP et des détails complémentaires.

Les dix types pris en charge par `Utilisateur.type_utilisateur` sont :
administrateur, archiviste, opérateur, contrôleur, auditeur, scolarité,
financier, direction, ancien étudiant et utilisateur externe.

La migration `accounts.0004_profils_et_permissions_initiaux` ajoute aussi quatre
rôles facultatifs, sans les ajouter aux types d’utilisateur : super administrateur,
agent RH, enseignant et visiteur en lecture seule.

## Fonctionnalités exposées

### Authentification et profil

L’API utilise des jetons JWT. La connexion renvoie les jetons d’accès et de
renouvellement ainsi que le profil, ses rôles et ses permissions. Les jetons
d’accès expirent après 30 minutes et les jetons de renouvellement après un jour.

| Méthode | Route | Fonction |
| --- | --- | --- |
| `POST` | `/api/auth/register/` | Demande d’inscription d’un compte externe inactif |
| `POST` | `/api/auth/login/` | Connexion et émission des jetons |
| `POST` | `/api/auth/refresh/` | Renouvellement du jeton d’accès |
| `POST` | `/api/auth/logout/` | Invalidation du jeton de renouvellement du compte connecté |
| `GET`, `PATCH` | `/api/auth/me/` | Consultation ou modification des champs du profil personnel |
| `POST` | `/api/auth/change-password/` | Changement du mot de passe connecté |
| `POST` | `/api/auth/password-reset/` | Demande de réinitialisation par e-mail |
| `POST` | `/api/auth/password-reset/confirm/` | Confirmation du nouveau mot de passe |

Les réponses à une demande de réinitialisation restent identiques que l’adresse
e-mail corresponde ou non à un compte actif. Après un changement ou une
réinitialisation du mot de passe, les jetons de renouvellement du compte sont
révoqués.

### Gestion des comptes, rôles et permissions

| Route | Fonction |
| --- | --- |
| `/api/utilisateurs/` | Liste paginée, recherche, création et consultation des comptes |
| `/api/utilisateurs/{id}/` | Consultation, modification et désactivation d’un compte |
| `/api/utilisateurs/roles/` | Liste des rôles attribuables |
| `/api/roles/` | Consultation et gestion des rôles |
| `/api/permissions/` | Consultation et gestion du catalogue de permissions |

Ces opérations exigent les permissions métier appropriées. La suppression d’un
compte désactive celui-ci au lieu d’effacer son historique. Un compte ne peut
pas se désactiver lui-même par ce mécanisme. Les rôles système ne peuvent pas
être renommés ou supprimés.

Les rôles principaux et leurs responsabilités configurées sont :

| Rôle | Principales permissions |
| --- | --- |
| Administrateur | Gestion des comptes, rôles, permissions, types de documents, classement, sauvegardes, supervision et audit |
| Auditeur | Consultation et export du journal d’audit |
| Direction | Validation des demandes et éliminations, signature et tableau de bord |
| Archiviste | Classement, conservation, emplacements et établissement des éliminations |
| Opérateur | Création des lots, import, métadonnées et correction OCR |
| Contrôleur | Contrôle, validation et rejet des lots |
| Scolarité | Consultation des dossiers étudiants, vérification des duplicata et génération de documents |
| Financier | Vérification des paiements et consultation des documents financiers |
| Ancien étudiant | Création et suivi de ses demandes, téléchargement de ses documents livrés |
| Externe | Vérification publique de l’authenticité d’un document |

Les rôles facultatifs sont le super administrateur (paramètres techniques,
sauvegardes et supervision), l’agent RH (dossiers du personnel), l’enseignant
(procès-verbaux de notes) et le visiteur en lecture seule (documents publics).

### Anciens étudiants

| Méthode | Route | Fonction |
| --- | --- | --- |
| `POST` | `/api/anciens-etudiants/inscription/` | Demande d’inscription avec création du compte inactif et du profil étudiant |
| `GET`, `PATCH` | `/api/anciens-etudiants/me/` | Consultation ou modification du profil étudiant connecté |

Un ancien étudiant ne peut consulter que son propre profil. Les demandes
d’inscription sont soumises à validation avant l’activation du compte.

### Journal d’audit et vérification publique

| Méthode | Route | Fonction |
| --- | --- | --- |
| `GET` | `/api/journal-audit/` | Consultation paginée et filtrable du journal |
| `GET` | `/api/journal-audit/{id}/` | Consultation d’une entrée |
| `GET` | `/api/journal-audit/export/` | Export CSV filtré |
| `GET` | `/api/verification/{code_qr}/` | Vérification publique d’un document officiel par code QR |

Le journal est en lecture seule via son API. L’export est réservé à la permission
`audit.exporter`. La vérification QR retourne les informations d’authenticité,
le numéro officiel, la date de génération et l’état de signature, sans donner
accès aux archives ni aux informations personnelles du demandeur.

## Règles de sécurité

- Les permissions sont attribuées aux rôles, puis les rôles aux comptes; les
  permissions métier ne sont pas affectées individuellement aux utilisateurs.
- Le backend vérifie les permissions même si le frontend masque les écrans non
  autorisés.
- Des contrôles empêchent certains cumuls de tâches : numérisation et contrôle
  qualité, établissement et validation d’une élimination, ou administration
  technique et signature/validation d’élimination.
- L’accès à un document métier exige une permission et peut être limité par les
  rôles autorisés sur le type de document et sur le dossier ou ses dossiers
  parents.
- Les anciens étudiants et utilisateurs externes ne peuvent pas utiliser les
  droits internes pour accéder aux archives.
- Les actions sensibles exposées, notamment les opérations de compte, les
  changements de rôles, les consultations d’audit et les exports, sont inscrites
  au journal.
- Dans l’interface Django Admin, l’audit est en lecture seule et les rôles et
  permissions sont présentés sans gestion directe de leurs affectations métier.

## Limites fonctionnelles

Cette application fournit les comptes, l’authentification, le RBAC, l’audit,
l’inscription des anciens étudiants et la vérification publique d’authenticité.
Elle ne réalise pas à elle seule les opérations de numérisation, de classement,
de paiement, de demande de duplicata ou de gestion des éliminations. Les droits
correspondants sont définis, mais ces parcours nécessitent leurs API et interfaces
métier dans les applications concernées.

## Fichiers principaux

- `backend/apps/accounts/models.py` : modèles utilisateur, rôle, permission,
  profil étudiant et audit.
- `backend/apps/accounts/serializers.py` : validation et représentation des
  données de l’API.
- `backend/apps/accounts/views.py` : endpoints et contrôles d’accès.
- `backend/apps/accounts/urls.py` : routes de l’application.
- `backend/apps/accounts/audit.py` : enregistrement des événements d’audit.
- `backend/apps/accounts/migrations/` : évolution du schéma et catalogue initial
  des rôles et permissions.
- `backend/apps/accounts/tests.py` : tests des parcours d’authentification, de
  gestion, d’audit et des règles d’accès.
