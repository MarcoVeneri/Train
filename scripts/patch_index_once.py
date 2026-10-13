from pathlib import Path

TARGETS = [Path("index.html"), Path("treno-v4.html")]

for p in TARGETS:
    s = p.read_text(encoding="utf-8")

    # Forza refresh della PWA per la correzione del treno sostitutivo.
    s = s.replace('const UI_BUILD="53";', 'const UI_BUILD="54";')

    # Il numero del treno deve essere dinamico: durante i lavori il 4099 è
    # sostituito dal 34221 e dal 5 dicembre torna automaticamente 4099.
    s = s.replace(
        '<div class="train-number"><span class="train-glyph">🚆</span><span>4099</span></div>',
        '<div class="train-number"><span class="train-glyph">🚆</span><span id="outTrainNumber">4099</span></div>'
    )
    s = s.replace(
        '<div class="train-number"><span class="train-glyph">🚆</span><span>18774</span></div>',
        '<div class="train-number"><span class="train-glyph">🚆</span><span id="backTrainNumber">18774</span></div>'
    )

    s = s.replace(
        ' outDeparture:$("#outDeparture"),outStatus:',
        ' outTrainNumber:$("#outTrainNumber"),outDeparture:$("#outDeparture"),outStatus:'
    )
    s = s.replace(
        ' backDeparture:$("#backDeparture"),backStatus:',
        ' backTrainNumber:$("#backTrainNumber"),backDeparture:$("#backDeparture"),backStatus:'
    )

    s = s.replace(
'''function resetForNewDay(){
 ui.outDeparture.textContent="07:00";
 ui.backDeparture.textContent="18:08";''',
'''function resetForNewDay(){
 const today=todayRome();
 const replacement=today>="2026-10-12" && today<="2026-12-04";
 ui.outTrainNumber.textContent=replacement?"34221":"4099";
 ui.backTrainNumber.textContent="18774";
 ui.outDeparture.textContent=replacement?"06:55":"07:00";
 ui.backDeparture.textContent="18:08";'''
    )

    s = s.replace(
''' ui.outBoardTime.textContent="07:00";
 ui.outDestTime.textContent="07:36";''',
''' ui.outBoardTime.textContent=replacement?"06:55":"07:00";
 ui.outDestTime.textContent=replacement?"07:31":"07:36";'''
    )

    s = s.replace(
''' inf=key==="out"?ui.outInfo:ui.backInfo, live=key==="out"?ui.outLive:ui.backLive;
 if(d?.departureScheduled)dep.textContent=d.departureScheduled;''',
''' inf=key==="out"?ui.outInfo:ui.backInfo, live=key==="out"?ui.outLive:ui.backLive;
 const trainNumberEl=key==="out"?ui.outTrainNumber:ui.backTrainNumber;
 if(d?.number)trainNumberEl.textContent=d.number;
 if(d?.departureScheduled)dep.textContent=d.departureScheduled;'''
    )

    # Imposta subito il numero/orario corretto anche prima del primo fetch live.
    s = s.replace(
'''setGreeting();
setInterval(setGreeting,60000);''',
'''setGreeting();
resetForNewDay();
setInterval(setGreeting,60000);'''
    )

    p.write_text(s, encoding="utf-8")

manifest = Path("manifest.webmanifest")
m = manifest.read_text(encoding="utf-8")
m = m.replace('"start_url": "./treno-v4.html?build=53"', '"start_url": "./treno-v4.html?build=54"')
m = m.replace('Dashboard automatica per i treni 4099 e 18774 tra Figline Valdarno e Arezzo.',
              'Dashboard automatica per i collegamenti pendolari tra Figline Valdarno e Arezzo.')
manifest.write_text(m, encoding="utf-8")
