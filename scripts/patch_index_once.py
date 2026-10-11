from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')

# Forza il nuovo frontend sull'iPhone/PWA.
s=s.replace('const UI_BUILD="50";','const UI_BUILD="51";')

# Un errore temporaneo dell'ultimo tentativo non invalida uno snapshot live già
# verificato oggi. Il dato diventa davvero non-live solo se liveAvailable è false
# oppure appartiene a un altro giorno.
s=s.replace(
    'const staleSource=!!d?.fetchError || d?.liveAvailable===false || (d?.dataDate && d.dataDate!==todayRome());',
    'const staleSource=d?.liveAvailable===false || (d?.dataDate && d.dataDate!==todayRome());'
)

# Sostituisce il messaggio tecnico/alarmistico sulla singola card con una nota
# breve quando viene mantenuto l’ultimo dato verificato.
s=s.replace(
    'if(d?.fetchError)bits.push("ultimo aggiornamento live non riuscito");',
    'if(d?.staleLive||d?.fetchError)bits.push("ultimo dato verificato mantenuto · nuovo controllo in corso");'
)

old=''' const sourceFailed=Object.values(data?.trains||{}).some(x=>x?.fetchError || x?.liveAvailable===false || (x?.dataDate && x.dataDate!==todayRome()));
 if(sourceFailed){
   ui.notice.textContent="Controllo live ViaggiaTreno non riuscito: non mostro più ‘in orario’ se il dato non è verificato. Riprovo automaticamente ogni 5 minuti.";
   ui.notice.classList.add("show");
 }else if(age>25){
   ui.notice.textContent=`ATTENZIONE: ultimo controllo ferroviario ${Math.round(age)} minuti fa.`;
   ui.notice.classList.add("show");
   for(const el of [ui.outStatus,ui.backStatus]){
     if(el.textContent==="IN ORARIO"){el.textContent="DATI NON LIVE";statusClass(el,"delay")}
   }
 }else{ui.notice.classList.remove("show")}'''
new=''' const hardSourceFailed=Object.values(data?.trains||{}).some(x=>x?.liveAvailable===false || (x?.dataDate && x.dataDate!==todayRome()));
 if(hardSourceFailed){
   ui.notice.textContent="Dati live momentaneamente non disponibili.";
   ui.notice.classList.add("show");
 }else if(age>25){
   ui.notice.textContent=`Ultimo controllo ferroviario ${Math.round(age)} minuti fa.`;
   ui.notice.classList.add("show");
   for(const el of [ui.outStatus,ui.backStatus]){
     if(el.textContent==="IN ORARIO"){el.textContent="DATI NON LIVE";statusClass(el,"delay")}
   }
 }else{ui.notice.classList.remove("show")}'''
if old in s:
    s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
