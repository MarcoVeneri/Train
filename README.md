# Dashboard Treni — SOLO GitHub

Questa versione **non richiede Cloudflare, API key o altri account**.

Funziona così:

1. GitHub Pages pubblica `index.html`.
2. GitHub Actions esegue automaticamente `scripts/update_trains.py`.
3. Lo script interroga ViaggiaTreno dal server GitHub e aggiorna `data/trains.json`.
4. La dashboard legge quel file.
5. Il meteo arriva direttamente da Open-Meteo.

## Treni configurati

- 18739 — Figline Valdarno → Arezzo
- 18776 — Arezzo → Figline Valdarno

## Cosa deve fare chi usa l'app

Nulla: apre il link e basta. Su iPhone può fare **Condividi → Aggiungi a Home**.

## Installazione su GitHub

Carica **tutto** il contenuto di questa cartella nel repository, compresa la cartella nascosta:

`.github/workflows/update-trains.yml`

Poi attiva GitHub Pages normalmente da:

`Settings → Pages → Deploy from a branch → main → / (root)`

La GitHub Action parte anche quando carichi inizialmente questi file; in seguito controlla i treni automaticamente ogni circa 5 minuti nelle fasce del pendolarismo dei giorni feriali.

### Se GitHub mostra che il workflow non può scrivere

Solo in quel caso:
`Settings → Actions → General → Workflow permissions → Read and write permissions`.

Nessun altro servizio è necessario.

## Nota tecnica

Le API di ViaggiaTreno usate dal workflow sono endpoint non documentati ufficialmente e possono cambiare in futuro. La dashboard mantiene comunque gli orari programmati se il servizio live non risponde.
