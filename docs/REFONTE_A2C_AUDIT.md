# Refonte A2C Retranscriptions — Audit et cadrage (Phase 0)

> Document de référence initial de la refonte. Rédigé le 2026-11-16 à partir de la lecture du **code réellement présent** (branche `main`, commit `aab1b26`), pas de la documentation.
> Aucun comportement applicatif, aucun fichier existant et aucune donnée n'ont été modifiés pour produire ce document.

## Périmètre et limites de l'audit

| Vérifié | Non vérifié (et pourquoi) |
|---|---|
| Tout le backend (`backend/app`, 12 modules d'API, modèles, services, schémas, 4 migrations, seeds, `start.sh`, config Railway) | **Base et données de production** : aucun accès (Railway CLI non connectée, aucun `DATABASE_URL` fourni). Interdit de toute façon par le cadre de la phase. |
| Frontend (routes, services API, pages dashboard / prestataire / dossiers, auth) | Comportement à l'exécution : l'application n'a pas été lancée. |
| Dépendances déclarées (`requirements.txt`, `package.json`) | Vulnérabilités de dépendances : `pip-audit` / `npm audit` **non exécutés** ; les points signalés au §6 viennent de ma connaissance des CVE et sont à confirmer. |
| Historique git (47 commits) : aucun `.env`, secret ou dump versionné | `docs/Cadrage_Retranscriptions_v2.pdf` cité par le README : **absent** (`docs/` et `database/` sont vides). |

**Tests : aucun.** Ni `tests/`, ni fichier de test, ni CI (`.github` absent). `pytest` est dans `requirements.txt` mais inutilisé. Aucun test n'a donc pu être exécuté.

---

## 1. État réel du projet

**Stack** : FastAPI 0.115 / SQLAlchemy 2 / Alembic / PostgreSQL ; React 19 + TypeScript + Vite 5 + axios ; déploiement Railway (Nixpacks, deux services : `backend`, `frontend` servi par `npx serve`). ~12 100 lignes de code applicatif.

**Vocabulaire** : l'objet central s'appelle `Dossier` (table `dossiers`) ; la refonte parle de « mission ». Le même mot « missions » désigne aujourd'hui, dans l'API (`missions.py`) et l'UI (`MissionsPage`), l'espace prestataire. Source de confusion à lever (§8).

**Modèle de données actuel** (16 tables) :

| Domaine | Tables |
|---|---|
| Accès | `users` (7 rôles : administratrice, coordinatrice, retranscripteur, correcteur, comptabilite, lecture_seule, client) |
| Métier | `clients`, `prestataires`, `dossiers` (17 statuts), `affectations` (retranscripteur/correcteur, 1 de chaque max par dossier), `fichiers_dossier`, `incidents_qualite` (modèle présent, **aucune route**) |
| Tarification | `grilles_tarifaires` (versionnées, datées), `regles_tarifaires`, `calculs_tarifaires` (versionnés, avec snapshot des règles appliquées) |
| Finance | `factures_clients`, `paiements_prestataires` |
| Traçabilité | `journal_activites` |

**Liens fragiles** : le compte (`users`) n'est relié ni au `prestataires` ni au `clients` par une clé étrangère, mais **par égalité d'e-mail** (`Prestataire.email == user.email`, `Client.email_contact == user.email`) — répété dans ≥ 8 endroits, avec `.first()` sans contrainte d'unicité.

**Déploiement** : `start.sh` lance `alembic upgrade head`, `seed.py`, `seed_grilles.py` à **chaque démarrage**, en continuant même si une étape échoue.

## 2. Fonctionnalités opérationnelles (d'après le code)

- Authentification JWT (bcrypt, expiration 8 h), création/édition d'utilisateurs par l'administratrice, IBAN prestataire chiffré (Fernet) lisible uniquement par l'administratrice.
- CRUD clients, prestataires, dossiers ; génération de référence `ANNÉE-TYPE-NNNN` ; détection d'urgence (< 2 jours).
- Machine de transitions de statuts dossier (`services/transition.py`) pour la route manuelle `/transition`.
- Affectation retranscripteur + correcteur, calcul automatique de l'échéance selon la durée audio (7 / 18 / 25 jours), e-mail au prestataire, compteur de charge.
- **Moteur tarifaire** (`services/pricing/engine.py`, `calcul_service.py`) : grilles CLIENT / RETRANSCRIPTEUR / CORRECTEUR / URGENCE / SNP / SPECIAL, règles par priorité, grilles spécifiques client/prestataire > globale, calculs versionnés avec détail des règles, ajustement motivé, marge brute. Grilles réelles France (forfaits par tranche) et Togo seedées.
- Facturation : génération (numéro `FAC-ANNÉE-NNNN`), TVA optionnelle, HTML/PDF (WeasyPrint), suivi non payée/partielle/soldée, création automatique des paiements prestataires.
- Paiements prestataires : génération, ajustement motivé, statut à payer/validé/payé, passage automatique du dossier à `prestataires_payes`.
- Upload prestataire/client (liste blanche d'extensions, taille max, nom disque = UUID), notification e-mail admin (SMTP optionnel, non bloquant).
- Journal d'activité (JSONB) sur la plupart des actions.
- UI : dashboard, liste/détail/création dossier, clients, prestataires, grilles (+ détail/règles), utilisateurs, aide, espace prestataire en cartes de mission, espace client.

## 3. Fonctionnalités incomplètes ou défectueuses

**Bugs confirmés à la lecture du code**

| # | Où | Problème |
|---|---|---|
| B1 | `factures.py:148` | `payeur` n'est **jamais défini** dans `generer_facture` → `NameError` *après* `db.commit()` : la facture et les paiements prestataires sont créés, mais l'appel renvoie une erreur 500 et l'e-mail client n'est jamais envoyé. L'interface croit à un échec ; un second essai est bloqué (« facture existe déjà »). |
| B2 | `auth.py:55-60` | `db.commit()` puis `log_action()` (qui ne fait que `flush`) : l'entrée de journal de **connexion n'est jamais committée** (perdue à la fermeture de session). Le journal d'authentification est vide. |
| B3 | `dossiers.py:166-195` | La suppression d'un dossier **supprime son journal** (`JournalActivite ... .delete()`), contredisant « journal immuable » (README, `models/journal.py`). |
| B4 | `affectations.py`, `calculs.py:98`, `factures.py:~75`, `paiements.py` | Les transitions de statut automatiques **contournent** `transition.py` (`dossier.statut = ...` directement) : on peut passer à `ENVOYE` via la validation d'un calcul depuis `EN_RETRANSCRIPTION`, ou à `FACTURE` depuis n'importe quel statut. La machine d'états n'est donc pas une garantie. |
| B5 | `calcul_service.py:63-84,129` | Calcul « auto-validé » (`DEFINITIF`) dès que le montant égale le forfait A2C : une validation sans action humaine. Et si la grille renvoie 0 €, le code **substitue un forfait codé en dur** (`_forfait_a2c`, dupliqué dans `calculs.py:21` et `calcul_service.py`) — c'est un tarif inventé silencieusement, contraire à « ne jamais inventer de tarif ». |
| B6 | `affectations.py:~230` | `except Exception: pass` autour de l'auto-calcul : une erreur de calcul est avalée sans trace. |
| B7 | `prestataire.charge_actuelle` | Incrémentée à l'affectation, décrémentée **seulement** au rejet — jamais à la livraison/validation. La charge dérive vers le haut ; inutilisable pour l'attribution assistée. |
| B8 | `prestataire.note_qualite` | Valeur fixe 1.00, jamais calculée. `incidents_qualite` sans route. Aucune donnée de performance n'existe. |
| B9 | `fichier.py` vs migration 0003 | Le modèle déclare `url_onedrive` `nullable=False`, la migration 0003 le passe à `nullable=True` (dérive modèle/base). |
| B10 | migration 0004 | `ALTER TYPE roleenum ADD VALUE 'client'` : les colonnes sont créées en `Text` (migration 0001), il n'existe pas de type `roleenum` si le schéma vient des migrations → la migration échoue sur une base neuve (et l'échec est masqué par `start.sh`). À vérifier sur la base réelle : le schéma de production vient peut-être de `create_all`, ce qui expliquerait l'écart. |
| B11 | `DossierDetailPage.tsx` | 1 243 lignes, tout le cycle dans un seul composant. |
| B12 | `DashboardPage.tsx` | Indicateurs calculés **côté navigateur** sur `limit=100` dossiers : faux au-delà de 100 dossiers ; « En retard » ne filtre rien au clic ; ni audios, ni facturation, ni paiements. |
| B13 | `generate_reference`, `_generate_numero_facture` | Numérotation par `COUNT()+1` : doublons possibles en concurrence, et un numéro de **facture** peut se recycler après suppression (`DELETE /factures/{id}`), ce qui est incompatible avec une numérotation comptable continue. |

**Incomplet par rapport au cadrage de la refonte**

Absents du code : mode B Graph (détection), Graph en lecture/téléchargement, livrables DOCX contrôlés, versions de livraison, attribution assistée, notifications en base, indicateurs de performance, tableau de bord métier demandé, séparation des trois statuts, archivage effectif (le champ `archive_snapshot` existe mais n'est jamais écrit), paiement client (hors table `factures_clients.statut_paiement` : pas de montants encaissés ni de dates).

**Microsoft Graph existant** (`services/onedrive.py`, 86 lignes) : uniquement `upload_file` (client credentials, `urllib`, sans bibliothèque). Pas de lecture, pas de liste, pas de delta, pas de mise en cache du jeton (un jeton demandé à chaque upload), pas de retry, pas de pagination, échec = `None` silencieux avec **repli sur le disque local**. **Rien de réutilisable pour le mode B** hormis le principe d'authentification.

## 4. Éléments à conserver

- **Moteur tarifaire** et ses modèles (`grilles`, `regles`, `calculs`) : conception saine (versionné, détaillé, snapshot des règles). À durcir (§8.F), pas à réécrire.
- **Grilles seedées** France et Togo, `seed_grilles.py` (idempotent).
- Calculs versionnés, ajustement motivé, marge brute.
- Chiffrement IBAN + accès administratrice seule.
- Journal d'activité (modèle + service) — à corriger (B2, B3), pas à remplacer.
- Machine de transitions : bon squelette, à refondre en 3 axes (§9) et à rendre **obligatoire** (B4).
- Hash bcrypt, JWT, pattern `require_*` de `core/deps.py`, schémas Pydantic séparés des modèles (protège du mass-assignment sur la plupart des routes).
- Schéma `clients` / `prestataires` / `affectations` / `factures_clients` / `paiements_prestataires` (extension plutôt que remplacement).
- Services e-mail (non bloquants, mode dégradé sans SMTP) — à brancher sur le futur système de notifications.
- Identité visuelle A2C, composants UI (`StatusBadge`, `TarifForfait`, cartes de mission prestataire).
- Configuration Railway (healthcheck `/health`, deux services).

## 5. Éléments à simplifier

| Aujourd'hui | Cible |
|---|---|
| 17 statuts mélangeant production, facturation et paiement (`facture`, `paye_entrant`, `prestataires_payes` dans le même enum que `en_correction`) | 3 statuts indépendants (§9) |
| « Dossier » / « mission » / « affectation » / « fichier » mêlés ; page Missions = espace prestataire | Vocabulaire unique (§8.A) |
| Qualification en plusieurs étapes (`recu` → `en_qualification` → `estime` → `a_attribuer`) | Une seule étape « à qualifier », un seul formulaire |
| `calcul_en_cours`, `en_mise_en_forme`, `a_valider`, `envoye` | Remplacés par le cycle livraison → contrôle → validation |
| Deux rôles prestataire (retranscripteur/correcteur) imposant 2 affectations | Une affectation principale ; correcteur = affectation optionnelle liée à la même mission |
| Compte ↔ prestataire par e-mail | Clé étrangère explicite |
| Upload libre + liens manuels (`POST /dossiers/{id}/fichiers` avec URL arbitraire) | Deux entrées documentaires distinctes : audio source (Graph) et livraison DOCX (stockage privé) |
| Forfait codé en dur ×3 | Une seule source : les grilles |
| Écrans : 12 pages, détail dossier de 1 243 lignes | ~8 écrans admin orientés tâche (§8.B) |
| Rôles : 7 | Voir §7 — `lecture_seule`/`comptabilite` conservés, `coordinatrice` à confirmer |

---

## 6. Risques de sécurité

Classés par gravité. Références `fichier:ligne` du code actuel. **Les points S1 à S4 contredisent directement l'architecture documentaire exigée par le cadrage** et doivent être traités avant toute nouvelle fonctionnalité.

### Critique

| # | Constat | Référence | Correctif cible |
|---|---|---|---|
| **S1** | **Le lien OneDrive est donné aux prestataires.** `FichierOut` renvoie `url_onedrive` ; `list_fichiers`, `fichiers_mission` le renvoient ; `MesDossiersPage.tsx:103` l'affiche en lien cliquable ; `download` fait un `RedirectResponse` vers cette URL (le lien fuit dans l'en-tête `Location`). | `schemas/fichier.py`, `fichiers.py:160`, `missions.py:893`, `upload.py:507-510` | Ne plus jamais renvoyer d'URL ; flux binaire proxifié par le backend ; `FichierOut` sans champ de localisation. |
| **S2** | **IDOR téléchargement/listing.** `download_fichier` laisse un prestataire récupérer **tout** fichier `AUDIO_BRUT` de **n'importe quel** dossier (aucun contrôle d'affectation, ligne 499). `list_fichiers` ne contrôle pas l'affectation pour les prestataires (il filtre seulement le type). | `upload.py:497-500`, `fichiers.py:171-173` | Autorisation par affectation active, contrôlée à chaque téléchargement (exigence §3 du cadrage). |
| **S3** | **Écriture sans contrôle de rôle.** `POST /dossiers/{id}/fichiers` : tout utilisateur authentifié (client, lecture seule…) peut attacher une URL arbitraire `http(s)://` à n'importe quel dossier, ensuite servie aux prestataires (hameçonnage, SSRF indirect si un jour suivi côté serveur). `PATCH /fichiers/{id}` : l'auteur peut changer statut/version. | `fichiers.py:184-253`, `schemas/fichier.py` | Route supprimée ou réservée admin ; remplacée par Graph (item id) et livraisons contrôlées. |
| **S4** | **Fuite des montants vers les prestataires/clients.** `GET /dossiers/{id}/calculs`, `/calculs/{id}`, `/dossiers/{id}/facture`, `/factures/{id}` (+ `/html`, `/pdf`), `/dossiers/{id}/paiements-prestataires`, `/dossiers/{id}/affectations`, `/dossiers/{id}/journal` n'exigent que `CurrentUser` — **tout rôle**, sans contrôle d'appartenance. Un prestataire peut lire le montant client, la marge, les montants des autres prestataires, les factures de tous les clients. Contredit « un prestataire ne voit jamais le montant client ». | `calculs.py:82,93`, `factures.py:163,172,268,280`, `paiements.py:114`, `affectations.py:77`, `journal_api.py:16` | `require_roles(admin, coordinatrice, comptabilité)` par défaut ; schémas de sortie dédiés « prestataire » sans montants. |
| **S5** | **Un client peut lire n'importe quel dossier.** `_check_access` ne traite que les prestataires ; `GET /dossiers/{id}` ne contrôle pas le rôle `client`. `DossierOut` expose aussi `notes_internes`, `criteres_tarif`, `payeur_id` à tout rôle autorisé (donc aux prestataires). | `dossiers.py:19-35,134` | Contrôle de propriété pour `client` ; deux schémas de sortie (admin / prestataire). |

### Élevé

| # | Constat | Référence |
|---|---|---|
| S6 | Un prestataire peut, via `PATCH /affectations/{id}`, modifier librement `date_limite_rendu`, `date_rendu_effectif`, `commentaire` (seul `statut` est restreint) : il peut repousser sa propre échéance (mass assignment partiel). Pas de contrôle de transition sur `statut` (re-livrer à l'infini). | `affectations.py:166-200`, `schemas/affectation.py` |
| S7 | Fichiers prestataires non validés : seule l'extension est contrôlée (`.doc/.docx/.pdf/.odt/.txt`) ; pas de type réel, pas de contenu, `Content-Type` ignoré. Fichier entier lu en mémoire (jusqu'à 500 Mo). Appels `urllib` bloquants dans un `async def` (bloque la boucle d'événements). | `upload.py:287-291,367,394` |
| S8 | **Repli silencieux vers le disque local** si OneDrive échoue (`_save_file`) : les fichiers livrés se retrouvent sur le disque éphémère Railway (perdus au redéploiement) sans alerte ; et le chemin local est stocké dans `url_onedrive`. Contraire à l'exigence « pas de stockage temporaire sur le disque local Railway ». | `upload.py:308-322` |
| S9 | Le jeton OneDrive en `client_credentials` sur tout un Drive (`ONEDRIVE_DRIVE_ID`) : permission application large (probablement `Files.ReadWrite.All`) ; les audios clients, les livrables prestataires et les dossiers `Admin/` cohabitent dans le même drive. | `services/onedrive.py`, `config.py` |
| S10 | Injection HTML dans les e-mails admin (`commentaire`, `nom_fichier`, `presta_nom` insérés sans échappement) et dans la facture HTML/PDF (`payeur.nom`, `dossier.titre` non échappés ; WeasyPrint peut suivre des URL externes → SSRF/lecture de ressources à la génération PDF). | `email.py:96-160`, `factures.py:179-262` |
| S11 | Dépendances : `python-jose 3.3.0` (CVE connues de 2024, projet peu maintenu → migrer vers PyJWT), `python-multipart 0.0.17` (CVE de DoS corrigée en 0.0.18), `weasyprint 62.3`, `fastapi 0.115.5`. **À confirmer par `pip-audit`.** `psycopg2-binary` **et** `asyncpg` sont déclarés (asyncpg inutilisé). |
| S12 | Aucune limitation de débit ni verrouillage sur `/auth/login` ; aucune politique de mot de passe (`UserCreate.password: str`) ; pas de révocation de jeton ; jeton dans `localStorage` (exposé en cas de XSS — aucun `dangerouslySetInnerHTML` trouvé, ce qui limite le risque aujourd'hui). |
| S13 | `seed.py` crée `admin@retranscriptions.local` / `ChangeMe123!` à chaque démarrage tant qu'aucune administratrice n'existe, et **imprime le mot de passe** dans les logs. Si l'unique administratrice est désactivée/supprimée, le compte par défaut est recréé au redémarrage suivant. |
| S14 | `start.sh` écrit dans les logs les 30 premiers caractères de `DATABASE_URL` (`postgresql://utilisateur:motde...`) : fuite partielle de l'identifiant et du début du mot de passe. |

### Moyen

- S15 : `DEBUG` vaut `True` **par défaut** (`config.py`) → `/docs` et `/redoc` publics si la variable est absente en production. Aucune validation de longueur/entropie de `SECRET_KEY`.
- S16 : Pas d'en-têtes de sécurité (CSP, HSTS, X-Content-Type-Options) ; frontend servi par `npx serve` sans configuration d'en-têtes. CORS : `allow_methods/headers=["*"]` avec credentials (origines bornées, acceptable mais à resserrer).
- S17 : `DELETE /dossiers/{id}` et `DELETE /factures/{id}` : suppression physique par la coordinatrice (journal compris, B3). Les opérations financières ne doivent jamais être supprimables (avoir/annulation).
- S18 : `PATCH /grilles/{id}` et `/regles/{id}` modifient **en place** (valeurs, dates) : l'historique de tarif n'est conservé que dans le journal ; un recalcul ultérieur d'un dossier ancien utilise la grille du jour (`date.today()` dans `_get_active_grille`) → modification rétroactive possible d'un montant non figé.
- S19 : `update_paiement` : un paiement `paye` reste modifiable (montant, ajustement) ; aucune machine d'états ; `FacturePaiementUpdate` accepte n'importe quel statut dans les deux sens (une facture soldée peut repasser « non payée »).
- S20 : IP source du journal renseignée uniquement à la création de dossier ; `request.client.host` derrière le proxy Railway renverrait l'IP du proxy sans `--proxy-headers`.
- S21 : Rôle `comptabilite`/`lecture_seule` : accès en lecture à tout via les routes `CurrentUser` (cf. S4) alors que le principe de moindre privilège voudrait des périmètres explicites.

### Points positifs à préserver

Aucun secret versionné ; `.gitignore` couvre `.env`, `uploads/`, audio ; requêtes SQLAlchemy paramétrées (aucune concaténation SQL trouvée) ; noms de fichiers disque = UUID + extension (pas de path traversal à l'écriture) ; IBAN chiffré et jamais renvoyé par l'API standard ; bcrypt ; messages de login non discriminants ; frontend sans `dangerouslySetInnerHTML`.

---

## 7. Architecture fonctionnelle cible

### 7.1 Principes

1. **Une mission = un dossier existant**, on conserve la table `dossiers` (aucun renommage en base) ; le vocabulaire « mission » est adopté côté API/UI.
2. **Trois statuts indépendants** par mission : production, facturation, paiement prestataire.
3. **Autorisation par ressource** : toute lecture/écriture passe par une dépendance qui vérifie rôle **et** appartenance (affectation active, client propriétaire).
4. **Deux types de fichiers, deux stockages** :
   - *Audio source* : reste dans OneDrive ; la base ne stocke que `drive_id` + `item_id` (+ métadonnées), jamais un lien utilisable par un tiers ; téléchargement en flux via le backend.
   - *Livraison DOCX* : stockage objet privé indépendant (S3-compatible), clés opaques, jamais d'URL publique permanente.
5. **Les montants n'existent que dans des schémas « admin/finance »** ; les schémas « prestataire » sont des modèles distincts, sans champ financier client.

### 7.2 Rôles

| Rôle | Périmètre |
|---|---|
| Administratrice | Tout. |
| Coordinatrice | Audios, missions, attribution, contrôle des livraisons, prestataires. **Sans** IBAN, tarifs, facturation, paiements (à confirmer — aujourd'hui elle y a accès). |
| Comptabilité | Facturation, encaissements, paiements prestataires, lecture des missions concernées. |
| Lecture seule | Lecture des missions, **sans** montants. |
| Retranscripteur / Correcteur | Espace prestataire uniquement. Compte lié à un `prestataire` par FK. |
| Client | **Gelé** : espace actuel conservé sans extension (le cadrage ne prévoit ni espace client ni cahier des charges externe). À confirmer. |

### 7.3 Modules

| Module | Contenu |
|---|---|
| Audios | Entrée manuelle (A) + file de détection (B) + états (nouveau, qualifié, ignoré, indisponible, erreur). |
| Missions | Qualification, échéances, caractéristiques, historique. |
| Attribution | Suggestions classées + choix libre + validation humaine. |
| Livraisons | Dépôt DOCX, contrôles automatiques, versions, retours/corrections. |
| Finance | Calcul (moteur existant), facture, encaissement, paiement prestataire. |
| Qualité | Indicateurs prestataires (admin seulement), incidents. |
| Notifications | In-app + e-mail configurable, dédoublonnées. |
| Archives | Missions soldées, snapshot immuable. |

---

## 8. Organisation des écrans

### A. Vocabulaire
« Audio » (fichier source) → « Mission » (dossier qualifié) → « Livraison » (dépôt DOCX versionné). « Affectation » reste un terme interne ; l'UI parle d'« attribution ».

### B. Espace Administration (navigation)

1. **Tableau de bord** — 12 tuiles (§8.D).
2. **Audios** — onglet *Nouveaux à traiter* (Graph) / *Ajout manuel* / *Traités*. Action : « Créer la mission » (pré-remplie).
3. **Missions** — liste filtrable par les trois statuts ; fiche mission en onglets (Résumé · Audio · Attribution · Livraisons · Finance · Historique), à la place du composant de 1 243 lignes.
4. **Attribution** — vue « missions à attribuer » avec, par mission, le panneau de suggestions (§10, lot 5).
5. **Livraisons** — file « à contrôler » avec rapport de conformité lisible.
6. **Finance** — Factures à établir · En attente de règlement · Paiements prestataires à effectuer · Effectués.
7. **Clients & instances** · **Prestataires** (+ qualité) · **Tarifs** (grilles existantes, calcul expliqué) · **Utilisateurs** · **Archives** · **Paramètres** (Graph, e-mails, seuils).

### C. Espace Prestataire
Écran unique « Mes missions » en cartes (conserver la refonte récente) : mission, échéance, téléchargement audio, dépôt, retours à traiter, historique de ses livraisons. **Aucun** montant client, aucune note de performance, aucun lien externe.

### D. Tableau de bord
Chaque tuile = un compteur **calculé côté serveur** (`GET /dashboard/summary`, une requête agrégée) et un lien vers la liste filtrée correspondante : nouveaux audios · missions à qualifier · à attribuer · en cours · en retard · livraisons reçues · à contrôler · validées · factures à établir · en attente de règlement · paiements prestataires à effectuer · effectués.

---

## 9. Workflow cible

### 9.1 Statut de production (`statut_production`)

```
[Audio] nouveau → (qualification admin) → a_qualifier → a_attribuer → attribuee → en_cours
   → livree → en_controle ─┬─ correction_demandee → (retour prestataire) → livree …
                           └─ validee → archivee
   (transversaux : bloquee, annulee)
```

| Étape du cadrage | Représentation |
|---|---|
| 1 Audio reçu | `audio_sources.statut = nouveau` (hors mission) |
| 2 Mission qualifiée | création de la mission, `a_qualifier` → `a_attribuer` |
| 3 À attribuer | `a_attribuer` |
| 4 Attribution validée | `attribuee` (action humaine obligatoire) |
| 5 Retranscription en cours | `en_cours` (au premier téléchargement/ouverture, ou par action prestataire) |
| 6 Livraison reçue | `livree` (dépôt DOCX réussi) |
| 7 Contrôle | `en_controle` (rapport automatique + revue admin) |
| 8 Correction éventuelle | `correction_demandee` → nouvelle version → `livree` |
| 9 Validation finale | `validee` |
| 13 Archivage | `archivee` (snapshot immuable) |

### 9.2 Statut de facturation (`statut_facturation`)
`non_applicable` → `a_etablir` (déclenché à `validee`) → `emise` → `partiellement_reglee` → `reglee` ; `annulee` uniquement par **avoir** (jamais de suppression).
Étapes 10 (facturation client) et 11 (encaissement).

### 9.3 Statut de paiement prestataire (`statut_paiement_presta`, par affectation)
`non_du` → `a_payer` (mission validée) → `valide` → `paye`.
Étape 12. Le paiement du prestataire est **indépendant** de l'encaissement client (règle à confirmer : bloquer ou non le paiement tant que la facture n'est pas réglée).

### 9.4 Règles de transition
- Table de transitions unique, **appelée par tout code qui change un statut** (suppression des `dossier.statut = ...` directs, B4).
- Chaque transition : rôle autorisé, pré-conditions (ex. `validee` exige une livraison dont le contrôle est conforme **ou** une dérogation admin motivée), entrée de journal, événement de notification.
- Une mission `archivee` ou une facture `emise` n'est plus modifiable ; correction par document d'ajustement.

---

## 10. Plan de développement priorisé

Principe : **sécuriser d'abord, ne rien casser en production, avancer par lots livrables séparément**, chacun avec ses tests (il n'y en a aucun aujourd'hui).

| Lot | Contenu | Pourquoi dans cet ordre | Taille |
|---|---|---|---|
| **0 — Filet** | Suite de tests (pytest + base PostgreSQL de test) : auth, matrice rôle × route, moteur tarifaire (grilles France/Togo), transitions. CI GitHub (tests + `pip-audit` + `npm audit` + `tsc`). | Aucun test aujourd'hui : refondre sans filet est le plus gros risque. | S |
| **1 — Sécurité** | Corriger S1–S6, S10, S13–S15 ; B1–B3 ; mise à niveau dépendances (S11) ; limitation de débit login. Aucun changement fonctionnel visible hors correction. | Les failles S1–S5 contredisent le cadrage. À livrer **avant** toute nouvelle fonction. | M |
| **2 — Fondations de données** | Lien compte↔prestataire/client par FK ; trois statuts + table de transitions appliquée partout ; tables `audio_sources`, `livraisons`, `notifications` ; schémas de sortie séparés admin/prestataire. Migrations additives uniquement. | Prérequis des lots suivants. | M |
| **3 — Audios, mode A** | Création de mission avec lien OneDrive privé, vérification d'accès Graph (lecture seule, `driveItem`), stockage `drive_id`/`item_id`, flux de téléchargement proxifié et contrôlé par affectation. | Premier flux complet ; valide la dépendance Graph. | M |
| **4 — Livraisons DOCX** | Stockage objet privé, contrôle DOCX (§12), versions, rapport admin, remplacement/correction ; suppression du repli disque local. | Cœur du produit documentaire. | L |
| **5 — Attribution assistée** | Calcul des indicateurs (qualité, délais, régularité, spécialisation, charge réelle recalculée, disponibilité), panneau de suggestions, validation humaine obligatoire, indicateurs invisibles aux prestataires. | Dépend des livraisons (lot 4) pour avoir des données. | M |
| **6 — Audios, mode B** | Détection Graph par *delta query*, file « nouveaux audios », anti-doublon, reprise sur erreur. | Indépendant du mode A, plus risqué (dépendances Azure). | L |
| **7 — Tableau de bord & écrans** | Endpoint d'agrégats serveur, navigation §8, fiche mission en onglets, espace prestataire finalisé. | S'appuie sur les statuts du lot 2. | M |
| **8 — Finance** | Facturation par mission validée, encaissements (montants/dates), paiements prestataires sur trois statuts, avoirs, numérotation sans trou, calcul expliqué. | Après stabilisation du workflow. | M |
| **9 — Notifications** | In-app, e-mails configurables, dédoublonnage, alertes de retard (tâche planifiée). | Consomme les événements des lots précédents. | M |
| **10 — Archives & finition** | Archivage avec snapshot, reprise des données historiques, retrait de l'ancien statut. | Dernier : suppression du code obsolète après bascule. | S |

Livraison progressive : chaque lot est déployable seul ; ancien et nouveau statut **coexistent** jusqu'au lot 10.

---

## 11. Migrations nécessaires

Toutes **additives** (nouvelles tables/colonnes, jamais de `DROP`/`ALTER` destructif avant le lot 10), idempotentes, testées sur une **copie** de la base de production.

| Migration | Contenu |
|---|---|
| M0 | **Réconciliation de l'existant** : confronter `alembic current` en production au schéma réel (B9, B10 : `roleenum`, `url_onedrive`) ; documenter les écarts avant toute nouvelle migration. |
| M1 | `users.prestataire_id` (FK, unique, nullable) et `users.client_id` (FK, nullable), remplies par correspondance d'e-mail **avec rapport des ambiguïtés** (doublons d'e-mail) à valider manuellement. |
| M2 | `dossiers.statut_production`, `statut_facturation` (colonnes + enums), peuplées par table de correspondance depuis `statut` ; `statut` conservé (lecture) jusqu'au lot 10. |
| M3 | `audio_sources` : `id`, `mode` (manuel/graph), `drive_id`, `item_id`, `nom`, `taille`, `mime`, `duree_s`, `etag`/`ctag`, `detecte_le`, `statut`, `dossier_id`, `client_id`, `traite_par_id` ; **unicité (`drive_id`, `item_id`)** (anti-doublon). Lien chiffré éventuel (mode A) pour traçabilité, jamais exposé. |
| M4 | `graph_sync_state` : `delta_link`, `dernier_sync`, `dernier_succes`, `dernière_erreur`, compteur d'échecs. |
| M5 | `livraisons` : `affectation_id`, `version`, `cle_stockage`, `sha256`, `taille`, `nom_original`, `depose_par_user_id`, `depose_le`, `rapport_controle` (JSONB), `conforme` (bool), `statut_revue`, `commentaire_revue`, `remplace_livraison_id`. Unicité (`affectation_id`, `version`). |
| M6 | `notifications` (+ `dedup_key` unique, `lu_le`) et `preferences_notification`. |
| M7 | Finance : `encaissements` (facture, montant, date, mode), `avoirs`, séquence PostgreSQL pour la numérotation des factures, `paiements_prestataires` : colonnes de statut alignées. |
| M8 | Indicateurs : `indicateurs_prestataires` (snapshot périodique, accès admin) ; recalcul de `charge_actuelle` depuis les affectations. |
| M9 | Grilles : contrainte « règle utilisée par un calcul définitif = immuable » (nouvelle version obligatoire) ; ajout, dans `calculs_tarifaires`, des valeurs de grille effectivement appliquées (déjà partiellement dans `regles_appliquees`). |
| M10 | Migration des fichiers historiques : inventaire `fichiers_dossier` (URL OneDrive, chemins locaux), rattachement à `audio_sources`/`livraisons` ; rapport des fichiers locaux **introuvables**. |

`start.sh` : séparer migration et démarrage (étape de déploiement dédiée), **échouer** si la migration échoue, retirer le seed du démarrage.

---

## 12. Dépendances externes

| Dépendance | Usage | État / question ouverte |
|---|---|---|
| **Microsoft Entra ID (Azure) — inscription d'application** | Graph (modes A et B) | Existante pour l'upload ; permissions exactes **inconnues**. Cible : `Sites.Selected` ou `Files.Read.All` en lecture limitée au dossier surveillé, secret en variable d'environnement, rotation planifiée. |
| **Microsoft Graph** | Lecture `driveItem`, téléchargement `/content`, `delta` ; abonnements webhook (optionnels) | Mode B par *delta query* planifiée (robuste, sans URL publique) ; webhooks seulement comme accélérateur. Gestion du 429 (`Retry-After`), renouvellement de jeton, `resyncRequired` du delta. |
| **Stockage objet privé** | Livrables DOCX | Choix à faire : Railway Bucket (si disponible sur le plan) ou S3-compatible (S3, R2…). URL signées de courte durée générées après autorisation, ou flux via le backend. Chiffrement au repos, sauvegarde. |
| **SMTP / service d'e-mail** | Notifications | Facultatif aujourd'hui ; cible : fournisseur transactionnel avec SPF/DKIM. |
| **Bibliothèques Python à examiner** (SECURITY.md : examen avant introduction) | `python-docx` (lecture DOCX), `lxml` défensif ou `defusedxml` (XML), `PyJWT` (remplace `python-jose`), `boto3` ou équivalent S3, `slowapi` (limitation de débit), `msal` (optionnel : jetons Graph avec cache) | Aucune ajoutée à ce stade. |
| **Planificateur** | Delta Graph, alertes de retard, indicateurs | Service/cron Railway ou thread interne ; à décider (éviter une tâche par réplique). |

**Contrôle DOCX (spécification)** — `.docx` = archive ZIP OOXML. Vérifier : signature ZIP (`PK`) et type réel ≠ extension ; limites anti « zip bomb » (taille décompressée, nombre d'entrées, ratio) ; structure (`[Content_Types].xml`, `word/document.xml`) ; refus des macros (`vbaProject.bin`, `.docm`), objets OLE embarqués et relations externes ; ouverture réelle par `python-docx` ; présence de texte non vide ; **police** et **taille** résolues par héritage (run → style de paragraphe → styles par défaut `docDefaults` → thème), pour les attributs `ascii/hAnsi/cs/eastAsia` ; taille corps = 12 pt (`w:sz` = 24) ; signalement des runs, en-têtes, pieds de page et tableaux non conformes avec **localisation** (paragraphe/page approximative). Résultat structuré (JSONB) : conforme / avertissements / non-conformités bloquantes. Une non-conformité ne supprime pas le dépôt : elle le marque et alerte l'administratrice. Définir en amont ce qui est « corps du texte » (titres, notes de bas de page, numéros de page) pour éviter les faux positifs.

## 13. Précautions de production

1. **Aucune migration sans copie.** Restaurer une sauvegarde récente de la base dans un environnement de recette, y jouer les migrations, comparer.
2. **Sauvegarde vérifiée** (restauration testée) avant chaque lot touchant au schéma ; plan de retour arrière écrit par migration.
3. **Environnement de recette Railway** séparé (base, stockage, application Azure de test), jamais le drive réel du client.
4. **Migrations additives** et déploiement en deux temps (schéma, puis code), ancien/nouveau statut en parallèle (§10).
5. **Fichiers existants** : inventorier ceux stockés sur disque local Railway (déjà potentiellement perdus), ceux sur OneDrive ; aucune suppression avant rapprochement (M10).
6. **Secrets** : rotation de `SECRET_KEY` (invalide les sessions, à planifier), `ENCRYPTION_KEY` **ne jamais changer** sans rechiffrement des IBAN ; mot de passe administratrice par défaut à changer immédiatement (S13) ; vérifier ce que contiennent déjà les logs Railway (S13, S14) et les purger/faire tourner si besoin.
7. **Finance** : aucune modification de facture émise, de calcul validé, de paiement effectué ; les nouveaux lots ne recalculent jamais l'historique ; contrôle de non-régression sur un échantillon de dossiers réels (montants avant/après identiques).
8. **Retrait des suppressions physiques** (dossier, facture) avant mise en production des nouveaux statuts.
9. **Observabilité** : journalisation structurée sans donnée personnelle, alertes sur échec de synchronisation Graph, de migration, d'envoi d'e-mail ; `/health` étendu (base + stockage).
10. **Données personnelles** : les enregistrements concernent des instances représentatives du personnel (confidentialité forte) et des IBAN : prévoir durées de conservation, droit d'accès/effacement, registre de traitement (RGPD), hébergement UE du stockage et de la base à vérifier.
11. **Bascule** : période de coexistence, formation de l'administratrice, retour arrière possible tant que le lot 10 n'est pas exécuté.

---

## Décisions retenues dans ce cadrage

1. Conserver la table `dossiers` (vocabulaire « mission » côté API/UI) — pas de renommage en base.
2. Trois statuts indépendants ; transitions obligatoires pour tout changement.
3. Sécurité documentaire (S1–S5) **avant** toute fonctionnalité ; lot 0 de tests préalable.
4. Audio source : `drive_id`/`item_id` en base, flux via le backend, jamais d'URL transmise. Livrables : stockage objet privé indépendant, **fin du repli disque local**.
5. Mode B par *delta query* planifiée, anti-doublon par unicité (`drive_id`, `item_id`) ; mode A et mode B indépendants.
6. Moteur tarifaire conservé ; suppression du forfait codé en dur ; règles utilisées par un calcul définitif immuables.
7. Migrations strictement additives jusqu'au lot 10.

## Blocages et questions ouvertes (à trancher avant les lots concernés)

| # | Point | Bloque | Hypothèse de travail si pas de réponse |
|---|---|---|---|
| Q1 | **Où se trouve le OneDrive « privé du client »** : dans le tenant Microsoft d'A2C (dossier partagé par les clients), ou dans le tenant de chaque client ? Une application Graph en mode application ne lit pas un OneDrive d'un autre tenant ni un lien de partage externe. | Lots 3 et 6 (conception de l'accès Graph) | Les audios sont dans un dossier du tenant A2C. |
| Q2 | **Accès à la production** : base (lecture seule sur une copie) et Railway (CLI non connectée) pour la réconciliation M0 (B9, B10, état des enums, volume de fichiers locaux). | M0, tous les lots touchant au schéma | Réalisé sur copie fournie par l'administratrice. |
| Q3 | **Permissions actuelles de l'application Azure** (celle qui sert à l'upload) : à lister dans le portail. | Lot 3 | Nouvelle inscription à privilèges minimaux. |
| Q4 | **Stockage objet** des livrables : Railway Bucket ou S3-compatible externe ? | Lot 4 | Railway Bucket si disponible, sinon S3-compatible UE. |
| Q5 | **Rôle Client** (espace de dépôt audio existant) : conserver tel quel, ou le retirer ? | Lot 2 | Conservé, gelé. |
| Q6 | **Rôle correcteur** : le cadrage décrit le contrôle par l'administratrice et la correction par le prestataire ; le code prévoit un correcteur distinct. Garder la double affectation ? | Lots 2, 5 | Conservé comme affectation optionnelle. |
| Q7 | **Règle de paiement prestataire** : indépendante de l'encaissement client, ou conditionnée ? | Lot 8 | Indépendante. |
| Q8 | **Document de cadrage v2.0** (`docs/Cadrage_Retranscriptions_v2.pdf`) absent du dépôt : à fournir si son contenu diffère de la présente demande. | Vérification de cohérence | Le présent cadrage prévaut. |
| Q9 | **Rôle coordinatrice** : conserver son accès actuel aux tarifs, IBAN-adjacent et facturation, ou le restreindre (§7.2) ? | Lot 1 | Restreint. |

Aucun de ces points n'empêche le **lot 0 (tests)** ni le **lot 1 (sécurité)**, qui peuvent démarrer immédiatement.
