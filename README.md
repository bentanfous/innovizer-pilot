# Innovizer Pilot v0.3 — Upload-first

La v0.3 retire les données Dunasys préchargées de l'application. L'utilisateur doit importer ses propres fichiers depuis l'écran **00 · Import**.

## Fichiers supportés dans ce pilote

1. **Brique 01 consolidée** — obligatoire (`.xlsx`/`.xlsm`) avec les onglets : `Controles`, `Annexe personnel`, `Qualification`, `Screening projets`, `Quotites`, `Fournisseurs`, `Documents`, `Couverture preuves`.
2. **Screening projets** — optionnel, onglet `Screening projets`.
3. **Screening sous-traitance** — optionnel, onglet `Screening fournisseurs` ou `Fournisseurs`.

Les fichiers 2 et 3 remplacent les onglets correspondants du fichier consolidé lorsqu'ils sont présents.

## Railway

Le repository doit être **privé**, car ces fichiers peuvent contenir des données RH, paie et R&D confidentielles.

Le stockage local Railway est éphémère lors d'un redeploy. Pour un usage durable, monter un Railway Volume et définir :

```
INNOVIZER_UPLOAD_DIR=/data/uploads
```

## Lancer localement

```bash
pip install -r requirements.txt
python app.py
```

Puis ouvrir http://localhost:3010.
