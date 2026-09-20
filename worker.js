/**
 * Cloudflare Worker - proxy ViaggiaTreno
 * Endpoint pubblico:
 *   GET /api/train?number=18739&from=FIGLINE%20VALDARNO&to=AREZZO
 *
 * Le API ViaggiaTreno qui usate sono non documentate ufficialmente e possono cambiare.
 */

const VT = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (url.pathname === "/health") {
      return json({ ok: true, service: "viaggiatreno-proxy", version: "1.0" });
    }

    if (url.pathname !== "/api/train") {
      return json({ error: "Endpoint non trovato" }, 404);
    }

    const number = (url.searchParams.get("number") || "").trim();
    const from = normalizeName(url.searchParams.get("from") || "");
    const to = normalizeName(url.searchParams.get("to") || "");

    if (!/^\d{1,6}$/.test(number) || !from || !to) {
      return json({ error: "Parametri number, from e to non validi" }, 400);
    }

    try {
      const id = await findTodayTrain(number);
      if (!id) throw new Error(`Treno ${number} non trovato per oggi`);

      const detailUrl = `${VT}/andamentoTreno/${encodeURIComponent(id.originCode)}/${encodeURIComponent(number)}/${encodeURIComponent(id.departureMillis)}`;
      const detail = await vtJson(detailUrl);

      const result = normalizeTrain(detail, number, from, to);
      return json(result, 200, { "Cache-Control": "public, max-age=45" });
    } catch (err) {
      return json({ error: err?.message || "Errore ViaggiaTreno" }, 502);
    }
  }
};

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(),
      ...extra,
    },
  });
}

async function vtText(url) {
  const r = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 TrainDashboard/1.0",
      "Accept": "text/plain,application/json;q=0.9,*/*;q=0.8",
    },
  });
  if (!r.ok) throw new Error(`ViaggiaTreno HTTP ${r.status}`);
  return r.text();
}

async function vtJson(url) {
  const text = await vtText(url);
  try { return JSON.parse(text); }
  catch { throw new Error("Risposta ViaggiaTreno non valida"); }
}

function todayRomeParts() {
  const p = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome", day: "2-digit", month: "2-digit", year: "2-digit"
  }).formatToParts(new Date());
  const m = Object.fromEntries(p.filter(x => x.type !== "literal").map(x => [x.type, x.value]));
  return `${m.day}/${m.month}/${m.year}`;
}

async function findTodayTrain(number) {
  const autoUrl = `${VT}/cercaNumeroTrenoTrenoAutocomplete/${encodeURIComponent(number)}`;
  const text = await vtText(autoUrl);
  const today = todayRomeParts();
  const candidates = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(parseAutocompleteLine).filter(Boolean);

  let chosen = candidates.find(c => c.date === today);
  if (!chosen && candidates.length) chosen = candidates[candidates.length - 1];
  if (chosen) return chosen;

  // Fallback: cercaNumeroTreno restituisce normalmente la corsa del giorno.
  const one = await vtJson(`${VT}/cercaNumeroTreno/${encodeURIComponent(number)}`);
  if (one?.codLocOrig && one?.millisDataPartenza) {
    return {
      originCode: one.codLocOrig,
      departureMillis: String(one.millisDataPartenza),
      date: one.dataPartenza || null,
    };
  }
  return null;
}

function parseAutocompleteLine(line) {
  const bar = line.lastIndexOf("|");
  if (bar < 0) return null;
  const left = line.slice(0, bar);
  const right = line.slice(bar + 1);
  const mRight = right.match(/^(\d+)-(S\d{5})-(\d+)$/);
  const mDate = left.match(/(\d{2}\/\d{2}\/\d{2})\s*$/);
  if (!mRight) return null;
  return {
    number: mRight[1],
    originCode: mRight[2],
    departureMillis: mRight[3],
    date: mDate ? mDate[1] : null,
  };
}

function normalizeName(s) {
  return String(s)
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toUpperCase().replace(/[.'’]/g, "")
    .replace(/\s+/g, " ").trim();
}

function stopMatch(stops, target) {
  const n = normalizeName(target);
  return stops.find(s => normalizeName(s?.stazione || "") === n)
      || stops.find(s => normalizeName(s?.stazione || "").includes(n))
      || stops.find(s => n.includes(normalizeName(s?.stazione || "")));
}

function toHHMM(ms) {
  if (!ms || !Number.isFinite(Number(ms))) return null;
  return new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).format(new Date(Number(ms)));
}

function addMinutesToHHMM(hhmm, mins) {
  if (!hhmm || !/^\d{2}:\d{2}$/.test(hhmm)) return null;
  const [h,m] = hhmm.split(":").map(Number);
  const d = new Date(Date.UTC(2000,0,1,h,m + Number(mins || 0)));
  return `${String(d.getUTCHours()).padStart(2,"0")}:${String(d.getUTCMinutes()).padStart(2,"0")}`;
}

function platformDeparture(stop) {
  return stop?.binarioEffettivoPartenzaDescrizione
      || stop?.binarioProgrammatoPartenzaDescrizione
      || stop?.binarioEffettivoPartenzaCodice
      || stop?.binarioProgrammatoPartenzaCodice
      || null;
}

function normalizeTrain(detail, number, fromName, toName) {
  const stops = Array.isArray(detail?.fermate) ? detail.fermate : [];
  const from = stopMatch(stops, fromName);
  const to = stopMatch(stops, toName);
  if (!from) throw new Error(`Fermata ${fromName} non trovata nel treno ${number}`);
  if (!to) throw new Error(`Fermata ${toName} non trovata nel treno ${number}`);

  const departureScheduled = toHHMM(from.partenza_teorica || from.programmata);
  const arrivalScheduled = toHHMM(to.arrivo_teorico || to.programmata);

  const rootDelay = Number(detail?.ritardo);
  const delayMinutes = Number.isFinite(rootDelay)
    ? rootDelay
    : Number.isFinite(Number(from.ritardoPartenza))
      ? Number(from.ritardoPartenza)
      : Number.isFinite(Number(from.ritardo))
        ? Number(from.ritardo)
        : 0;

  const cancelled =
    ["ST"].includes(detail?.tipoTreno) ||
    Number(from.actualFermataType) === 3 ||
    Number(to.actualFermataType) === 3;

  const departureActual = toHHMM(from.partenzaReale || from.effettiva);
  const arrivalActual = toHHMM(to.arrivoReale || to.effettiva);
  const started = Boolean(departureActual) || Boolean(detail?.oraUltimoRilevamento);

  let status = "NOT_STARTED";
  if (cancelled) status = "CANCELLED";
  else if (arrivalActual) status = "ARRIVED";
  else if (started) status = delayMinutes > 0 ? "DELAYED" : "ON_TIME";
  else if (delayMinutes > 0) status = "DELAYED";

  let arrivalExpected = arrivalActual;
  if (!arrivalExpected && arrivalScheduled) arrivalExpected = addMinutesToHHMM(arrivalScheduled, delayMinutes);

  const lastDetection = detail?.stazioneUltimoRilevamento
    ? `Ultimo rilevamento: ${detail.stazioneUltimoRilevamento}`
    : null;

  return {
    number,
    from: from.stazione || fromName,
    to: to.stazione || toName,
    status,
    cancelled,
    started,
    delayMinutes: Math.max(0, Math.round(delayMinutes || 0)),
    departureScheduled,
    departureActual,
    arrivalScheduled,
    arrivalExpected,
    arrivalActual,
    platform: platformDeparture(from),
    lastDetection,
    updatedAt: Date.now(),
    source: "ViaggiaTreno",
  };
}
