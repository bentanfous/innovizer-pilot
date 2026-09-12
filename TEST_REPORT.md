# Innovizer Pilot v0.4 — Test report

## Exécuté

- Compilation Python `app.py` : OK
- Compilation `innovizer/raw_builder.py` : OK
- Démarrage serveur : OK
- `GET /api/health` : OK, version `0.4.0`
- `GET /api/raw/status` : OK
- Démarrage sans dataset préchargé : OK
- Les huit catégories de sources sont initialisées vides : OK
- Data Hub verrouillé tant que les sources obligatoires ne sont pas présentes : prévu par l'API/UI

## Non rejoué faute de sources brutes disponibles dans ce package

Le build complet paie + bulletins PDF + timesheets n'a pas été rejoué sur les sources Dunasys originales, car les fichiers bruts originaux ne sont pas inclus dans le contexte de build actuel. Les moteurs utilisés sont ceux des batches validés précédemment ; le premier test réel doit être effectué via l'interface avec les sources Dunasys.
