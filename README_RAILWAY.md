# Innovizer Pilot v0.2 — Déploiement Railway

## 1. Mettre ce dossier dans GitHub
Créez un nouveau repository GitHub vide, puis chargez **le contenu de ce dossier** à la racine du repository.

Fichiers indispensables pour Railway :
- `app.py`
- `requirements.txt`
- `Procfile`
- `railway.toml`
- `.python-version`
- dossier `innovizer/`
- dossier `web/`
- dossier `data/` avec les trois fichiers Excel snapshot Dunasys

Ne commitez jamais `.env` ni aucune clé privée.

## 2. Déployer sur Railway
1. Railway > New Project
2. Deploy from GitHub repo
3. Choisir le repository Innovizer
4. Railway détecte le projet automatiquement
5. Le start command est déjà `python app.py`
6. Settings > Networking > Generate Domain

## 3. Vérifier
Ouvrez :
`https://VOTRE-DOMAINE.up.railway.app/api/health`

Vous devez obtenir un JSON avec `"ok": true`.

Puis ouvrez simplement la racine du domaine pour utiliser le MVP.

## Variables d'environnement
Aucune variable n'est requise pour le test texte actuel.

Plus tard seulement :
- `OPENAI_API_KEY`
- `VAPI_PUBLIC_KEY`
- `VAPI_ASSISTANT_ID`
- `ELEVENLABS_API_KEY`

`PORT` est injecté automatiquement par Railway : ne le forcez pas.

## Limite connue du pilote
Les sessions Eva sont conservées en mémoire du processus et des JSON locaux. Railway peut redémarrer le conteneur ; une session en cours peut alors ne plus être reprenable. C'est acceptable pour le premier test. La v0.2 utilisera PostgreSQL/Supabase.
