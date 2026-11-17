# Refonte A2C Retranscriptions — Rapport final

> Réalisé le 2026-11-16 sur la base de `docs/REFONTE_A2C_AUDIT.md`, complété le même jour par les décisions métier sur les tarifs, les majorations et les notifications (§10), puis sur les délais, les barèmes annuels et l'urgence (§11). Environnement : développement local (PostgreSQL 16 réel via `pgserver`, API FastAPI, interface Vite). **Aucun déploiement ni aucune opération sur la base Railway n'ont été effectués.**

## 1. Synthèse

| Domaine | Résultat |
|---|---|
| Failles critiques S1–S5 | Corrigées et couvertes par des tests automatisés |
| Bugs de l'audit B1–B13 | Corrigés (détail §3) |
| Tests | Backend **148 tests** · Frontend **16 tests** · tous verts |
| Dépendances | pip-audit : 23 vulnérabilités → **0** · npm audit : 23 (dont 11 élevées) → **0** |
| Interface | Refonte complète (claire, responsive, 17 écrans vérifiés en navigateur, desktop et mobile, sans erreur console) |
| Migrations | 3 migrations additives (0005, 0006, 0007), testées sur base vierge **et** sur données de l'ancien modèle |
| Tarifs | **Administrables par la cliente** (grilles, tranches, majorations, dates d'application, historique, simulateur), sans rétroactivité (§10) |

## 2. Fonctionnalités réalisées

### Organisation et droits
- Rôles : administratrice (tous droits), coordinatrice/relectrice, comptabilité, lecture seule, retranscripteur, client (périmètre gelé). Le rôle « correcteur » n'est plus proposé (pas de correcteur externe) ; la relecture est interne.
- **Droits configurables** : 13 permissions (dossiers, audios, attribution, relecture, validation, finance, tarifs, journal…). Valeurs par défaut par rôle, ajustables utilisateur par utilisateur par l'administratrice. Gestion des utilisateurs et consultation des IBAN : réservées à l'administratrice, jamais délégables.
- Comptes liés explicitement à une fiche retranscripteur ou client (clé étrangère) — fin de la correspondance par email.
- Mot de passe temporaire (affiché une seule fois) et **changement imposé** à la première connexion ; politique de mot de passe (12 caractères, 3 types) ; révocation des sessions au changement de mot de passe, de rôle ou à la désactivation.

### Production (machine d'états unique, contrôlée côté serveur)
`À qualifier → À attribuer → Attribué → En cours → Livré → À relire → (Correction demandée → Livré…) → À contrôler → Validé → Archivé`, plus `Bloqué` (avec motif et retour à l'étape précédente).
Trois suivis indépendants : production, facturation (`non facturable → à établir → émise → partiellement réglée → réglée`), paiement retranscripteur (`à payer → validé → payé`). Aucune route ne modifie un statut hors de `services/workflow.py` ; chaque changement est journalisé avec son auteur.

### Audios et OneDrive
- **Mode manuel opérationnel** : lien de partage OneDrive/SharePoint (domaines Microsoft uniquement, lien chiffré, jamais renvoyé) ou fichier (signature audio vérifiée, 500 Mo max).
- Vérification d'accès Graph à l'ajout du lien quand OneDrive est configuré ; sinon l'audio est enregistré « non vérifié » avec un message explicite (aucune vérification simulée).
- Création de la mission depuis l'audio en une étape (client, instance, échéance, critères).
- **Proxy sécurisé** : téléchargement en flux, après contrôle de l'identité, du rôle, de l'attribution active et de l'appartenance du fichier ; aucune URL de stockage n'est transmise.
- **Graph préparé** : client avec cache de jeton, reprises (429/5xx, `Retry-After`), envoi simple et par session (gros fichiers), résolution des liens, **détection par delta** (anti-doublon, reprise sur erreur, état visible dans l'interface), rangement `A2C Retranscriptions/<Client>/<Dossier>/PV_vN.docx`.
- Plus aucune bascule silencieuse vers le disque local (le stockage local n'existe qu'en développement et est refusé en production).

### PV Word
- Dépôt exclusivement `.docx`, contrôle du **type réel** (archive OOXML, type de contenu Word), refus des macros, protections anti « zip bomb » et XML sans entités externes, ouverture réelle par python-docx.
- Contrôle **Comic Sans MS 12 pt** par résolution de l'héritage des styles (défauts du document → styles de paragraphe → styles de caractère → mise en forme directe → polices du thème). Titres tolérés en taille, en-têtes/pieds contrôlés en police.
- Rapport : taux de conformité, polices et tailles utilisées, passages signalés (paragraphe + extrait), avertissements (objets embarqués, ressources externes, modifications suivies, commentaires), nombre de pages selon Word. **Le document n'est jamais modifié.**
- Non-conformité non bloquante au dépôt (alerte), mais validation finale soumise à un **motif de dérogation**.
- Versions successives conservées (déposant, date, empreinte SHA-256), versions corrigées par l'équipe, **comparaison texte entre versions**.
- Stockage durable : PostgreSQL par défaut, OneDrive en option.

### Attribution assistée
Suggestions classées et expliquées (qualité = corrections/livraisons, respect des délais, rapidité, fiabilité, régularité, conformité des documents, spécialités déclarées ou acquises, disponibilité, charge réelle recalculée). En dessous de 3 missions terminées : « Historique insuffisant », l'historique n'entre pas dans le score et aucun indicateur n'est inventé. **Aucune attribution automatique** : la responsable choisit et confirme. Indicateurs invisibles des retranscripteurs.

### Finance
- Moteur tarifaire, grilles France/Togo, majorations, versions historiques et chiffrement des IBAN conservés.
- Calcul toujours « à valider » par une personne habilitée ; détail des règles appliquées affiché (« Comment ce montant est calculé »).
- Facture : bug `payeur` corrigé, numérotation sans réutilisation, HTML échappé, PDF sans accès réseau ; **plus de suppression** : annulation motivée qui conserve le numéro.
- Encaissements partiels/complets (montant, date, mode, référence), contrôle du trop-perçu.
- Paiements retranscripteurs : générés à l'émission de la facture, ajustement motivé, validation, paiement avec date de virement, puis figés.
- Aucun recalcul après facturation ; règles d'une grille ayant servi à un calcul validé non modifiables (nouvelle version obligatoire, fonction « nouvelle version » fournie).

### Notifications
In-app (cloche, compteur, marquage lu) + emails **Brevo** configurables par utilisateur. Événements : mission attribuée, échéance proche, retard, PV livré, nouvelle version, correction demandée, PV validé, PV à contrôler, facture à établir, facture créée, encaissement reçu, paiement effectué, nouvel audio, mission retirée, échéance modifiée. Dédoublonnage en base ; statut d'email réel (`envoye`/`echec`/`non_configure`) ; les notifications internes fonctionnent sans Brevo. Alertes périodiques activables (`ENABLE_SCHEDULER`).

### Interface
- Identité A2C (vert sauge) déclinée en thème clair, police Outfit **auto-hébergée** (plus d'appel à Google Fonts), icônes Lucide homogènes, contrastes accessibles, navigation clavier, responsive (menu mobile).
- **Administration** : tableau de bord à 15 indicateurs réels calculés côté serveur et cliquables vers la liste filtrée ; liste des dossiers (filtres par étape, retard, urgence, recherche) ; fiche dossier avec frise d'avancement, encadré « Prochaine étape » contextuel et onglets Aperçu / Versions du PV / Attribution / Facturation / Historique ; Audios reçus ; Facturation & règlements ; Clients ; Retranscripteurs (charge, spécialités, indicateurs, création d'accès) ; Tarifs (pages existantes restylées) ; Utilisateurs & droits ; Journal ; Mon compte ; Aide réécrite.
- **Retranscripteurs** : une carte par mission (échéance relative, priorité, consignes, téléchargement de l'audio, dépôt par glisser-déposer, rapport de conformité immédiat, corrections, historique des versions), sans aucun vocabulaire administratif ni montant.
- Jeton de session en `sessionStorage` ; en-têtes de sécurité (CSP, anti-clickjacking, HSTS) sur le serveur statique.

## 3. Corrections de sécurité et bugs

| Réf. audit | Correction | Test |
|---|---|---|
| S1 lien OneDrive exposé | Plus aucune URL/identifiant de stockage dans les réponses ; flux proxy | `test_s1_*` |
| S2 IDOR audio | Accès limité à l'affectation active du prestataire (404 sinon), retiré au retrait de mission | `test_s2_*` |
| S3 URL arbitraire | Routes `fichiers`/`upload` supprimées ; liens restreints aux domaines Microsoft (anti-SSRF) | `test_s3_*`, `test_validation_liens_onedrive` |
| S4 montants exposés | Permissions `finance.*` sur calculs, factures, paiements, grilles ; schémas prestataire sans montants | `test_s4_*` |
| S5 dossiers client | Accès client limité à son client (FK), schéma réduit | `test_s5_client_cloisonne` |
| S6 échéance modifiable par le prestataire | PATCH réservé aux responsables | `test_prestataire_ne_modifie_pas_son_echeance` |
| S7 contrôle des fichiers | Signature audio, contrôle DOCX complet, limites de taille | `test_docx.py`, `test_audio_signature_verifiee` |
| S8 repli disque local | Supprimé ; stockage local interdit en production | config + tests |
| S10 injections HTML | Échappement des emails et factures, PDF sans ressources externes, CSP | `test_facture_html_echappee` |
| S11 dépendances | PyJWT remplace python-jose, passlib remplacé par bcrypt, mises à jour | pip-audit / npm audit à 0 |
| S12 force brute | Limitation par compte et par IP, vérification à temps constant, politique de mot de passe | `test_anti_bruteforce` |
| S13 compte par défaut | Supprimé du code ; l'ancien compte au mot de passe public est désactivé automatiquement | seed |
| S14 fuite dans les logs | `start.sh` n'affiche plus l'URL de base | — |
| S15 DEBUG | Désactivé par défaut ; refus de démarrer en production avec une configuration faible | config |
| S16 en-têtes | API et frontend | `test_en_tetes_securite` |
| S17 suppressions | Dossier : suppression logique ; facture : annulation | `test_suppression_*`, `test_annulation_conserve_numero` |
| S18 rétroactivité des tarifs | Grilles utilisées figées, recalcul interdit après facture | `test_grille_utilisee_figee`, `test_recalcul_interdit_apres_facture` |
| S19 paiements | Machine d'états, paiement figé | `test_paiement_prestataire_machine_etats` |
| B1 `payeur` | Corrigé | `test_generation_facture_bug_payeur_corrige` |
| B2 journal de connexion | Enregistré dans la transaction (succès et échecs) | `test_login_ok_et_journal_enregistre` |
| B3 journal supprimé | Suppression logique + journal immuable (refus ORM des modifications) | `test_journal_immuable`, `test_suppression_logique_conserve_journal` |
| B4 transitions contournées | Machine d'états unique | `test_transitions_interdites`, `test_cycle_complet_production` |
| B5 forfait codé en dur / auto-validation | Supprimés ; tarif client officiel transposé en grille versionnée | `test_grille_client_identique_ancien_bareme` (19 cas), `test_calcul_refuse_sans_grille_client` |
| B7 charge dérivante | Charge recalculée depuis les attributions actives | `test_suggestions_charge_et_specialite` |
| B9/B10 dérive de schéma | Modèle aligné ; migration 0004 rendue conditionnelle | `test_0004_avec_enum_natif` |
| B13 numérotation | Plus grand numéro + 1, pas de réutilisation | tests dossiers et factures |
| Nouveau | `alembic/env.py` plantait si l'URL de base contenait `%` | `test_migrations.py` |

## 4. Tests exécutés

| Suite | Commande | Résultat |
|---|---|---|
| Backend (PostgreSQL 16 réel, migrations jouées à chaque exécution) | `python -m pytest -q` | **148 passed** |
| Frontend (Vitest + Testing Library) | `npm test` | **16 passed** |
| Typage | `tsc -p tsconfig.app.json --noEmit` | OK |
| Lint | `npm run lint` | 0 erreur |
| Build | `npm run build` | OK (pages lourdes chargées à la demande) |
| Dépendances Python | `pip-audit -r requirements.txt` | 0 vulnérabilité connue (avant : 23 dans 6 paquets) |
| Dépendances JS | `npm audit` | 0 vulnérabilité (avant : 23 dont 11 élevées) |
| Parcours réel en navigateur | Chrome headless, données de démonstration | 24 écrans (dont 7 pour les tarifs), 0 erreur console, 0 erreur 5xx ; redirection d'un retranscripteur hors des pages internes vérifiée |

Couverture backend : authentification (11), droits et failles S1–S5 avec matrice de rôles (33), workflow complet et transitions (14), contrôle DOCX (16), finance (30 dont 19 cas de non-régression tarifaire), tarifs et majorations administrables (13), délais de réalisation et cycle de vie des échéances (11), attribution/notifications/alertes/détection Graph/tableau de bord (18), migrations (2, dont la reprise des grilles par les 0006 et 0007).

## 5. Décisions importantes

1. Table `dossiers` conservée ; nouveaux statuts en colonnes texte additionnelles ; l'ancien `statut` reste rempli (compatibilité).
2. **Tarif client** : la grille client en base ne contenait qu'un « taux de référence 5 €/page » ; le barème officiel (forfaits par tranche) n'existait que dans le code supprimé. Il est désormais porté par la grille « Tarif client A2C — forfaits par tranche » (v2026.1), **grille initiale modifiable par la cliente** ; un test vérifie qu'elle reproduit exactement l'ancien barème de 1 à 137 pages. L'ancienne référence 5 €/page reste dans l'historique de la même grille (désactivée). **À confirmer par la cliente.**
3. PV stockés par défaut dans PostgreSQL (durable, sauvegardé) en attendant OneDrive.
4. Paiement retranscripteur indépendant de l'encaissement client.
5. Coordinatrice par défaut : production, attribution, relecture, validation, clients, journal — sans finance ni tarifs (ajustable en un clic).
6. Espace client conservé avec un périmètre minimal (suivi + dépôt d'audio).

## 6. Limitations connues

- **Microsoft Graph n'a pas été testé contre un vrai tenant** (aucun identifiant disponible) : le code est couvert par des tests avec un client simulé uniquement. Premier essai réel à mener en recette.
- Le dépôt d'un **fichier** audio charge le fichier en mémoire (500 Mo max) : à surveiller selon la mémoire Railway ; l'ajout par lien n'a pas cette limite.
- La limitation des tentatives de connexion est en mémoire par processus (suffisante pour une instance unique).
- Le jeton en `sessionStorage` reste lisible en cas de faille XSS (risque réduit par la CSP et l'absence de HTML injecté).
- Contrôle DOCX : heuristique robuste mais pas exhaustive (zones de texte imbriquées, scripts complexes) ; le nombre de pages provient des métadonnées Word.
- Pondérations du score d'attribution : choix initial, à ajuster à l'usage.
- La majoration urgence s'applique aussi à la rémunération du retranscripteur (comportement existant conservé comme configuration initiale, désormais modifiable par la cliente) : **à confirmer** (§10.5).
- Pas de génération d'avoir : une facture partiellement réglée ne peut pas être annulée dans la plateforme.
- PDF de facture : nécessite les bibliothèques système de WeasyPrint sur Railway ; à défaut, message explicite et version HTML disponible.
- Immutabilité du journal garantie au niveau applicatif (pas de déclencheur PostgreSQL).
- Les anciens fichiers de la table `fichiers_dossier` (liens/chemins locaux) ne sont plus accessibles par l'API ; la table est conservée.
- L'éditeur de « règles avancées » (planchers, plafonds, conditions combinées) reste l'ancien écran, restylé ; les grilles courantes (tranches) et les majorations ont leur interface simplifiée.
- Python 3.12 épinglé via `backend/.python-version` : non vérifié sur Railway.

## 7. Variables d'environnement

Voir `docs/CONFIGURATION_SERVICES_EXTERNES.md` et `backend/.env.example`. Minimum pour la production : `DATABASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`, `APP_ENV=production`, `ALLOWED_ORIGINS`, `APP_PUBLIC_URL`, et `VITE_API_URL` côté frontend.

## 8. Accès externes encore nécessaires

1. **Microsoft 365 de l'association** : confirmation du type de compte et de l'emplacement des fichiers, application Entra ID (tenant, client, secret), identifiant du lecteur, consentement administrateur.
2. **Brevo** : compte, domaine authentifié (SPF/DKIM/DMARC), adresse d'envoi, clé API.
3. **Railway** : accès au projet pour configurer les variables et lancer la réinitialisation.

## 9. Opérations restant à effectuer avant production

1. Relire et valider la refonte (les modifications ne sont pas encore commitées).
2. **Sauvegarder la base Railway** (même si les données sont fictives).
3. Configurer les variables (section 7), dont `APP_ENV=production`, puis déployer : les migrations 0004 (sécurisée) et 0005 s'appliquent ; le démarrage s'interrompt en cas d'échec.
4. Réinitialiser les données de démonstration existantes (autorisé par la cliente) :
   `CONFIRMER_REINITIALISATION=SUPPRIMER-TOUT python scripts/reinitialiser_donnees.py --confirmer`
   (via `railway run`) — vide toutes les tables, recrée les deux comptes internes et les grilles tarifaires.
5. Se connecter avec les comptes initiaux `administratrice@a2c.example` et `coordinatrice@a2c.example` (mots de passe transmis séparément), définir le mot de passe définitif, puis **remplacer ces adresses de connexion** par les vraies adresses dans « Utilisateurs & droits ».
6. Créer les clients et les fiches retranscripteurs, puis leurs accès (bouton « Créer l'accès »).
7. Faire vérifier par la cliente ses tarifs et majorations dans « Tarifs & paramètres » (simulateur), et trancher les points du §10.5.
8. Configurer Microsoft Graph, puis `ENABLE_SCHEDULER` ; Brevo plus tard (non bloquant).
9. Valider avec la cliente les points marqués « à confirmer » (§5.2, §6 et §10.5).

## 10. Évolutions complémentaires : tarifs, majorations et notifications

### 10.1 Analyse préalable du moteur tarifaire
| Constat dans le code existant | Risque | Traitement |
|---|---|---|
| Grille choisie à la date du jour (`date.today()`), sans ordre déterministe | Un recalcul après un changement de tarif appliquait le nouveau tarif à un dossier ancien | Grille choisie à la **date de réception de l'audio** ; ordre de priorité explicite |
| Le calcul ne gardait que nom/version des grilles ; règles modifiables sur place | Impossible de savoir quels montants avaient servi ; historique perdu | **Copie intégrale** des grilles et règles dans chaque calcul ; versions publiées non modifiables |
| Champs « grille tarifaire » des fiches client et retranscripteur ignorés par le moteur | Tarif négocié / convention Togo impossibles à appliquer simplement | Attribution depuis la fiche prise en compte (toutes versions de la grille) |
| Urgence : description « +30 % sur le montant client », mais calcul appliqué **aussi** au retranscripteur | Ambiguïté métier | Comportement réel conservé comme configuration initiale, réglable, **à confirmer** |
| Aucune grille « sans prise de notes » ni « prestation particulière » | Ces critères n'avaient aucun effet | Créables par la cliente depuis l'interface |
| Montants des calculs validés et factures stockés, jamais recalculés | — (point fort) | Conservé ; recalcul interdit après facturation |

Le mécanisme de versionnement existant (numéro de version, dates de début/fin, « nouvelle version ») a été réutilisé et complété (famille de versions, brouillon) plutôt que remplacé.

### 10.2 Ce que la cliente peut faire seule (rubrique « Tarifs & paramètres »)
- **Tarifs clients / Rémunération des retranscripteurs** : créer une grille, définir ses tranches (« à partir de N pages » → forfait ou prix par page), avec un aperçu lisible (« 10 à 20 pages · 100,00 € ») ; choisir à qui elle s'applique : par défaut, à un type d'instance, ou aux clients / retranscripteurs auxquels elle est attribuée (depuis leur fiche) ; enregistrer en brouillon ou appliquer à partir d'une date ; désactiver / réactiver ; consulter l'historique des versions (période, état, auteur, utilisation).
- **Majorations** (urgence, sans prise de notes, prestation particulière) : activer / désactiver, pourcentage ou montant fixe, application **indépendante** au tarif client et à la rémunération du retranscripteur, conditions de déclenchement de l'urgence (case cochée, dossier signalé urgent, délai réception → échéance ≤ N jours), date d'application, historique.
- **Simulateur** : prix client, rémunération, marge, grilles et majorations retenues, détail ligne à ligne, pour n'importe quelle date de réception.
- Droits : permission `tarifs.gerer` (administratrice ; délégable à la coordinatrice). La comptabilité consulte sans modifier. L'attribution d'un tarif négocié à une fiche exige aussi `tarifs.gerer`.

### 10.3 Garanties de non-rétroactivité (testées)
1. Une version publiée n'est jamais modifiée : « Modifier » crée une nouvelle version, l'ancienne reste consultable.
2. Une publication ne peut pas prendre effet dans le passé ; la version précédente est automatiquement clôturée la veille.
3. Le tarif applicable est celui en vigueur à la **date de réception de l'audio** : un dossier reçu avant le changement garde l'ancien tarif, même recalculé.
4. Chaque calcul conserve la copie intégrale des paramètres appliqués (grilles, règles, conditions, date de référence), visible dans l'onglet Facturation du dossier.
5. Calculs validés et factures ne sont jamais recalculés ; un brouillon n'a aucun effet ; toute action est journalisée.

### 10.4 Notifications
Inchangé et conforme à la demande : les notifications internes fonctionnent sans aucun service externe ; Brevo est facultatif (configuration ultérieure) ; sans clé, chaque email est marqué « non configuré » et n'est jamais présenté comme envoyé (testé).

### 10.5 Arbitrages restant à confirmer avec la cliente
| Point | Configuration initiale retenue | Où le modifier |
|---|---|---|
| Majoration urgence (taux, montant, application client / retranscripteur, déclenchement) | **Désactivée** depuis la décision du §11 ; les anciennes valeurs (+30 %, client et retranscripteur) restent affichées à titre indicatif | Tarifs & paramètres → Majorations → « Configurer et activer » |
| Date de référence des tarifs et des délais | **Confirmée** : date de réception de l'audio | — |
| Barème client par tranche (remplace la référence 5 €/page) | Grille « Tarif client A2C — forfaits par tranche » | Tarifs & paramètres → Tarifs clients |
| Rémunération France identique au tarif client (marge nulle hors majorations) | Reprise des conventions documentées | Tarifs & paramètres → Rémunération |
| Grille Togo | Publiée « sur attribution » : s'applique aux retranscripteurs dont la fiche la désigne | Fiche du retranscripteur |
| Publication avec effet rétroactif | Interdite (date ≥ aujourd'hui) | — |

### 10.6 Fichiers ajoutés ou modifiés
Backend : `app/services/tarifs.py` (sélection, majorations, versions, copie des paramètres), `app/api/v1/tarifs.py`, `app/services/calcul_service.py`, `app/models/pricing/grille.py`, `alembic/versions/0006_tarifs_administrables.py`, `seed_grilles.py`, contrôles d'attribution dans `clients.py` / `prestataires.py`, tests `tests/test_tarifs.py`.
Frontend : `src/pages/tarifs/` (page, éditeurs, simulateur), `src/lib/tarifs.ts`, fiches client et retranscripteur, onglet Facturation du dossier, test `src/test/tarifs.test.ts`.

## 11. Décisions complémentaires : délais, barèmes annuels, urgence

### 11.1 Délais de réalisation administrables
- **Avant** : trois valeurs codées en dur — délai de rendu selon la durée de l'audio (7 / 18 / 25 jours, issu des « modalités A2C » de l'ancien code, compté depuis l'attribution), seuil « dossier urgent » (< 2 jours), alerte « échéance proche » (48 h).
- **Maintenant** : onglet « Délais de réalisation » de « Tarifs & paramètres » :
  - règles de délai évaluées dans l'ordre choisi par la cliente, chacune avec des conditions facultatives (type d'instance, durée de l'audio, urgence, sans prise de notes / prestation particulière), un délai en jours **calendaires ou ouvrés** et une note ;
  - paramètres généraux : seuil « dossier urgent », alerte « échéance proche », temps de relecture réservé avant l'échéance client (rendu attendu du retranscripteur) ;
  - outil « Tester un délai ».
- **Cycle de vie de l'échéance client** :
  1. à la réception de l'audio (création du dossier) : échéance prévisionnelle = **date de réception + délai de la première règle applicable**, historisée ;
  2. tant que le dossier n'est pas attribué : recalcul automatique si les règles changent ou si la durée / le type d'instance du dossier change (chaque recalcul est historisé : ancienne et nouvelle date) ;
  3. à la **première attribution** : l'échéance est **figée** (date du gel conservée, entrée « échéance figée » dans l'historique avec l'échéance applicable) ;
  4. ensuite : aucune modification des règles ne la change, y compris si la mission est retirée puis réattribuée ; le retour au calcul automatique est refusé ;
  5. à tout moment : modification manuelle possible pour les personnes autorisées (droit « dossiers.gerer »), historisée avec ancienne valeur, nouvelle valeur, date et auteur.
- **Temps de relecture** : le rendu attendu du retranscripteur = échéance client − temps de relecture paramétré ; l'échéance promise au client n'est pas modifiée.
- Le dossier affiche l'origine de l'échéance (« calculée : 7 j après réception (« Audio jusqu'à 1 h ») », « saisie manuellement », « figée le … à l'attribution ») ; l'onglet Historique liste chaque changement.
- Une modification manuelle de l'échéance client après attribution ne déplace pas automatiquement l'échéance du retranscripteur : elle s'ajuste séparément (bouton « Échéance » de l'attribution).
- **Aucun paramètre inventé** : la configuration initiale reprend exactement les valeurs de l'ancien code (marquées « à confirmer par la cliente ») ; elle est créée une seule fois par `seed_parametres.py` et n'est jamais réécrite ensuite. Si un paramètre est vidé, la fonction correspondante est désactivée (pas de valeur de secours dans le code) : par exemple sans règle applicable, l'échéance est à saisir.
- Limite : les jours ouvrés excluent samedi et dimanche mais pas les jours fériés.

### 11.2 Barèmes annuels
Le dispositif du §10 couvre le besoin ; un bouton « Barème {année suivante} » prépare directement la nouvelle version avec entrée en vigueur au 1er janvier (date modifiable). Les anciennes versions sont conservées intégralement ; le barème applicable reste déterminé par la date de réception de l'audio ; les dossiers engagés et factures validées ne sont jamais recalculés.

### 11.3 Majoration d'urgence
Désactivée par défaut (nouvelles installations et migration 0007 des bases existantes) : aucune majoration n'est appliquée tant que la cliente ne l'a pas configurée et activée (taux ou montant, application au prix client et/ou à la rémunération, conditions, date). Les calculs déjà enregistrés ne sont pas modifiés.

### 11.4 Paramètres à fournir ou confirmer par la cliente
| Paramètre | État actuel | Où le régler |
|---|---|---|
| Délais de réalisation | Reprise de l'ancien code (7 / 18 / 25 j selon la durée), à confirmer ; la tranche « 1 h à 2 h » était ambiguë dans l'ancienne documentation (« 2 h – 4 h ») et suit ici le code (≤ 4 h → 18 j) | Délais de réalisation |
| Jours calendaires ou ouvrés | Calendaires | Idem |
| Seuil « dossier urgent » | 2 jours (ancien code) | Délais → Autres paramètres |
| Alerte « échéance proche » | 48 h (ancien code) | Idem |
| Temps de relecture avant l'échéance client | 0 jour (le retranscripteur rend à l'échéance client) | Idem |
| Majoration d'urgence | Désactivée | Majorations |
| Barème client de l'année suivante | À saisir | Tarifs clients → « Barème {année} » |

## 12. Guide de prise en main interactif (dans la plateforme)

- **Visite guidée** : bulles de conseil qui mettent en évidence les éléments réels de l'écran et changent de page toute seule (tableau de bord, audios, dossiers, facturation, tarifs, retranscripteurs, utilisateurs). Trois versions selon le profil : responsables (13 étapes, filtrées par droits), fiche dossier (« Guide de cette page »), retranscripteurs (4 étapes). Navigation par boutons ou flèches du clavier, Échap pour quitter, adaptée au mobile.
- **Lancement** : automatique une seule fois à la première connexion de chaque compte (mémorisé dans le navigateur), puis à volonté depuis la page Aide.
- **Parcours de démonstration** (`/aide/parcours`, responsables) : un PV fictif (« Plénière de novembre ») suivi en 9 étapes, de la réception de l'audio au règlement de la facture, avec écrans simulés, action à cliquer à chaque étape, conseils, et un contrôle de conformité volontairement raté puis corrigé. Entièrement simulé : aucune donnée enregistrée, aucun risque pour les vraies données.
- **Parcours complémentaires** (page Aide, sans doublon avec le parcours du PV qui couvre le chemin idéal), tous simulés et interactifs :
  - *Préparer le barème de l'année et les majorations* (4 min) : nouveau barème, date d'entrée en vigueur, non-rétroactivité, activation de la majoration d'urgence ;
  - *Délais et échéances* (4 min) : règles de délai, calcul à réception, recalcul avant attribution, gel à l'attribution, modification manuelle tracée ;
  - *Quand ça se complique* (6 min) : dérogation sur PV non conforme, retrait de mission, blocage, règlement en deux fois, annulation de facture, paiement du retranscripteur ;
  - *Accès et droits de l'équipe* (3 min) : création d'accès, première connexion, droits de la coordinatrice, vraies adresses ;
  - *Ma première mission* (3 min, retranscripteurs) : mission reçue, audio, dépôt non conforme puis corrigé, correction demandée, mission validée.
- Fichiers : `frontend/src/components/tour/` (visites guidées, texte dans `tours.ts`), `frontend/src/pages/demo/` (moteur commun `moteur.tsx`, contenu des parcours `pv.tsx` et `autres.tsx`, registre). Tests : `src/test/tour.test.tsx` (28 tests frontend au total, chaque parcours est joué jusqu'au bout).
