# Validation locale

Testé le 2026-09-12 dans l'environnement de génération :

- `python -m compileall -q .` : OK
- `python run_pilot.py` : OK — entretien complet, couverture 100 %, synthèse générée
- `GET /api/health` : OK
- `GET /api/projects` : OK — 91 projets Dunasys chargés
- création d'un entretien via API : OK
- envoi d'une réponse via API : OK — passage `probleme` → `etat_art`

Le pilote ne contient aucune clé API privée.
