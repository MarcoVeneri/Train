# Dashboard Treni Figline ↔ Arezzo

Dashboard web/PWA nello stile Apple Glass per:

- **Andata:** treno **18739**, Figline Valdarno → Arezzo
- **Ritorno:** treno **18776**, Arezzo → Figline Valdarno
- meteo Figline/Arezzo utile per il monopattino
- aggiornamento automatico predefinito ogni **2 minuti**
- stato evidente: in orario / ritardo / soppresso
- binario quando disponibile
- tema chiaro/scuro automatico
- layout iPhone e iPad

## Perché c'è una cartella `worker`

La pagina GitHub Pages è HTTPS, mentre l'endpoint ViaggiaTreno usato per i dati live è una API non ufficialmente documentata e viene normalmente esposta via HTTP. Per evitare problemi di mixed-content/CORS la dashboard usa un piccolo **Cloudflare Worker** come proxy.

Le API ViaggiaTreno sono state ricostruite tramite reverse engineering e possono cambiare; per questo il Worker isola tutta la parte ferroviaria dal layout.

## 1. Pubblica la dashboard su GitHub Pages

Carica nella root del repository:

- `index.html`
- `manifest.webmanifest`
- `icon.svg`
- `.nojekyll`

Poi in GitHub:
`Settings → Pages → Deploy from a branch → main → / (root)`.

## 2. Pubblica il Worker Cloudflare

Metodo semplice:

1. crea un account Cloudflare se non lo hai;
2. vai in **Workers & Pages → Create → Worker**;
3. sostituisci il codice con `worker/worker.js`;
4. pubblica;
5. otterrai un URL simile a:
   `https://figline-arezzo-trains.nomeutente.workers.dev`
6. apri quell'URL aggiungendo `/health` e verifica che risponda con `"ok": true`.

In alternativa, con Wrangler:

```bash
cd worker
npx wrangler deploy
```

## 3. Collega il Worker alla dashboard

Apri la dashboard sul telefono:

1. premi **⚙︎**
2. incolla l'URL HTTPS del Worker
3. lascia `2` minuti come aggiornamento
4. premi **Salva e verifica**

L'URL viene memorizzato nel browser del dispositivo.

## Meteo

Il meteo usa Open-Meteo direttamente dal browser e non richiede chiavi API.

La dashboard mostra:
- mattina: Figline + Arezzo
- sera: Arezzo + Figline

## Installazione su iPhone

In Safari:
**Condividi → Aggiungi a Home**.

Non è incluso un Service Worker: è una scelta voluta per evitare che iOS conservi vecchie versioni dopo gli aggiornamenti del repository.

## Nota sui dati ferroviari

ViaggiaTreno consente di ottenere numero treno, fermate, ritardo, binari e stato del convoglio. L'integrazione usata qui non è un'API pubblica/supportata ufficialmente: se Trenitalia cambia gli endpoint, può essere necessario aggiornare `worker/worker.js`.
