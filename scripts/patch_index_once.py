from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")

# Forza la nuova logica sull'iPhone/PWA.
s = s.replace('const UI_BUILD="51";', 'const UI_BUILD="52";')

# A mezzanotte il giorno riparte dagli orari programmati e da IN ORARIO.
s = s.replace(
''' ui.outStatus.textContent="IN ATTESA"; statusClass(ui.outStatus,"neutral");
 ui.backStatus.textContent="IN ATTESA"; statusClass(ui.backStatus,"neutral");

 ui.outPunctuality.textContent="A FIGLINE · ATTESA DATI";
 ui.outPunctuality.className="punctuality neutral";
 ui.backPunctuality.textContent="AD AREZZO · ATTESA DATI";
 ui.backPunctuality.className="punctuality neutral";''',
''' ui.outStatus.textContent="IN ORARIO"; statusClass(ui.outStatus,"ok");
 ui.backStatus.textContent="IN ORARIO"; statusClass(ui.backStatus,"ok");

 ui.outPunctuality.textContent="A FIGLINE · IN ORARIO";
 ui.outPunctuality.className="punctuality ok";
 ui.backPunctuality.textContent="AD AREZZO · IN ORARIO";
 ui.backPunctuality.className="punctuality ok";'''
)

s = s.replace(
''' for(const el of [ui.outBoardDelta,ui.outDestDelta,ui.backBoardDelta,ui.backDestDelta]){
   el.textContent="attesa dati";
   el.className="timing-delta";
 }
 ui.outLive.textContent="In attesa del primo controllo ViaggiaTreno di oggi";
 ui.backLive.textContent="In attesa del primo controllo ViaggiaTreno di oggi";''',
''' for(const el of [ui.outBoardDelta,ui.outDestDelta,ui.backBoardDelta,ui.backDestDelta]){
   el.textContent="in orario";
   el.className="timing-delta ok";
 }
 ui.outLive.textContent="Controllo automatico prima della partenza";
 ui.backLive.textContent="Controllo automatico prima della partenza";'''
)

# Se la pagina è aperta durante il cambio giorno, il reset è silenzioso e pulito.
s = s.replace(
''' if(staleDay){
   resetForNewDay();
   ui.notice.textContent="Nuovo giorno · in attesa dei dati live di oggi.";
   ui.notice.classList.add("show");
   return data;
 }''',
''' if(staleDay){
   resetForNewDay();
   ui.notice.classList.remove("show");
   return data;
 }'''
)

s = s.replace(
'''   resetForNewDay();
   ui.notice.textContent="Nuovo giorno · in attesa dei dati live di oggi.";
   ui.notice.classList.add("show");
   refreshAll();''',
'''   resetForNewDay();
   ui.notice.classList.remove("show");
   refreshAll();'''
)

# Un baseline programmato non è un errore live: resta IN ORARIO finché parte la scansione.
s = s.replace(
''' if(d?.staleLive||d?.fetchError)bits.push("ultimo dato verificato mantenuto · nuovo controllo in corso");
 live.textContent=bits.length?bits.join(" · "):"Stato live ViaggiaTreno";''',
''' if(d?.provisional)bits.push("controllo automatico prima della partenza");
 else if(d?.staleLive||d?.fetchError)bits.push("ultimo dato verificato mantenuto · nuovo controllo in corso");
 live.textContent=bits.length?bits.join(" · "):"Stato live ViaggiaTreno";'''
)

old = ''' const age=dataAgeMinutes(data?.generatedAt);
 const hardSourceFailed=Object.values(data?.trains||{}).some(x=>x?.liveAvailable===false || (x?.dataDate && x.dataDate!==todayRome()));
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
new = ''' const age=dataAgeMinutes(data?.generatedAt);
 const hardSourceFailed=Object.values(data?.trains||{}).some(x=>x?.liveAvailable===false || (x?.dataDate && x.dataDate!==todayRome()));
 const provisional=Object.values(data?.trains||{}).some(x=>x?.provisional===true);
 const nowParts=romeDateParts();
 const hm=Number(nowParts.hour)*60+Number(nowParts.minute);
 const activeWindow=(hm>=360&&hm<=570)||(hm>=1020&&hm<=1260);
 if(hardSourceFailed){
   ui.notice.textContent="Dati live momentaneamente non disponibili.";
   ui.notice.classList.add("show");
 }else if(age>25 && activeWindow && !provisional){
   ui.notice.textContent=`Ultimo controllo ferroviario ${Math.round(age)} minuti fa.`;
   ui.notice.classList.add("show");
   for(const el of [ui.outStatus,ui.backStatus]){
     if(el.textContent==="IN ORARIO"){el.textContent="DATI NON LIVE";statusClass(el,"delay")}
   }
 }else{ui.notice.classList.remove("show")}'''
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
