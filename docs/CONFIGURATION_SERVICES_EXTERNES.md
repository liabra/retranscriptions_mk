# Configuration des services externes — A2C Retranscriptions

Ce document s'adresse à la personne qui met la plateforme en service (administratrice, responsable informatique de l'association ou prestataire technique). Aucun identifiant n'est fourni ici : chacun doit être créé par l'association, puis saisi **uniquement** dans les variables d'environnement Railway (jamais dans le code ni dans un fichier commité).

La plateforme fonctionne **sans** Microsoft Graph ni Brevo : l'ajout manuel des audios par fichier, la production, le dépôt des PV (stockés en base), la facturation et les notifications internes sont opérationnels. Chaque service ajoute une capacité.

---

## 1. Variables obligatoires (service backend Railway)

| Variable | Rôle | Comment l'obtenir |
|---|---|---|
| `DATABASE_URL` | Base PostgreSQL | Injectée par le plugin PostgreSQL Railway |
| `SECRET_KEY` | Signature des sessions (32 caractères minimum) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Chiffrement des IBAN et des liens OneDrive | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — **ne jamais la changer** ensuite (les données chiffrées deviendraient illisibles). Conserver une copie dans un coffre-fort de mots de passe. |
| `APP_ENV` | `production` | Active les contrôles stricts (clé longue, DEBUG interdit, stockage local interdit) |
| `ALLOWED_ORIGINS` | Adresse exacte de l'interface | ex. `https://a2c-retranscriptions.up.railway.app` |
| `APP_PUBLIC_URL` | Même adresse, utilisée dans les liens des emails | |
| `AUDIO_STORAGE_BACKEND` | `onedrive` en production | Sans OneDrive configuré, le dépôt d'un **fichier** audio est refusé avec un message clair ; l'ajout par **lien** reste possible |
| `PV_STORAGE_BACKEND` | `database` (défaut) ou `onedrive` | `database` : PV conservés dans PostgreSQL (durable, inclus dans les sauvegardes Railway) |

Service frontend : `VITE_API_URL=https://<adresse-du-backend>/api/v1` (variable de **build**).

Python : le backend est épinglé en 3.12 (`backend/.python-version`).

## 2. Microsoft Graph (OneDrive de l'association)

### 2.1 À confirmer avec le responsable informatique
1. **Type de compte** : Microsoft 365 professionnel / association (Entra ID). Un compte OneDrive *personnel* (outlook.com, hotmail) ne permet pas l'accès applicatif décrit ici.
2. **Emplacement des fichiers** : OneDrive d'un utilisateur de l'association **ou** bibliothèque SharePoint dédiée (recommandé : bibliothèque « A2C Retranscriptions » sur un site SharePoint, plus simple à sécuriser et à partager entre les deux responsables).
3. Les audios doivent se trouver **dans le tenant de l'association**. Un lien de partage provenant du tenant d'un client ne peut pas être lu par l'application : il faut d'abord copier le fichier dans le OneDrive de l'association.

### 2.2 Création de l'application (portail Entra ID)
1. *Entra ID → Inscriptions d'applications → Nouvelle inscription* : nom « A2C Retranscriptions — plateforme », comptes de ce répertoire uniquement, pas d'URI de redirection.
2. *Certificats & secrets → Nouveau secret client* : durée 12 ou 24 mois. **Noter l'échéance** : à renouveler avant expiration (sinon la plateforme affiche « Authentification Microsoft refusée »).
3. *Autorisations d'API → Microsoft Graph → Autorisations d'application* :
   - **Option recommandée (moindre privilège)** : `Sites.Selected`, puis accorder à l'application l'accès en écriture **au seul site SharePoint** A2C (via Graph `POST /sites/{site-id}/permissions` ou PowerShell PnP, à faire par l'administrateur Microsoft).
   - Option simple mais large : `Files.ReadWrite.All` (accès à tous les fichiers du tenant) — à éviter si possible.
   - Pour vérifier les liens de partage saisis manuellement : `Files.Read.All` ou `Sites.Selected` couvrant l'emplacement concerné.
4. *Accorder le consentement administrateur*.

### 2.3 Identifiant du lecteur (`ONEDRIVE_DRIVE_ID`)
Avec l'explorateur Graph ou un script de l'administrateur Microsoft :
- bibliothèque SharePoint : `GET https://graph.microsoft.com/v1.0/sites/{hostname}:/sites/{nom-du-site}:/drives` → champ `id` ;
- OneDrive d'un utilisateur : `GET https://graph.microsoft.com/v1.0/users/{email}/drive` → champ `id`.

### 2.4 Variables
| Variable | Valeur |
|---|---|
| `ONEDRIVE_TENANT_ID` | ID du locataire (Vue d'ensemble Entra ID) |
| `ONEDRIVE_CLIENT_ID` | ID d'application (client) |
| `ONEDRIVE_CLIENT_SECRET` | Valeur du secret client (affichée une seule fois) |
| `ONEDRIVE_DRIVE_ID` | Identifiant du lecteur (2.3) |
| `ONEDRIVE_ROOT_FOLDER` | `A2C Retranscriptions` (dossier racine, créé automatiquement) |
| `ONEDRIVE_INBOX_FOLDER` | Dossier surveillé pour la détection, ex. `A2C Retranscriptions/Nouveaux audios` |
| `AUDIO_STORAGE_BACKEND` | `onedrive` |
| `PV_STORAGE_BACKEND` | `onedrive` pour ranger les PV dans OneDrive, sinon `database` |

Organisation produite automatiquement :
```
A2C Retranscriptions/
  <Client>/
    Audios/                     ← audios déposés via la plateforme
    <Référence du dossier>/
      PV_<référence>_v1_retranscription.docx
      PV_<référence>_v2_corrige_interne.docx …
  Nouveaux audios/              ← dossier surveillé (détection automatique)
```
Les versions ne sont jamais écrasées (`conflictBehavior=fail`).

### 2.5 Détection automatique des nouveaux audios (préparée, désactivée par défaut)
- `ENABLE_SCHEDULER=true` et `GRAPH_SYNC_INTERVAL_MINUTES=15` (par exemple).
- Fonctionnement : requête *delta* Microsoft Graph sur le dossier surveillé ; chaque nouveau fichier audio apparaît dans « Audios reçus → À traiter ». **Aucun dossier n'est créé automatiquement** ; un fichier déjà connu n'est jamais réimporté ; en cas d'erreur, la position de synchronisation n'avance pas et l'erreur est affichée dans l'écran Audios.
- Une seule instance du backend doit avoir `ENABLE_SCHEDULER=true` (les doublons de notifications sont de toute façon bloqués par la base).
- Bouton « Vérifier maintenant » disponible dans l'écran Audios.

### 2.6 Sécurité
- Le jeton Microsoft, le secret et les liens de téléchargement Graph restent côté serveur ; les retranscripteurs reçoivent le fichier en flux via l'API, après vérification de leur attribution active.
- Les liens OneDrive saisis sont chiffrés en base et ne sont jamais renvoyés, même aux responsables.

## 3. Brevo (emails)

1. Créer un compte Brevo au nom de l'association.
2. *Expéditeurs, domaines → Domaines* : authentifier le domaine d'envoi (enregistrements DNS **SPF, DKIM et DMARC** fournis par Brevo, à ajouter chez l'hébergeur du domaine).
3. *Expéditeurs* : créer l'adresse d'envoi (ex. `notifications@<domaine-association>`).
4. *SMTP & API → Clés API* : créer une clé **dédiée** à la plateforme.
5. Variables Railway : `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`.

Comportement : la notification interne est toujours créée ; l'email part en arrière-plan et son statut réel est enregistré (`envoye`, `echec`, `non_configure`). Aucun succès n'est simulé. Chaque utilisateur peut désactiver les emails dans « Mon compte ». Les emails ne contiennent ni montant ni lien de fichier, seulement un lien vers la plateforme.

## 4. Tâches périodiques

`ENABLE_SCHEDULER=true` active, toutes les `SCHEDULER_INTERVAL_MINUTES` : alertes d'échéance proche (48 h) et de retard (retranscripteur + responsables), puis la détection OneDrive si elle est configurée. Les alertes peuvent aussi être lancées manuellement (`POST /api/v1/notifications/alertes/executer`).

## 5. Récapitulatif de mise en service

1. Variables obligatoires (section 1) → déploiement → les migrations s'appliquent automatiquement (le démarrage s'arrête si une migration échoue).
2. Réinitialisation des données de démonstration existantes (voir rapport final, section « Opérations avant production »).
3. Connexion avec les comptes initiaux, changement de mot de passe imposé, correction des emails de connexion dans « Utilisateurs & droits ».
4. Puis, quand l'association est prête : Microsoft Graph (section 2), Brevo (section 3), planificateur (section 4).
