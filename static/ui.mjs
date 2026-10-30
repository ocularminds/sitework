export const $ = (id) => document.getElementById(id);
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  camera: '<path d="M14.5 5h-5L8 8H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-4z"/><circle cx="12" cy="13.5" r="3.5"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  book: '<path d="M4 3h7v17H4a2 2 0 0 0 0 0V3Zm16 0h-7v17h7V3ZM11 20h2M6 7h3M15 7h3M6 11h3M15 11h3"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  external: '<path d="M14 3h7v7M10 14 21 3M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  play: '<path d="m8 5 11 7-11 7z"/>',
  light: '<rect x="7" y="2" width="10" height="18" rx="3"/><path d="M10 22h4"/><circle cx="12" cy="6" r="1"/><circle cx="12" cy="11" r="1"/><circle cx="12" cy="16" r="1"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4"/>',
  deck: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16M3 10h6m6 4h6"/>',
  trench: '<path d="M2 5h4l4 14h4l4-14h4M2 21h20M2 10h3m14 0h3"/>',
  pipe: '<path d="M5 2v10a7 7 0 0 0 7 7h10M11 2v10a1 1 0 0 0 1 1h10M3 2h10m9 9v10"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  unlock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 7.5-2m-3.5 10v2"/>',
  settings: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor" stroke="none"/><circle cx="16" cy="12" r="2" fill="currentColor" stroke="none"/><circle cx="8" cy="18" r="2" fill="currentColor" stroke="none"/>',
  ruler: '<path d="m3 16 13-13 5 5L8 21zM7 12l2 2m2-6 2 2m2-6 2 2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  fullscreen: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
};

export function icon(name, extra = "") {
  return `<svg class="icon ${esc(extra)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name] || paths.info}</svg>`;
}

export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => { el.innerHTML = icon(el.dataset.icon); });
}

export function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
}

export const sceneName = (scene) => ({ decking: "Decking", trench: "Trench", plumbing: "Plumbing" }[scene] || scene || "Inspection");
export const conditionName = (condition) => ({ clean: "Clean / dry", rain: "Rain", mud: "Mud", dusk_glare: "Dusk / glare", outdoor: "Outdoor" }[condition] || condition || "—");
export const jurisdictionName = (jurisdiction) => ({ US: "United States", "US-OSHA": "US · OSHA", SE: "Sweden" }[jurisdiction] || jurisdiction);
export const dateTime = (value, timeOnly = false) => {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "—";
  return timeOnly ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};

export function presentation(light, { connected = true, mock = false } = {}) {
  if (!connected) return { color: "off", title: "Status unavailable", label: "CONNECTION LOST", kicker: "Waiting to reconnect", icon: "refresh" };
  if (mock) return { color: "red", title: "Test environment", label: "MOCK GATE", kicker: "No live release", icon: "info" };
  const label = String(light?.label || "NO INSPECTION").replaceAll("_", " ");
  if (light?.color === "green") return { color: "green", title: "Hold released", label, kicker: "Release finalized", icon: "check" };
  if (light?.color === "blue") return { color: "blue", title: "Human release recorded", label, kicker: "Released by a person", icon: "unlock" };
  if (light?.color === "amber") return { color: "amber", title: "Human review required", label, kicker: "Hold stays closed", icon: "pause" };
  if (light?.color === "red") return { color: "red", title: label === "NO DECISION" ? "No decision received" : label === "BLOCK" ? "Hold blocked" : "Hold stays closed", label, kicker: "Release not authorized", icon: "lock" };
  return { color: "off", title: "Awaiting inspection", label: "NO INSPECTION", kicker: "Hold point", icon: "lock" };
}

export function matchesSelection(record, scene, condition, jurisdiction) {
  return !!record && record.scene === scene && record.condition === condition && record.jurisdiction === jurisdiction;
}

// A stored dossier has no light, so its verdict says whether the release went through.
export function released(record) {
  const v = record?.verdict;
  return record?.light?.color === "green" || !!(v?.decision === "ALLOW" && v.should_execute && v.grant_claimed && v.grant_finalized);
}

export function inspectionMessage(record) {
  if (!record) return "Run an inspection to check this hold point against its cited requirement.";
  if (record.failure) return "No decision came back from Decionis, so the hold stays closed. Check the connection details.";
  if (record.regrounded_from && record.verdict?.decision === "ALLOW" && record.verdict?.grant_error) return "Decionis allows this under the new jurisdiction, but a re-decision never releases the hold. Inspect again to release it.";
  if (record.verdict?.grant_error) return "Decionis allowed the action, but SiteWork did not complete the release, so the hold stays closed. The decision details say why.";
  if ((record.errors || []).some((error) => /marker not found/i.test(error))) return "The calibration marker was not found. Bring it clearly into view, then inspect again.";
  if (!(record.citations || []).length) return "No approved requirement covers this inspection, so it cannot be released automatically.";
  if (record.errors?.length) return `${record.errors.length} evidence issue${record.errors.length === 1 ? " needs" : "s need"} review. They are listed under the measurements.`;
  const reason = record.verdict?.reason || "";
  if (reason && !/^[A-Z_0-9,\s]+$/.test(reason)) return reason;
  if (["ESCALATE", "REVIEW_REQUIRED"].includes(record.verdict?.decision)) return "A named reviewer must check the evidence before this hold can be released.";
  if (record.verdict?.decision === "BLOCK") return "The policy blocked this release. Compare the measurements with the cited requirement.";
  if (record.verdict?.decision === "ALLOW") return released(record) ? "Decionis allowed this release. SiteWork claimed its single-use grant and finalized it." : "Decionis allowed the action without authorizing execution, so the hold stays closed.";
  return reason || "Review the recorded evidence and decision details.";
}

export function measurementName(kind, scene) {
  if (kind === "angle_deg") return { decking: "Board angle", plumbing: "Pipe alignment" }[scene] || "Angle";
  return ({ gap_mm: "Board gap", slope_deg: "Wall slope", depth_mm: "Trench depth", seat_audio: "Seating sound" })[kind] || kind.replaceAll("_", " ");
}

const unitOf = (kind) => kind.endsWith("_mm") ? " mm" : kind.endsWith("_deg") ? "°" : "";

export function limitText(check, kind) {
  const n = (v) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(v);
  const has = (v) => v !== null && v !== undefined && v !== "";
  const unit = unitOf(kind);
  if (has(check?.min) && has(check?.max)) return `${n(check.min)}–${n(check.max)}${unit}`;
  if (has(check?.max)) return `≤ ${n(check.max)}${unit}`;
  if (has(check?.min)) return `≥ ${n(check.min)}${unit}`;
  return "No numeric limit";
}

export function sourceName(spec) {
  if (!spec) return "";
  if (spec.startsWith("camera:")) return `Camera ${spec.slice(7)}`;
  return spec.replace(/^file:/, "");
}

export function measurementValue(measurement) {
  if (typeof measurement.value === "boolean") return { value: measurement.value ? "Detected" : "Not detected", unit: "" };
  const unit = unitOf(measurement.kind).trim();
  const value = Number.isFinite(measurement.value) ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(measurement.value) : "—";
  return { value, unit };
}

export async function api(url, body, method = "POST") {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : data?.detail ? JSON.stringify(data.detail) : response.statusText;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  if (data === null) throw new Error("The server returned an unreadable response.");
  return data;
}

export function proofMarkup(result) {
  const explanation = !result.verified ? "The artifact did not pass verification." : result.issuer_authentic
    ? "The signature is intact and the issuer’s authenticity is confirmed."
    : "The signature is intact. This check has not independently established the issuer’s authenticity.";
  return `<strong class="${result.verified ? "ok" : "bad"}">${icon(result.verified ? "check" : "close")} ${result.verified ? "Signature valid" : "Verification failed"}</strong>${explanation}
    <details class="disclosure"><summary>${icon("chevron", "chevron")}Verification details</summary><p>Mode: ${esc(result.mode)} · Trust: ${esc(result.trust)}<br>
    Signed artifacts: ${esc((result.artifact_paths || []).join(", ") || "none")}${result.coverage !== undefined ? `<br>Coverage: ${esc(result.coverage)}` : ""}</p></details>`;
}

export function connectState(onMessage, onConnection) {
  let socket, retry, disposed = false;
  const connect = () => {
    if (disposed) return;
    socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "state") onConnection(true);
        onMessage(message);
      } catch (error) { console.error("SiteWork could not display an update.", error); }
    };
    socket.onclose = () => { if (!disposed) { onConnection(false); retry = setTimeout(connect, 2000); } };
    socket.onerror = () => socket.close();
  };
  connect();
  const stop = () => { disposed = true; clearTimeout(retry); socket?.close(); };
  window.addEventListener("pagehide", stop, { once: true });
  return stop;
}
