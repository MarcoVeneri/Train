#!/usr/bin/env python3
"""Runtime compatibility layer for the continuous Train monitor.

Keeps both commuter trains checked every cycle, preserves the last verified state
on temporary source errors, and maps temporary replacement train numbers caused
by planned infrastructure works without changing the logical PWA slot.
"""
from datetime import date, datetime

import update_trains as core


# The continuous 5-minute monitor checks both logical commuter slots every cycle.
# This lets the app recover a missed/final state later in the same day.
core.should_monitor = lambda _number: True


# RFI planned works: RV 4099 is cancelled from 12 Oct to 4 Dec 2026 and is
# replaced by RV 34221. At Figline the replacement departs 06:55 and reaches
# Arezzo at 07:31. From 5 Dec the normal 4099 mapping is used again automatically.
REPLACEMENTS = {
    "4099": {
        "from": date(2026, 10, 12),
        "to": date(2026, 12, 4),
        "number": "34221",
        "departure": "06:55",
        "arrival": "07:31",
    }
}


def today_rome():
    return datetime.now(core.ROME).date()


def replacement(number):
    cfg = REPLACEMENTS.get(str(number))
    if not cfg:
        return None
    today = today_rome()
    return cfg if cfg["from"] <= today <= cfg["to"] else None


_original_train_data = core.train_data
_original_baseline = core.baseline_payload
_original_unavailable = core.unavailable_payload


def train_data(number, fr, to):
    cfg = replacement(number)
    service_number = cfg["number"] if cfg else str(number)
    payload = _original_train_data(service_number, fr, to)
    if cfg:
        payload["logicalNumber"] = str(number)
        payload["replacementFor"] = str(number)
        payload["temporaryReplacement"] = True
        payload["source"] = f"ViaggiaTreno · sostitutivo {service_number}"
    return payload


def baseline_payload(number, fr, to, error=None):
    payload = _original_baseline(number, fr, to, error)
    cfg = replacement(number)
    if not cfg:
        return payload

    payload["number"] = cfg["number"]
    payload["logicalNumber"] = str(number)
    payload["replacementFor"] = str(number)
    payload["temporaryReplacement"] = True
    payload["departureScheduled"] = cfg["departure"]
    payload["departureExpected"] = cfg["departure"]
    payload["boardingArrivalScheduled"] = cfg["departure"]
    payload["boardingArrivalExpected"] = cfg["departure"]
    payload["arrivalScheduled"] = cfg["arrival"]
    payload["arrivalExpected"] = cfg["arrival"]
    payload["source"] = f"Programma · sostitutivo {cfg['number']}"
    return payload


# Install the replacement-aware functions before calling the original fallback:
# unavailable_payload resolves baseline_payload dynamically from the core module.
core.train_data = train_data
core.baseline_payload = baseline_payload


def unavailable_payload(number, fr, to, error, old=None):
    payload = _original_unavailable(number, fr, to, error, old)
    if not payload.get("staleLive"):
        payload["liveAvailable"] = False
        cfg = replacement(number)
        if cfg:
            payload["number"] = cfg["number"]
            payload["logicalNumber"] = str(number)
            payload["replacementFor"] = str(number)
            payload["temporaryReplacement"] = True
            payload["source"] = f"Programma · sostitutivo {cfg['number']} · dati live non disponibili"
        else:
            payload["source"] = "Programma · dati live non disponibili"
    return payload


core.unavailable_payload = unavailable_payload


if __name__ == "__main__":
    raise SystemExit(core.main())
