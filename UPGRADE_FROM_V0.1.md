# Mise à jour Railway v0.1 → v0.2

La v0.2 expose les 3 briques dans l'interface :
1. Data Hub
2. Project Mapper
3. Audit Eva

## Mise à jour la plus simple
Dans GitHub, remplace le contenu du repository par le contenu de ce dossier puis commit.
Railway redéploiera automatiquement.

## Mise à jour minimale
Si le repo v0.1 fonctionne déjà, les fichiers principaux modifiés sont :
- `app.py`
- `web/index.html`
- `README.md`
- `README_RAILWAY.md`

Les autres fichiers restent compatibles avec la v0.1.

## Vérification
Après déploiement :
- `/api/health` doit renvoyer `version: 0.2.0`
- la page d'accueil doit afficher une navigation à gauche : Data Hub / Project Mapper / Audit Eva.
