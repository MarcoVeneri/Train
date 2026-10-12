#!/usr/bin/env python3
"""Runtime compat layer: keep the proven continuous monitor, query both trains every cycle,
and never show a guessed 'in orario' as live data when the source failed."""
import update_trains as core

# With the continuous 5-minute monitor there is no need to suppress one of the two
# trains by time window. This also lets the app recover the final state of a train
# later in the same day if an earlier check was missed.
core.should_monitor = lambda _number: True

_original_unavailable = core.unavailable_payload

def unavailable_payload(number, fr, to, error, old=None):
    payload = _original_unavailable(number, fr, to, error, old)
    if not payload.get("staleLive"):
        payload["liveAvailable"] = False
        payload["source"] = "Programma · dati live non disponibili"
    return payload

core.unavailable_payload = unavailable_payload

if __name__ == "__main__":
    raise SystemExit(core.main())
