#!/usr/bin/env python3
import json, re, sys, urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"
ROME = ZoneInfo("Europe/Rome")
OUT = Path("data/trains.json")
TRAINS = {
    "18739": ("FIGLINE VALDARNO", "AREZZO"),
    "18776": ("AREZZO", "FIGLINE VALDARNO"),
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
    arrival_scheduled = hhmm(to.get("arrivo_teorico") or to.get("programmata"))
    departure_actual = hhmm(fr.get("partenzaReale") or fr.get("effettiva"))
    arrival_actual = hhmm(to.get("arrivoReale") or to.get("effettiva"))

    candidates = [fr.get("ritardoPartenza"), fr.get("ritardo"), detail.get("ritardo")]
    delay = next((float(v) for v in candidates if isinstance(v,(int,float)) or (isinstance(v,str) and re.fullmatch(r"-?\d+(\.\d+)?",v))), 0.0)
    cancelled = detail.get("tipoTreno") == "ST" or fr.get("actualFermataType") == 3 or to.get("actualFermataType") == 3
    started = bool(departure_actual or detail.get("oraUltimoRilevamento"))

    if cancelled: status = "CANCELLED"
    elif arrival_actual: status = "ARRIVED"
    elif started and delay > 0: status = "DELAYED"
    elif started: status = "ON_TIME"
    elif delay > 0: status = "DELAYED"
    else: status = "NOT_STARTED"

    expected = arrival_actual or add_minutes(arrival_scheduled, delay)
    _, today_iso = today_strings()
    return {
        "number": str(number),
        "from": fr.get("stazione") or from_name,
        "to": to.get("stazione") or to_name,
        "status": status,
        "cancelled": bool(cancelled),
        "started": bool(started),
        "delayMinutes": max(0, round(delay)),
        "departureScheduled": departure_scheduled,
        "departureActual": departure_actual,
        "arrivalScheduled": arrival_scheduled,
        "arrivalExpected": expected,
        "arrivalActual": arrival_actual,
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
                    "number":number,"from":fr,"to":to,"status":"NOT_STARTED","cancelled":False,"started":False,
                    "delayMinutes":0,
                    "departureScheduled":"07:04" if number=="18739" else "19:08",
                    "arrivalScheduled":"07:54" if number=="18739" else "19:48",
                    "arrivalExpected":"07:54" if number=="18739" else "19:48",
                    "platform":None,"dataDate":today_strings()[1],"fetchError":str(e),"source":"ViaggiaTreno"
                }

    # Scrive solo quando i dati significativi cambiano: evita centinaia di commit inutili.
    if stable_payload(current) == stable_payload(previous) and previous.get("dataDate") == current.get("dataDate"):
        print("Nessuna variazione: file invariato.")
        return 0

    current["generatedAt"] = datetime.now(ROME).isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("Aggiornato", OUT)
    return 0 if had_success or previous.get("trains") else 1

if __name__ == "__main__":
    raise SystemExit(main())
