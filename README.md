# Innovizer Pilot v0.1

Fusion exécutable des batches Claude : **Brique 01 Data/Evidence + screening projets + Brique 03 Eva**.

## Ce qui est déjà branché

- paie, bulletins PDF, temps PayFit, identité, contrôles et Evidence Hub ;
- personnel / assiette, screening projets et sous-traitance / MESR ;
- snapshot Dunasys 2025 inclus pour tester sans réimporter les pièces sensibles ;
- moteur Eva : banque de questions, machine à états, challenge, classification, transcript, synthèse ;
- mini interface web pour choisir un vrai projet Dunasys et conduire un entretien texte.

## Correctifs appliqués pendant la fusion

- bug `limites` du classifieur séparé en `limites_etat_art` et `limites_resultats` ;
- validation plus stricte de la sortie du classifieur LLM ;
- APEC sortie des cotisations éligibles par défaut ; titres-restaurant mis en `A_ARBITRER` ;
- création d'un `FicheProjet` commun entre les briques ;
- préqualification du personnel rendue prudente (`A_CONFIRMER`, `TO_REVIEW`) au lieu d'une décision fiscale automatique.

## Lancement le plus simple

Python 3.11+ recommandé.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Puis ouvrir : **http://localhost:3010**

Le fichier `data/DUNASYS_2025_brique01.xlsx` est chargé automatiquement. Choisir un projet, cliquer **Démarrer l'entretien**, répondre comme le CTO, puis **Finaliser**.

## Smoke test sans navigateur

```bash
python run_pilot.py
```

## Utiliser les fichiers sources réels

Le pipeline fusionné reste disponible dans `innovizer.pipeline.Brique01` :

```python
from innovizer import config
from innovizer.pipeline import Brique01

b = Brique01(config.DUNASYS_2025)
b.charger_paie("livre_de_paie.xlsx")
b.charger_bulletins("Bulletins/*Bulletin*.pdf")
b.charger_temps("time-tracking-export-2025-*.xlsx")
b.moteur_personnel().moteur_assiette().moteur_projets(None)
b.exporter("outputs/brique01.xlsx")
```

Les référentiels MESR peuvent encore être fournis en XLSX à `charger_referentiels_mesr`. Le connecteur API live MESR est la prochaine industrialisation, pas un prérequis pour tester le moteur.

## Voix

Cette version teste volontairement **le moteur métier avant la voix**. Les variables Vapi/OpenAI/ElevenLabs sont prévues dans `.env.example`, mais les clés privées ne sont pas incluses. Le prochain branchement est un bridge Vapi → endpoints d'entretien, sans déplacer la logique métier dans le prompt Vapi.

## Structure

```text
innovizer/
  config.py identity.py controls.py evidence.py pipeline.py
  ingest/paie.py bulletins.py temps.py
  engines/people.py assiette.py screening.py subcontracting.py fiche_projet.py
  brique03/questions.py classifier.py interview.py runtime.py
app.py              # interface web locale
run_pilot.py        # smoke test CLI
data/                # snapshot Dunasys + sessions JSON
```

## Limites assumées du pilote

- le Project Mapper intelligent n'est pas encore industrialisé : on part du screening projet existant ;
- le snapshot Brique 01 ne contient pas le détail personne × projet, donc l'UI snapshot connaît le nombre de collaborateurs mais pas leurs noms ; en ingestion brute, `contexte_depuis_brique01` récupère le détail ;
- la décision CIR/CII reste une **revue experte** : Eva mesure la couverture/defendabilité et collecte les preuves, elle ne délivre pas une validation fiscale automatique.
