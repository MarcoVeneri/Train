#!/usr/bin/env python3
import json, re, sys, subprocess, time, urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASES = [
    "https://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno",
    "https://www.viaggiatreno.it/viaggiatrenonew/resteasy/viaggiatreno",
    "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno",
    "http://www.viaggiatreno.it/viaggiatrenonew/resteasy/viaggiatreno",
]
ROME = ZoneInfo("Europe/Rome")
OUT = Path("data/trains.json")

TRAINS = {
    "4099": ("FIGLINE VALDARNO", "AREZZO"),
    "18774": ("AREZZO", "FIGLINE VALDARNO"),
}
SCHEDULE = {
    "4099": {"departure": "07:00", "arrival": "07:36"},
    "18774": {"departure": "18:08", "arrival": "18:48"},
}

# Le vecchie finestre che funzionavano bene: il controllo parte prima del treno
# e continua per seguire eventuali variazioni. Sono attive 7 giorni su 7.
MONITOR_WINDOWS = {
    "4099": (6 * 60, 9 * 60 + 30),       # 06:00 - 09:30 Europe/Rome
    "18774": (17 * 60, 21 * 60),         # 17:00 - 21:00 Europe/Rome
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/154 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    "Referer": "https://www.viaggiatreno.it/infomobilita/index.jsp",
    "Origin": "https://www.viaggiatreno.it",
    "Cache-Control": "no-cache",
    "Connection": "close",
}


def now_iso():
    return datetime.now(ROME).isoformat(timespec="seconds")


def now_minutes():
    now = datetime.now(ROME)
    return now.hour * 60 + now.minute


def should_monitor(number):
    start, end = MONITOR_WINDOWS[number]
    minute = now_minutes()
    return start <= minute <= end


def _curl_text(url):
    cmd = [
        "curl", "--http1.1", "--fail", "--silent", "--show-error", "--location", "--compressed",
        "--connect-timeout", "10", "--max-time", "22", "--retry", "2", "--retry-delay", "1",
        "-A", HEADERS["User-Agent"],
        "-H", f"Accept: {HEADERS['Accept']}",
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
        "-H", f"Referer: {HEADERS['Referer']}",
        "-H", f"Origin: {HEADERS['Origin']}",
        "-H", f"Cache-Control: {HEADERS['Cache-Control']}",
        url,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or f"curl exit {p.returncode}").strip())
    return p.stdout


def _urllib_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=22) as r:
        return r.read().decode("utf-8", "replace")


def get_text_url(url):
    errors = []
    for getter in (_curl_text, _urllib_text):
        for attempt in range(2):
            try:
                text = getter(url)
                if text is None or not text.strip():
                    raise RuntimeError("risposta vuota")
                return text
            except Exception as e:
                errors.append(str(e))
                if attempt == 0:
                    time.sleep(1)
    raise RuntimeError("; ".join(errors[-3:]) or "sorgente non disponibile")


def api_text(path):
    errors = []
    for base in BASES:
        try:
            return get_text_url(base + path)
        except Exception as e:
            errors.append(f"{base}: {e}")
    raise RuntimeError(" | ".join(errors))


def api_json(path):
    text = api_text(path)
    if not text.strip():
        raise RuntimeError("risposta vuota")
    return json.loads(text)


def normalize(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.upper().replace(".", "").replace("’", "").replace("'", "")).strip()


def today_strings():
    now = datetime.now(ROME)
    return now.strftime("%d/%m/%y"), now.strftime("%Y-%m-%d")


def parse_autocomplete(line):
    m = re.search(r"(\d+)\s*-\s*([^|]+?)\s*-\s*(\d{2}/\d{2}/\d{2})\|(\d+)-(S\d{5})-(\d+)\s*$", line)
    if not m:
        return None
    return {
        "number": m.group(4),
        "originName": m.group(2).strip(),
        "date": m.group(3),
        "originCode": m.group(5),
        "departureMillis": m.group(6),
    }


def identity_for_today(number):
    today_short, today_iso = today_strings()
    txt = api_text(f"/cercaNumeroTrenoTrenoAutocomplete/{number}")
    items = [parse_autocomplete(x.strip()) for x in txt.splitlines() if x.strip()]
    items = [x for x in items if x]
    same_day = [x for x in items if x["date"] == today_short]
    if same_day:
        return same_day[0]

    one = api_json(f"/cercaNumeroTreno/{number}")
    if one and one.get("codLocOrig") and one.get("millisDataPartenza"):
        return {
            "number": str(number),
            "originName": one.get("descLocOrig"),
            "date": one.get("dataPartenza") or today_iso,
            "originCode": one["codLocOrig"],
            "departureMillis": str(one["millisDataPartenza"]),
        }
    raise RuntimeError(f"Treno {number} non trovato per oggi")


def find_stop(stops, name):
    n = normalize(name)
    for stop in stops:
        if normalize(stop.get("stazione")) == n:
            return stop
    for stop in stops:
        a = normalize(stop.get("stazione"))
        if a and (n in a or a in n):
            return stop
    return None


def hhmm(ms):
    if ms in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, ROME).strftime("%H:%M")
    except Exception:
        return None


def add_minutes(hm, mins):
    if not hm:
        return None
    h, m = map(int, hm.split(":"))
    total = (h * 60 + m + int(round(mins or 0))) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def pick_platform(stop):
    return (
        stop.get("binarioEffettivoPartenzaDescrizione")
        or stop.get("binarioProgrammatoPartenzaDescrizione")
        or stop.get("binarioEffettivoPartenzaCodice")
        or stop.get("binarioProgrammatoPartenzaCodice")
    )


def numeric_delay(values, default=0.0):
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value):
            return float(value)
    return float(default)


def train_data(number, from_name, to_name):
    ident = identity_for_today(number)
    detail = api_json(f"/andamentoTreno/{ident['originCode']}/{number}/{ident['departureMillis']}")
    stops = detail.get("fermate") or []
    fr = find_stop(stops, from_name)
    to = find_stop(stops, to_name)
    if not fr or not to:
        raise RuntimeError(f"Fermate non trovate per {number}")

    departure_scheduled = hhmm(fr.get("partenza_teorica") or fr.get("programmata"))
    boarding_arrival_scheduled = hhmm(fr.get("arrivo_teorico") or fr.get("programmata")) or departure_scheduled
    destination_arrival_scheduled = hhmm(to.get("arrivo_teorico") or to.get("programmata"))
    departure_actual = hhmm(fr.get("partenzaReale") or fr.get("effettiva"))
    boarding_arrival_actual = hhmm(fr.get("arrivoReale"))
    destination_arrival_actual = hhmm(to.get("arrivoReale") or to.get("effettiva"))

    # Le metriche sono riferite alla stazione dove si sale:
    # 4099 a Figline, 18774 ad Arezzo. Prima della partenza usiamo il ritardo
    # corrente del convoglio come migliore stima di arrivo alla stazione di salita.
    if departure_actual:
        boarding_candidates = [fr.get("ritardoPartenza"), fr.get("ritardo"), detail.get("ritardo")]
    else:
        boarding_candidates = [detail.get("ritardo"), fr.get("ritardo"), fr.get("ritardoPartenza")]
    boarding_delay = numeric_delay(boarding_candidates, 0)

    if destination_arrival_actual:
        destination_candidates = [to.get("ritardoArrivo"), to.get("ritardo"), detail.get("ritardo")]
    else:
        destination_candidates = [detail.get("ritardo"), to.get("ritardo"), to.get("ritardoArrivo")]
    destination_delay = numeric_delay(destination_candidates, boarding_delay)

    cancelled = (
        detail.get("tipoTreno") == "ST"
        or fr.get("actualFermataType") == 3
        or to.get("actualFermataType") == 3
    )
    train_started = bool(detail.get("oraUltimoRilevamento"))
    departed_from_boarding = bool(departure_actual)

    if cancelled:
        status = "CANCELLED"
    elif departed_from_boarding:
        status = "DEPARTED"
    elif boarding_delay > 0:
        status = "DELAYED"
    else:
        status = "ON_TIME"

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
        "liveAvailable": True,
        "staleLive": False,
        "provisional": False,
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
        "verifiedAt": now_iso(),
        "source": "ViaggiaTreno",
    }


def load_previous():
    try:
        return json.loads(OUT.read_text("utf-8"))
    except Exception:
        return {"trains": {}}


def has_verified_snapshot(old, today_iso):
    if not old or old.get("dataDate") != today_iso or old.get("provisional") is True:
        return False
    if old.get("liveAvailable") is not True:
        return False
    return bool(
        old.get("verifiedAt")
        or old.get("sourceTimestamp")
        or old.get("departureActual")
        or old.get("arrivalActual")
    )


def baseline_payload(number, fr, to, error=None):
    _, today_iso = today_strings()
    schedule = SCHEDULE[number]
    dep = schedule["departure"]
    arr = schedule["arrival"]
    payload = {
        "number": number,
        "from": fr,
        "to": to,
        "status": "ON_TIME",
        "cancelled": False,
        "started": False,
        "trainStarted": False,
        "liveAvailable": True,
        "staleLive": False,
        "provisional": True,
        "delayMinutes": 0,
        "boardingDelayMinutes": 0,
        "destinationDelayMinutes": 0,
        "departureScheduled": dep,
        "departureExpected": dep,
        "departureActual": None,
        "boardingArrivalScheduled": dep,
        "boardingArrivalExpected": dep,
        "boardingArrivalActual": None,
        "arrivalScheduled": arr,
        "arrivalExpected": arr,
        "arrivalActual": None,
        "platform": None,
        "lastDetection": None,
        "sourceTimestamp": None,
        "dataDate": today_iso,
        "source": "Programma · controllo automatico",
    }
    if error is not None:
        payload["fetchError"] = str(error)
        payload["lastAttemptAt"] = now_iso()
    return payload


def unavailable_payload(number, fr, to, error, old=None):
    _, today_iso = today_strings()
    old = old or {}

    # Un errore temporaneo non cancella mai un dato già verificato oggi.
    if has_verified_snapshot(old, today_iso):
        kept = dict(old)
        kept["liveAvailable"] = True
        kept["staleLive"] = True
        kept["fetchError"] = str(error)
        kept["lastAttemptAt"] = now_iso()
        kept["source"] = "ViaggiaTreno · ultimo dato verificato"
        return kept

    # Prima del primo dato live del giorno si mantiene il comportamento storico:
    # orario programmato = IN ORARIO, mentre il controllo automatico continua.
    return baseline_payload(number, fr, to, error)


def main():
    previous = load_previous()
    _, today_iso = today_strings()
    current = {"dataDate": today_iso, "trains": {}}
    successes = 0
    retained = 0
    monitored = 0

    for number, (fr, to) in TRAINS.items():
        old = (previous.get("trains") or {}).get(number)

        # Fuori dalla finestra live non interroghiamo inutilmente ViaggiaTreno.
        # A mezzanotte, non essendoci ancora un record di oggi, questo crea il
        # nuovo baseline IN ORARIO e cancella naturalmente i ritardi di ieri.
        if not should_monitor(number):
            if old and old.get("dataDate") == today_iso:
                current["trains"][number] = old
            else:
                current["trains"][number] = baseline_payload(number, fr, to)
            continue

        monitored += 1
        try:
            current["trains"][number] = train_data(number, fr, to)
            successes += 1
            print(f"{number}: LIVE OK")
        except Exception as e:
            print(f"{number}: LIVE NON DISPONIBILE: {e}", file=sys.stderr)
            payload = unavailable_payload(number, fr, to, e, old)
            current["trains"][number] = payload
            if payload.get("staleLive"):
                retained += 1

    current["generatedAt"] = now_iso()
    current["liveSuccessCount"] = successes
    current["retainedVerifiedCount"] = retained
    current["monitoredTrainCount"] = monitored
    current["liveComplete"] = monitored == 0 or successes == monitored
    current["monitorWeekendEnabled"] = True
    current["monitorMode"] = "commuter-windows-5min"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(
        f"Aggiornato {OUT}: {successes}/{monitored} live nella finestra, "
        f"{retained} snapshot verificati mantenuti"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
