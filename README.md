# Dashboard Treni v4

Treni monitorati:
- Andata: Regionale Veloce 4099, Figline Valdarno 07:00 → Arezzo 07:36, prosegue per Roma Tiburtina.
- Ritorno: Regionale 18774, Arezzo 18:08 → Figline Valdarno 18:48.

## Correzione live
Il workflow GitHub Actions gira ora tutti i giorni, sabato e domenica inclusi.
Prima era limitato a lunedì-venerdì: nei festivi il file live restava fermo e la PWA poteva mostrare "PROGRAMMATO" anche dopo la partenza.

Il backend controlla circa ogni 5 minuti nelle finestre mattina/sera. Se lo stato non cambia, pubblica comunque un heartbeat circa ogni 15 minuti. La PWA segnala chiaramente dati vecchi invece di presentarli come live.

## Installazione
Caricare tutti i file, compresa la cartella `.github`.
In GitHub: Settings → Actions → General → Workflow permissions → Read and write permissions.
In GitHub Pages usare branch `main`, root `/`.

Dopo l'upload aprire una volta `reset-treno-v4.html`, poi usare `treno-v4.html`.
