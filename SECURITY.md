# Règles communes de sécurité

Ce fichier constitue la référence commune de sécurité du projet.

Tout assistant IA ou agent intervenant sur le code doit lire et respecter
ces règles avant toute analyse, génération ou modification de code.

## Principe général

Appliquer une approche Security by Design avec une vigilance systématique
sur les risques couverts notamment par le Top 10 OWASP.

## Règles obligatoires

- Prévenir les injections SQL, NoSQL, OS, XSS et autres injections.
- Ne jamais construire une requête avec des données utilisateur concaténées.
- Valider, normaliser et contrôler toutes les données provenant d'un utilisateur,
  d'une API, d'un fichier ou d'une source externe.
- Appliquer les contrôles d'authentification et d'autorisation côté serveur.
- Vérifier les autorisations sur chaque ressource concernée.
- Respecter le principe du moindre privilège.
- Ne jamais exposer de mot de passe, token, clé API, secret ou donnée sensible
  dans le code, les logs, les erreurs ou les réponses API.
- Stocker les secrets uniquement dans les mécanismes prévus à cet effet,
  notamment les variables d'environnement.
- Ne jamais commiter de fichier `.env` contenant des secrets.
- Protéger les sessions et tokens contre le vol, la réutilisation,
  la fixation et l'escalade de privilèges.
- Vérifier selon le contexte les risques XSS, CSRF, SSRF, IDOR/BOLA,
  path traversal, mass assignment et upload de fichiers dangereux.
- Ne jamais désactiver une protection de sécurité uniquement pour faire
  fonctionner une fonctionnalité.
- Refuser par défaut une opération lorsque son autorisation ne peut pas
  être établie de manière sûre.
- Limiter les données collectées et exposées au strict nécessaire.
- Éviter d'inscrire des données personnelles ou des secrets dans les logs.
- Examiner les nouvelles dépendances avant leur introduction.
- Ne pas introduire volontairement de dépendance manifestement obsolète
  ou vulnérable lorsqu'une alternative maintenue existe.
- Préserver les protections de sécurité déjà présentes dans le projet.

## Avant une modification

1. Identifier les risques de sécurité liés à la demande.
2. Examiner les protections déjà présentes.
3. Modifier uniquement ce qui est nécessaire.
4. Ne pas modifier du code sans rapport avec la demande.

## Après une modification

1. Exécuter les tests pertinents disponibles.
2. Ajouter ou adapter les tests lorsque la modification touche :
   - l'authentification ;
   - les autorisations ;
   - les entrées utilisateur ;
   - les données sensibles ;
   - les routes ou opérations critiques.
3. Signaler clairement les tests échoués.
4. Signaler les risques restant réellement identifiés.
5. Ne jamais présenter une implémentation comme totalement sécurisée.

## Style de travail

- Fournir du code sécurisé par défaut.
- Privilégier des modifications limitées et vérifiables.
- Éviter les longues explications lorsque quelques lignes suffisent.
- Les commentaires de sécurité ajoutés au code doivent rester courts
  et utiles, par exemple `// fix` ou `# fix`.
- Préserver le comportement existant sauf lorsqu'il constitue un risque
  de sécurité ou contredit explicitement la demande.
