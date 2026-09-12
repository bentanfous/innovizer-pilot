# Mise à jour v0.3 → v0.4

1. Dézipper la v0.4.
2. Remplacer le contenu du repo GitHub par celui de la v0.4.
3. Ne pas uploader dans GitHub les fichiers paie / CV / diplômes / factures.
4. Commit : Railway redéploie automatiquement.
5. Vérifier `/api/health` : la version doit être `0.4.0`.
6. Ouvrir l'application : l'écran **00 · Sources** apparaît.
7. Déposer directement paie + bulletins PDF + timesheets, puis les sources optionnelles.
8. Cliquer **Construire le Data Hub**.

## Railway Volume recommandé

Dans Railway, créer un volume monté par exemple sur `/data` puis ajouter :

- `INNOVIZER_RAW_DIR=/data/raw_uploads`
- `INNOVIZER_UPLOAD_DIR=/data/derived`

Ainsi les sources et le Data Hub survivent aux redeploys.
