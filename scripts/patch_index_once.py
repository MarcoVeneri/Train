from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")

# Forza refresh della PWA dopo la correzione dello stato dei treni conclusi.
s = s.replace('const UI_BUILD="52";', 'const UI_BUILD="53";')

# Uno stato DEPARTED/started resta "PARTITO" per tutta la giornata anche se
# l'endpoint live non espone più la corsa dopo la conclusione.
s = s.replace(
''' const staleSource=d?.liveAvailable===false || (d?.dataDate && d.dataDate!==todayRome());
 if(staleSource){''',
''' const staleSource=d?.liveAvailable===false || (d?.dataDate && d.dataDate!==todayRome());
 const departed=Boolean(d?.departureActual || d?.started===true || d?.status==="DEPARTED");
 if(staleSource && !departed){'''
)

s = s.replace(
''' else if(d?.departureActual){
   txt=boardingDelay>0?`PARTITO +${Math.round(boardingDelay)}`:"PARTITO";
   cls=boardingDelay>=15?"bad":boardingDelay>0?"delay":"ok";
 }''',
''' else if(departed){
   txt=boardingDelay>0?`PARTITO +${Math.round(boardingDelay)}`:"PARTITO";
   cls=boardingDelay>=15?"bad":boardingDelay>0?"delay":"ok";
 }'''
)

s = s.replace(
''' if(d?.departureActual)bits.push(`Partenza effettiva ${d.departureActual}`);
 else if(d?.trainStarted && d?.lastDetection)bits.push(`Treno in viaggio · ultimo rilevamento: ${d.lastDetection}`);''',
''' if(d?.departureActual)bits.push(`Partenza effettiva ${d.departureActual}`);
 else if(departed && d?.boardingArrivalActual)bits.push(`Partito · passaggio alla stazione di salita ${d.boardingArrivalActual}`);
 else if(departed)bits.push("Partito");
 else if(d?.trainStarted && d?.lastDetection)bits.push(`Treno in viaggio · ultimo rilevamento: ${d.lastDetection}`);'''
)

p.write_text(s, encoding="utf-8")
