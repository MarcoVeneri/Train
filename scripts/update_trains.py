#!/usr/bin/env python3
import json, re, sys, urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"
ROME = ZoneInfo("Europe/Rome")
OUT = Path("data/trains.json")
TRAINS = {
    "4099": ("FIGLINE VALDARNO", "AREZZO"),
    "18774": ("AREZZO", "FIGLINE VALDARNO"),
}

def get_text(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 GitHubActions TrainDashboard/2.0",
        "Accept": "application/json,text/plain,*/*"
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def get_json(url):
    return json.loads(get_text(url))

def normalize(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.upper().replace(".", "").replace("’","").replace("'","")).strip()

def today_strings():
    now = datetime.now(ROME)
    return now.strftime("%d/%m/%y"), now.strftime("%Y-%m-%d")

def parse_autocomplete(line):
    # Esempio:
    # 3041 - MILANO ROGOREDO - 22/07/25|3041-S01820-1753135200000
    m = re.search(r"(\d+)\s*-\s*([^|]+?)\s*-\s*(\d{2}/\d{2}/\d{2})\|(\d+)-(S\d{5})-(\d+)\s*$", line)
    if not m:
        return None
    return {"number": m.group(4), "originName": m.group(2).strip(), "date": m.group(3),
            "originCode": m.group(5), "departureMillis": m.group(6)}

def identity_for_today(number):
    today_short, today_iso = today_strings()
    txt = get_text(f"{BASE}/cercaNumeroTrenoTrenoAutocomplete/{number}")
    items = [parse_autocomplete(x.strip()) for x in txt.splitlines() if x.strip()]
    items = [x for x in items if x]
    same_day = [x for x in items if x["date"] == today_short]
    if same_day:
        return same_day[0]
    # fallback dell'endpoint singolo
    one = get_json(f"{BASE}/cercaNumeroTreno/{number}")
    if one and one.get("codLocOrig") and one.get("millisDataPartenza"):
        return {"number": str(number), "originName": one.get("descLocOrig"), "date": one.get("dataPartenza") or today_iso,
                "originCode": one["codLocOrig"], "departureMillis": str(one["millisDataPartenza"])}
    raise RuntimeError(f"Treno {number} non trovato per oggi")

def find_stop(stops, name):
    n = normalize(name)
    for s in stops:
        if normalize(s.get("stazione")) == n:
            return s
    for s in stops:
        a = normalize(s.get("stazione"))
        if a and (n in a or a in n):
            return s
    return None

def hhmm(ms):
    if ms in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(ms)/1000, ROME).strftime("%H:%M")
    except Exception:
        return None

def add_minutes(hm, mins):
    if not hm:
        return None
    h,m = map(int,hm.split(":"))
    total = (h*60+m+int(round(mins or 0)))%(24*60)
    return f"{total//60:02d}:{total%60:02d}"

def pick_platform(stop):
    return (stop.get("binarioEffettivoPartenzaDescrizione")
            or stop.get("binarioProgrammatoPartenzaDescrizione")
            or stop.get("binarioEffettivoPartenzaCodice")
            or stop.get("binarioProgrammatoPartenzaCodice"))

def train_data(number, from_name, to_name):
    ident = identity_for_today(number)
    detail = get_json(f"{BASE}/andamentoTreno/{ident['originCode']}/{number}/{ident['departureMillis']}")
    stops = detail.get("fermate") or []
    fr, to = find_stop(stops, from_name), find_stop(stops, to_name)
    if not fr or not to:
        raise RuntimeError(f"Fermate non trovate per {number}")

    departure_scheduled = hhmm(fr.get("partenza_teorica") or fr.get("programmata"))
    boarding_arrival_scheduled = hhmm(fr.get("arrivo_teorico") or fr.get("programmata")) or departure_scheduled
    destination_arrival_scheduled = hhmm(to.get("arrivo_teorico") or to.get("programmata"))
    departure_actual = hhmm(fr.get("partenzaReale") or fr.get("effettiva"))
    boarding_arrival_actual = hhmm(fr.get("arrivoReale"))
    destination_arrival_actual = hhmm(to.get("arrivoReale") or to.get("effettiva"))

    # Ritardo riferito alla stazione dove Marco sale.
    # Se ViaggiaTreno non fornisce ancora il ritardo specifico della fermata,
    # usiamo il ritardo corrente del convoglio come migliore stima disponibile.
    # Prima che il treno lasci la stazione di salita, il dato più utile è il
    # ritardo corrente del convoglio: è la migliore stima di come arriverà a
    # Figline/Arezzo. Dopo la partenza dalla stazione usiamo invece il ritardo
    # specifico registrato a quella fermata.
    if departure_actual:
        boarding_candidates = [fr.get("ritardoPartenza"), fr.get("ritardo"), detail.get("ritardo")]
    else:
        boarding_candidates = [detail.get("ritardo"), fr.get("ritardo"), fr.get("ritardoPartenza")]
    boarding_delay = next((float(v) for v in boarding_candidates if isinstance(v,(int,float)) or (isinstance(v,str) and re.fullmatch(r"-?\d+(\.\d+)?",v))), 0.0)

    # Per la destinazione, dopo la salita usiamo il ritardo corrente del convoglio:
    # può aumentare o diminuire durante il viaggio.
    if destination_arrival_actual:
        destination_candidates = [to.get("ritardoArrivo"), to.get("ritardo"), detail.get("ritardo")]
    else:
        destination_candidates = [detail.get("ritardo"), to.get("ritardo"), to.get("ritardoArrivo")]
    destination_delay = next((float(v) for v in destination_candidates if isinstance(v,(int,float)) or (isinstance(v,str) and re.fullmatch(r"-?\d+(\.\d+)?",v))), boarding_delay)

    cancelled = detail.get("tipoTreno") == "ST" or fr.get("actualFermataType") == 3 or to.get("actualFermataType") == 3
    train_started = bool(detail.get("oraUltimoRilevamento"))
    departed_from_boarding = bool(departure_actual)

    if cancelled: status = "CANCELLED"
    elif departed_from_boarding: status = "DEPARTED"
    elif boarding_delay > 0: status = "DELAYED"
    else: status = "ON_TIME"

    departure_expected = departure_actual or add_minutes(departure_scheduled, boarding_delay)
    boarding_arrival_expected = boarding_arrival_actual or add_minutes(boarding_arrival_scheduled, boarding_delay)
    destination_arrival_expected = destination_arrival_actual or add_minutes(destination_arrival_scheduled, destination_delay)
    _, today_iso = today_strings()
    return {
        "number": str(number),
        "from": fr.get("stazione") or from_name,
        "to": to.get("stazione") or to_name,
        "status": status,
        "cancelled": bool(cancelled),
        "started": bool(departed_from_boarding),
        "trainStarted": bool(train_started),
        "delayMinutes": round(boarding_delay),
        "boardingDelayMinutes": round(boarding_delay),
        "destinationDelayMinutes": round(destination_delay),
        "departureScheduled": departure_scheduled,
        "departureExpected": departure_expected,
        "departureActual": departure_actual,
        "boardingArrivalScheduled": boarding_arrival_scheduled,
        "boardingArrivalExpected": boarding_arrival_expected,
        "boardingArrivalActual": boarding_arrival_actual,
        "arrivalScheduled": destination_arrival_scheduled,
        "arrivalExpected": destination_arrival_expected,
        "arrivalActual": destination_arrival_actual,
        "platform": pick_platform(fr),
        "lastDetection": detail.get("stazioneUltimoRilevamento"),
        "sourceTimestamp": detail.get("oraUltimoRilevamento"),
        "dataDate": today_iso,
        "source": "ViaggiaTreno"
    }

def load_previous():
    try:
        return json.loads(OUT.read_text("utf-8"))
    except Exception:
        return {"trains":{}}

def stable_payload(obj):
    # Non includere campi puramente tecnici per decidere se i dati sono realmente cambiati.
    def clean(v):
        if isinstance(v, dict):
            return {k:clean(x) for k,x in sorted(v.items()) if k not in {"fetchError"}}
        if isinstance(v, list): return [clean(x) for x in v]
        return v
    return clean(obj.get("trains",{}))

def main():
    previous = load_previous()
    current = {"dataDate": today_strings()[1], "trains":{}}
    had_success = False

    for number,(fr,to) in TRAINS.items():
        try:
            current["trains"][number] = train_data(number,fr,to)
            had_success = True
            print(f"{number}: OK")
        except Exception as e:
            print(f"{number}: ERRORE: {e}", file=sys.stderr)
            old = (previous.get("trains") or {}).get(number)
            if old:
                old = dict(old)
                old["fetchError"] = str(e)
                current["trains"][number] = old
            else:
                current["trains"][number] = {
                    "number":number,"from":fr,"to":to,"status":"ON_TIME","cancelled":False,"started":False,"trainStarted":False,
                    "delayMinutes":0,"boardingDelayMinutes":0,
                    "departureScheduled":"07:00" if number=="4099" else "18:08",
                    "departureExpected":"07:00" if number=="4099" else "18:08",
                    "boardingArrivalScheduled":"07:00" if number=="4099" else "18:08",
                    "boardingArrivalExpected":"07:00" if number=="4099" else "18:08",
                    "destinationDelayMinutes":0,
                    "arrivalScheduled":"07:36" if number=="4099" else "18:48",
                    "arrivalExpected":"07:36" if number=="4099" else "18:48",
                    "platform":None,"dataDate":today_strings()[1],"fetchError":str(e),"source":"ViaggiaTreno"
                }

    now = datetime.now(ROME)
    # Ogni esecuzione schedulata produce un heartbeat reale.
    # Il workflow gira ogni 5 minuti nelle finestre di pendolarismo.
    current["generatedAt"] = now.isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("Aggiornato", OUT)
    return 0 if had_success or previous.get("trains") else 1

if __name__ == "__main__":
    raise SystemExit(main())
