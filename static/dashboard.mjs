import { $, api, conditionName, connectState, dateTime, esc, hydrateIcons, icon, inspectionMessage, jurisdictionName, limitText, matchesSelection, measurementName, measurementValue, presentation, proofMarkup, safeUrl, sceneName, sourceName } from "./ui.mjs";

let state = null;
let last = null;
let scene = "decking";
let connected = false;
let operation = "";
let view = "live";
let sourceFailed = false;
let previousSource = false;
let requestError = "";
let proofBusy = false;
let toastTimer;
let frameRevision = 0;
const sceneTabs = [...document.querySelectorAll("[data-scene]")];
hydrateIcons();

function toast(message) {
  clearTimeout(toastTimer);
  $("toastMessage").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 8000);
}
$("closeToast").onclick = () => { $("toast").hidden = true; };

function controls() {
  const busy = !!operation;
  $("inspect").disabled = busy || !connected || !state?.source || sourceFailed;
  $("condition").disabled = busy || !state;
  $("jurisdiction").disabled = busy || !connected || !state?.jurisdictions?.length;
  sceneTabs.forEach((tab) => { tab.disabled = busy; });
  document.querySelectorAll("[data-open-source], [data-proposal-action]").forEach((button) => { button.disabled = busy || !connected; });
  $("release").disabled = $("keep").disabled = busy || !connected;
  const verifiable = !!(last?.verdict?.dossier_id && last.gate_mode === "live");
  $("verify").disabled = $("tamper").disabled = busy || proofBusy || !verifiable;
}

function setOperation(name, message = "") {
  operation = name;
  $("captureStage").setAttribute("aria-busy", String(["inspect", "reground"].includes(name)));
  $("processing").hidden = !["inspect", "reground"].includes(name);
  $("processingLabel").textContent = message;
  $("inspectLabel").textContent = name === "inspect" ? "Inspecting…" : name === "reground" ? "Re-evaluating…" : "Run inspection";
  $("announcer").textContent = message;
  controls();
  renderStatus();
}

function setConnection(value) {
  connected = value;
  $("connection").dataset.status = value ? "connected" : "disconnected";
  $("connectionLabel").textContent = value ? "Workspace connected" : "Reconnecting…";
  $("connection").title = value ? "Receiving updates from the SiteWork app" : "Live status is unavailable. Waiting for the app to reconnect.";
  controls();
  renderStatus();
}

function applyState(next, forceSource = false) {
  const changedSource = !!state && state.source !== next.source;
  if (changedSource && last) previousSource = true;
  const restartFeed = forceSource || !state || changedSource;
  state = next;
  $("mock").hidden = next.gate_mode !== "mock";
  $("gate").className = `badge heading-badge ${next.gate_mode === "mock" ? "badge-red" : next.decision_mode === "SHADOW" ? "badge-amber" : "badge-neutral"}`;
  const mode = next.gate_mode === "mock" ? "MOCK GATE" : ({ ENFORCEMENT: "Enforced decisions", SHADOW: "Shadow decisions", PARALLEL: "Parallel decisions" }[next.decision_mode] || "Live gate configured");
  $("gateLabel").textContent = mode;
  $("gatewayMode").textContent = mode;
  try { $("gatewayAddress").textContent = new URL(next.gateway).host; }
  catch { $("gatewayAddress").textContent = "Gateway not configured"; }
  const jurisdictions = next.jurisdictions?.length ? next.jurisdictions : [next.jurisdiction].filter(Boolean);
  $("jurisdiction").innerHTML = jurisdictions.map((j) => `<option value="${esc(j)}" ${j === next.jurisdiction ? "selected" : ""}>${esc(jurisdictionName(j))}</option>`).join("");
  $("source").textContent = next.source ? sourceName(next.source) : "No source connected";
  $("source").title = next.source || next.source_error || "No capture source";
  updateSourceDescription();
  if (restartFeed) {
    frameRevision += 1;
    sourceFailed = false;
    $("live").removeAttribute("src");
    if (next.source) $("live").src = `/api/stream?t=${Date.now()}`;
    view = "live";
  }
  if (next.last) render(next.last);
  else if (last) resetResult();
  updateView();
  controls();
  renderStatus();
}

function selectScene(value) {
  if (!sceneTabs.some((tab) => tab.dataset.scene === value)) return;
  scene = value;
  sceneTabs.forEach((tab) => {
    const selected = tab.dataset.scene === value;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  $("inspectionWorkspace").setAttribute("aria-labelledby", `scene-${value}`);
  $("captureTip").textContent = {
    decking: "Keep the 40 mm calibration marker and both board edges in view.",
    trench: "Keep the calibration marker, wall tops and toes visible. Do not enter the trench to capture it.",
    plumbing: "Frame the pipe and fitting with the calibration marker. Capture the seating sound during the join.",
  }[value];
  updateSourceDescription();
  renderStatus();
}

function updateSourceDescription() {
  const detail = state?.source?.startsWith("file:") ? "Recorded video · loops for preview" : state?.source ? "Camera connected to the app" : "Camera or video replay";
  $("sourceDetail").textContent = scene === "plumbing" && state?.audio ? `${detail} · Audio: ${state.audio}` : detail;
}

sceneTabs.forEach((tab, index) => {
  tab.onclick = () => selectScene(tab.dataset.scene);
  tab.onkeydown = (event) => {
    const destination = { ArrowRight: (index + 1) % sceneTabs.length, ArrowLeft: (index + sceneTabs.length - 1) % sceneTabs.length, Home: 0, End: sceneTabs.length - 1 }[event.key];
    if (destination === undefined || operation) return;
    event.preventDefault();
    sceneTabs[destination].focus();
    selectScene(sceneTabs[destination].dataset.scene);
  };
});
$("condition").onchange = renderStatus;

function renderSelection() {
  if (!last) { $("selectionNote").hidden = true; return; }
  const mismatch = !matchesSelection(last, scene, $("condition").value, $("jurisdiction").value);
  $("selectionNote").hidden = !mismatch && !previousSource && !requestError;
  $("selectionNote").textContent = requestError ? "The previous inspection is shown below; no new result has been confirmed."
    : previousSource ? "This result belongs to the previous capture source. Run an inspection for the new source."
      : `Showing the last ${sceneName(last.scene).toLowerCase()} inspection. Run an inspection for the selected setup.`;
}

function renderStatus() {
  const pending = ["inspect", "reground"].includes(operation);
  const p = presentation(state?.light, { connected: connected || !state, mock: state?.gate_mode === "mock" });
  const otherSetup = !!last && (previousSource || !matchesSelection(last, scene, $("condition").value, $("jurisdiction").value));
  const provisional = pending || !!requestError || otherSetup;
  $("verdictCard").className = `panel verdict-card ${provisional ? "off" : p.color}`;
  $("statusIcon").innerHTML = pending ? '<span class="spinner"></span>' : icon(requestError ? "info" : p.icon);
  $("statusTitle").textContent = pending ? (operation === "reground" ? "Re-evaluating evidence" : "Inspection in progress") : requestError ? "Status unconfirmed" : otherSetup && connected ? "New inspection needed" : p.title;
  $("statusKicker").textContent = pending ? "Waiting for a result" : requestError ? "A new decision is unavailable" : otherSetup && connected ? "Setup changed" : p.kicker;
  $("statusBadge").textContent = pending ? "Processing" : !connected && state ? "Disconnected" : otherSetup ? "Previous result" : last ? "Latest result" : "Not inspected";
  $("decisionLabel").textContent = provisional || (!connected && last) ? "Previous Decionis decision" : "Decionis decision";
  $("decision").textContent = last?.verdict?.decision || (last?.failure ? "NO DECISION" : "—");
  $("reason").textContent = pending ? (operation === "reground" ? "The saved evidence is being checked against the selected jurisdiction’s requirements." : "The evidence is being evaluated. Wait for the confirmed hold status before proceeding.")
    : requestError || (!connected && state ? "The app connection was interrupted. The current hold status cannot be confirmed."
      : otherSetup ? "The selected setup has not been inspected. The previous decision is retained below for reference."
        : inspectionMessage(last));
  renderSelection();
  renderHold();
}

function render(record) {
  const isNew = !last || last.record_id !== record.record_id;
  last = record;
  if (state) { state.last = record; state.light = record.light; }
  requestError = "";
  if (isNew) {
    previousSource = false;
    selectScene(record.scene);
    $("condition").value = record.condition;
    $("jurisdiction").value = record.jurisdiction;
    $("proof").textContent = "";
    $("approver").value = "";
    $("resolutionNote").value = "";
    $("holdError").hidden = true;
    $("approver").removeAttribute("aria-invalid");
    $("proofStatus").className = "badge badge-neutral";
    $("proofStatus").textContent = record.verdict?.dossier_id && record.gate_mode === "live" ? "Not verified" : "No signed dossier";
  }
  $("resultContext").hidden = false;
  $("resultContext").innerHTML = [sceneName(record.scene), conditionName(record.condition), record.jurisdiction].map((v) => `<span class="badge badge-neutral">${esc(v)}</span>`).join("");
  $("policyVersion").textContent = `Policy ${record.verdict?.policy_version || "—"}`;
  $("policyVersion").title = record.action || "";
  const latency = record.verdict?.latency_ms ?? record.failure?.latency_ms;
  $("latency").innerHTML = `${icon("clock")} ${typeof latency === "number" ? `${esc(latency.toFixed(0))} ms · ` : ""}${esc(dateTime(record.created_at, true))}`;
  $("latency").title = `Gate latency · ${dateTime(record.created_at)}`;
  $("decisionDetails").hidden = false;
  $("decisionRaw").textContent = [record.action, record.verdict?.reason, record.verdict?.grant_error, record.failure?.error].filter(Boolean).join("\n");
  renderMeasurements(record);
  renderCitation(record);
  $("dossierEmpty").hidden = true;
  $("dossierIdentity").hidden = false;
  $("dossier").textContent = record.record_id.length > 24 ? `${record.record_id.slice(0, 18)}…` : record.record_id;
  $("dossier").title = record.record_id;
  $("dossierLink").hidden = false;
  $("dossierLink").href = `/dossier?id=${encodeURIComponent(record.record_id)}`;
  const verifiable = !!(record.verdict?.dossier_id && record.gate_mode === "live");
  $("tamperDetails").hidden = !verifiable;
  if (!verifiable) $("proof").textContent = "This inspection has no signed Decionis dossier to verify.";
  $("showInspected").disabled = !record.overlay;
  if (isNew && record.overlay) drawOverlay(record);
  if (!record.overlay) { view = "live"; updateView(); }
  renderStatus();
  controls();
  if (isNew) $("announcer").textContent = `${sceneName(record.scene)} inspection complete. ${record.light.label}.`;
}

function resetResult() {
  frameRevision += 1;
  last = null;
  previousSource = false;
  requestError = "";
  view = "live";
  $("resultContext").hidden = true;
  $("dossierEmpty").hidden = false;
  $("dossierIdentity").hidden = true;
  $("dossierLink").hidden = true;
  $("tamperDetails").hidden = true;
  $("decisionDetails").hidden = true;
  $("showInspected").disabled = true;
  $("proof").textContent = "";
  $("proofStatus").textContent = "No record";
  $("proofStatus").className = "badge badge-neutral";
  $("policyVersion").textContent = "Policy —";
  $("latency").textContent = "Awaiting a decision";
  renderMeasurements(null);
  renderCitation(null);
}

function renderMeasurements(record) {
  const measurements = record?.measurements || [];
  $("measurementCount").textContent = measurements.length ? `${measurements.length} reading${measurements.length === 1 ? "" : "s"}` : record ? "No measurements" : "No readings yet";
  const checks = new Map((record?.checks || []).map((check) => [`${check.kind}:${check.value}`, check]));
  $("measurementRows").innerHTML = measurements.length ? measurements.map((m) => {
    const value = measurementValue(m);
    const check = checks.get(`${m.kind}:${m.value}`);
    const confidence = Number.isFinite(m.confidence) && m.confidence >= 0 && m.confidence <= 1 ? m.confidence : null;
    const bound = check ? `<span class="${check.within ? "ok" : "bad"}">${check.within ? "Within limit" : "Outside limit"}</span><span class="measure-range">${esc(limitText(check, m.kind))}</span>` : '<span class="muted">No cited limit</span>';
    return `<tr><td><span class="measure-name">${esc(measurementName(m.kind, record.scene))}</span><span class="measure-method">${esc(m.method)}</span></td><td class="num measure-value">${esc(value.value)} <small>${value.unit}</small></td><td class="num"><span class="confidence">${confidence === null ? "—" : `<span class="confidence-track" aria-hidden="true"><i style="width:${confidence * 100}%"></i></span>${(confidence * 100).toFixed(0)}%`}</span></td><td class="num">${bound}</td></tr>`;
  }).join("") : `<tr><td colspan="4"><div class="empty-measurements"><strong>${record ? "Measurements unavailable" : "Evidence starts with an inspection"}</strong><p>${record ? "Review the evidence issues below before proceeding." : "Measured values and their confidence will appear here."}</p></div></td></tr>`;
  $("errors").hidden = !record?.errors?.length;
  $("errors").innerHTML = (record?.errors || []).map((error) => `<li>${esc(error)}</li>`).join("");
}

function renderCitation(record) {
  $("citationJurisdiction").textContent = record?.jurisdiction || "—";
  const citations = record?.citations || [];
  $("citation").innerHTML = citations.length ? citations.map((c) => {
    const url = safeUrl(c.url);
    return `<div class="citation-text">${esc(c.requirement)}</div><div class="citation-source">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(c.source_domain)} ${icon("external")}</a>` : esc(c.source_domain)}<span class="muted">· ${esc(dateTime(c.retrieved_at))}</span></div><div class="citation-hash">Source SHA-256 <code>${esc(c.content_sha256?.slice(0, 16) || "—")}…</code></div>`;
  }).join('<hr style="border:0;border-top:1px solid var(--line);margin:17px 0">') : `<div class="empty-copy ${record ? "warning" : ""}">${record ? `The ${esc(jurisdictionName(record.jurisdiction))} pack has no approved requirement for this hold point. Decionis was told the citation is missing, so it cannot allow a release.` : "The requirement this work is checked against, and its source, will appear with the result."}</div>`;
}

function renderHold() {
  const escalated = ["ESCALATE", "REVIEW_REQUIRED"].includes(last?.verdict?.decision);
  $("hold").hidden = !escalated || !!last?.resolution || !connected || previousSource || !!requestError
    || !matchesSelection(last, scene, $("condition").value, $("jurisdiction").value) || ["inspect", "reground"].includes(operation);
  const resolution = last?.resolution;
  $("resolution").hidden = !resolution;
  if (resolution) $("resolution").innerHTML = `<strong style="color:var(--${resolution.release ? "blue" : "red"})">${resolution.release ? "Released" : "Kept on hold"} by ${esc(resolution.approver)}</strong>${esc(dateTime(resolution.at))}${resolution.note ? `<br>${esc(resolution.note)}` : ""}`;
}

async function holdDecision(release) {
  if (!last || operation || !connected) return;
  const approver = $("approver").value.trim();
  if (!approver) {
    $("holdError").hidden = false;
    $("holdError").textContent = "Enter the full name of the person making this decision.";
    $("approver").setAttribute("aria-invalid", "true");
    $("approver").focus();
    return;
  }
  const recordId = last.record_id;
  setOperation("resolve", "Recording the reviewer’s decision…");
  try {
    const outcome = await api(`/api/dossiers/${encodeURIComponent(recordId)}/resolve`, { approver, release, note: $("resolutionNote").value.trim() });
    if (last?.record_id === recordId) render({ ...last, resolution: outcome.resolution, light: outcome.light });
    toast(release ? "Human release recorded alongside the dossier." : "Decision to keep the hold recorded.");
  } catch (error) { $("holdError").textContent = error.message; $("holdError").hidden = false; }
  finally { setOperation(""); }
}
$("approver").oninput = () => { $("approver").removeAttribute("aria-invalid"); $("holdError").hidden = true; };
$("release").onclick = () => holdDecision(true);
$("keep").onclick = () => holdDecision(false);

function updateView() {
  const inspected = view === "inspected" && !!last?.overlay;
  const available = !!state?.source && !sourceFailed;
  $("live").hidden = inspected || !available;
  $("overlay").hidden = !inspected;
  $("feedEmpty").hidden = inspected || available;
  $("captureHud").hidden = $("frameContext").hidden = !inspected && !available;
  $("showLive").setAttribute("aria-pressed", String(!inspected));
  $("showInspected").setAttribute("aria-pressed", String(inspected));
  $("feedMode").textContent = inspected ? "Recorded evidence" : state?.source?.startsWith("file:") ? "Video replay" : "Camera feed";
  $("calibrationStatus").textContent = inspected ? (last.overlay.marker?.length ? "Calibration marker detected" : "No calibration marker") : "Calibration checked on inspection";
  $("frameLabel").textContent = inspected ? `${sceneName(last.scene)} · ${last.jurisdiction} · ${dateTime(last.created_at, true)}` : sourceName(state?.source);
  const width = inspected ? last.overlay.width : $("live").naturalWidth;
  const height = inspected ? last.overlay.height : $("live").naturalHeight;
  $("frameSize").hidden = !width;
  $("frameSize").textContent = `${width} × ${height}`;
  $("captureSubtitle").textContent = inspected ? `Evidence captured ${dateTime(last.created_at)}` : "The work, as it is.";
  $("feedEmptyTitle").textContent = sourceFailed ? "Preview unavailable" : "Bring the work into view";
  $("feedEmptyMessage").textContent = sourceFailed ? "The source stopped sending frames. Reconnect it to continue."
    : state?.source_error ? `The last source couldn’t be opened (${state.source_error}). Connect a camera or replay a recorded clip.`
      : "Connect a camera or replay a recorded clip to begin an inspection.";
}
$("live").onerror = () => { if (operation === "source" || !state?.source) return; sourceFailed = true; updateView(); controls(); };
$("live").onload = () => { sourceFailed = false; updateView(); controls(); };
$("showLive").onclick = () => { view = "live"; updateView(); };
$("showInspected").onclick = () => { if (last?.overlay) { view = "inspected"; updateView(); } };

function drawOverlay(record) {
  const revision = ++frameRevision;
  const overlay = record.overlay;
  const image = new Image();
  image.onload = () => {
    if (last?.record_id !== record.record_id || revision !== frameRevision) return;
    const canvas = $("overlay");
    canvas.width = overlay.width;
    canvas.height = overlay.height;
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    context.lineWidth = Math.max(2, overlay.width / 400);
    if (overlay.marker?.length) {
      context.strokeStyle = "#60e2ee";
      context.beginPath();
      overlay.marker.forEach(([x, y], index) => index ? context.lineTo(x, y) : context.moveTo(x, y));
      context.closePath();
      context.stroke();
    }
    context.strokeStyle = "#f8d76a";
    (overlay.segments || []).forEach(([[x1, y1], [x2, y2]]) => { context.beginPath(); context.moveTo(x1, y1); context.lineTo(x2, y2); context.stroke(); });
    // Readings sit on a dark plate above the frame label, clear of the HUD chips and the marker.
    const lines = (record.measurements || []).map((m) => {
      const value = measurementValue(m);
      return `${measurementName(m.kind, record.scene)} ${value.value}${value.unit === "°" ? "°" : value.unit ? ` ${value.unit}` : ""}`;
    });
    if (lines.length) {
      const stage = $("captureStage");
      const scale = Math.min(stage.clientWidth / overlay.width, stage.clientHeight / overlay.height) || 1;
      const top = Math.max(0, (stage.clientHeight - overlay.height * scale) / 2);
      const size = Math.max(16, overlay.width / 40);
      const pad = size * 0.5, lineHeight = size * 1.35;
      const height = lines.length * lineHeight + pad;
      const x = Math.max(12, 14 / scale);
      const y = Math.max(12, overlay.height - height - Math.max(12, (Math.max($("frameContext").offsetHeight, 20) + 20 - top) / scale));
      context.font = `600 ${size}px system-ui, sans-serif`;
      context.textBaseline = "top";
      context.fillStyle = "rgba(19, 25, 33, 0.78)";
      context.fillRect(x, y, Math.max(...lines.map((line) => context.measureText(line).width)) + pad * 2, height);
      context.fillStyle = "#f8d76a";
      lines.forEach((line, index) => context.fillText(line, x + pad, y + pad * 0.75 + index * lineHeight));
    }
    view = "inspected";
    updateView();
  };
  image.onerror = () => { view = "live"; updateView(); toast("The inspected frame could not be displayed. Its dossier is still available."); };
  image.src = `data:image/jpeg;base64,${overlay.frame_jpeg}`;
}

$("inspect").onclick = async () => {
  if (operation || !connected) return;
  requestError = "";
  setOperation("inspect", scene === "plumbing" ? "Capturing the join and its seating sound…" : "Evaluating the captured evidence…");
  let completed = false;
  try { render(await api("/api/inspect", { scene, condition: $("condition").value })); completed = true; }
  catch (error) { requestError = `Inspection request failed: ${error.message}`; toast(requestError); }
  finally { setOperation(""); }
  if (completed && matchMedia("(max-width: 760px)").matches) {
    $("verdictCard").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
  }
};

$("jurisdiction").onchange = async () => {
  if (operation || !connected) return;
  const jurisdiction = $("jurisdiction").value;
  const previous = state?.jurisdiction;
  requestError = "";
  setOperation("reground", `Checking the ${jurisdictionName(jurisdiction)} requirement pack…`);
  try { applyState(await api("/api/jurisdiction", { jurisdiction })); }
  catch (error) { $("jurisdiction").value = previous; requestError = `Jurisdiction change failed: ${error.message}`; toast(requestError); }
  finally { setOperation(""); }
};

async function verify(tamper = false) {
  if (!last || proofBusy || operation) return;
  const recordId = last.record_id;
  proofBusy = true;
  controls();
  $("proof").textContent = tamper ? "Changing one byte in a copy, then verifying…" : "Verifying the saved signature…";
  try {
    const result = await api(`/api/dossiers/${encodeURIComponent(recordId)}/${tamper ? "tamper" : "verify"}`);
    if (last?.record_id !== recordId) return;
    if (tamper) {
      $("proof").innerHTML = `<span>Copy changed at <code>${esc(result.pointer)}</code>: “${esc(result.before)}” → “${esc(result.after)}” (${esc(result.bytes_changed)} byte)</span><br>${proofMarkup(result.result)}`;
    } else {
      $("proof").innerHTML = proofMarkup(result);
      $("proofStatus").textContent = result.verified ? "Signature valid" : "Invalid";
      $("proofStatus").className = `badge ${result.verified ? "badge-blue" : "badge-red"}`;
    }
  } catch (error) { if (last?.record_id === recordId) $("proof").textContent = `Verification failed: ${error.message}`; }
  finally { proofBusy = false; controls(); }
}
$("verify").onclick = () => verify(false);
$("tamper").onclick = () => verify(true);
$("copyDossier").onclick = async () => {
  if (!last) return;
  try { await navigator.clipboard.writeText(last.record_id); toast("Dossier ID copied."); }
  catch { toast(`Dossier ID: ${last.record_id}`); }
};

function openSource() {
  if (operation || $("sourceDialog").open) return;
  $("sourceError").hidden = true;
  $("sourceDialog").showModal();
}
document.querySelectorAll("[data-open-source]").forEach((button) => { button.onclick = openSource; });
$("closeSource").onclick = $("cancelSource").onclick = () => { if (operation !== "source") $("sourceDialog").close(); };
$("sourceDialog").oncancel = (event) => { if (operation === "source") event.preventDefault(); };
$("sourceKind").onchange = () => {
  const camera = $("sourceKind").value === "camera";
  $("fileField").hidden = $("sourcePath").disabled = camera;
  $("cameraField").hidden = $("cameraIndex").disabled = !camera;
  $("sourcePath").required = !camera;
  $("cameraIndex").required = camera;
};
$("sourceForm").onsubmit = async (event) => {
  event.preventDefault();
  if (operation) return;
  const spec = $("sourceKind").value === "camera" ? `camera:${$("cameraIndex").value}` : $("sourcePath").value.trim();
  if (!spec) return;
  $("sourceError").hidden = true;
  $("connectSource").disabled = true;
  $("connectSource").textContent = "Connecting…";
  setOperation("source", "Connecting the capture source…");
  try {
    const next = await api("/api/source", { spec });
    applyState(next, true);
    view = "live";
    updateView();
    if (!next.source) throw new Error(next.source_error || "This source could not be opened.");
    // Restore the opener before closing so keyboard focus can return to it.
    setOperation("");
    $("sourceDialog").close();
    toast("Capture source connected.");
  } catch (error) { $("sourceError").textContent = error.message; $("sourceError").hidden = false; }
  finally { $("connectSource").disabled = false; $("connectSource").innerHTML = `Connect source${icon("arrow")}`; setOperation(""); }
};

async function loadProposals() {
  try {
    const list = await api("/api/proposals", undefined, "GET");
    const pending = list.filter((p) => p.status === "pending").length;
    $("policyCount").hidden = !pending;
    $("policyCount").textContent = pending;
    $("policyBadge").textContent = `${pending} pending`;
    $("policyBadge").className = `badge ${pending ? "badge-amber" : "badge-neutral"}`;
    $("policySummary").textContent = pending ? `${pending} proposal${pending === 1 ? "" : "s"} awaiting a named reviewer.` : "Amendments and recalls found by research. Every change goes through Decionis and a named reviewer.";
    $("proposals").innerHTML = list.length ? list.map((p) => {
      const verdict = p.exchange?.result || {};
      const findings = (p.findings || []).map((f) => `<li>${esc(f.title)} <span class="muted">· ${esc(sceneName(f.scene))}</span>${f.allowlisted ? "" : ' <span class="bad">Source not on allowlist</span>'}</li>`).join("");
      // A proposal the gate never decided can be rejected, never approved.
      const decided = !!verdict.decision;
      const action = p.status === "pending" ? `<div class="proposal-form">${decided ? "" : '<p class="warning small">The gate call failed, so Decionis never decided this proposal. It can only be rejected; run the research again to send a new proposal through the gate.</p>'}<div class="field"><label for="who-${esc(p.id)}">Reviewer’s full name</label><input id="who-${esc(p.id)}" placeholder="Enter your full name" autocomplete="name" aria-describedby="error-${esc(p.id)}"></div><div id="error-${esc(p.id)}" class="inline-error" role="alert" hidden></div><div class="button-row">${decided ? `<button class="btn btn-sm" data-proposal-action="approve" data-proposal-id="${esc(p.id)}">Approve proposal</button>` : ""}<button class="btn btn-sm btn-danger" data-proposal-action="reject" data-proposal-id="${esc(p.id)}">Reject proposal</button></div></div>`
        : `<div class="proposal-resolution">${p.status === "approved" ? "Approved" : p.status === "rejected" ? "Rejected" : esc(p.status)} by ${esc(p.resolved_by || "—")}${p.resolved_at ? ` · ${esc(dateTime(p.resolved_at))}` : ""}</div>${p.note ? `<details class="disclosure"><summary>${icon("chevron", "chevron")}Reviewer’s reason</summary><p>${esc(p.note)}</p></details>` : ""}`;
      return `<article class="proposal"><div class="proposal-heading"><strong>${esc(jurisdictionName(p.jurisdiction))}</strong><span class="badge badge-neutral">${decided ? `Decionis ${esc(verdict.decision)}` : "No Decionis decision"}</span><code class="muted">${esc(p.id.slice(0, 8))}</code>${verdict.dossier_id ? `<a class="small" href="/dossier?id=${encodeURIComponent(verdict.dossier_id)}" target="_blank" rel="noopener">Dossier ${icon("external")}</a>` : ""}</div><ul>${findings}</ul>${action}</article>`;
    }).join("") : '<p class="empty-copy" style="padding:20px 0">No policy proposals to review.</p>';
    controls();
  } catch (error) {
    $("policySummary").textContent = "Policy proposals could not be loaded.";
    $("proposals").innerHTML = `<div style="padding:20px 0"><p class="inline-error">${esc(error.message)}</p><button class="btn btn-sm" data-retry-proposals>Try again</button></div>`;
  }
}

$("proposals").onclick = async (event) => {
  if (event.target.closest("[data-retry-proposals]")) { loadProposals(); return; }
  const button = event.target.closest("[data-proposal-action]");
  if (!button || operation || !connected) return;
  const id = button.dataset.proposalId;
  const name = $(`who-${id}`);
  const errorField = $(`error-${id}`);
  const approver = name.value.trim();
  if (!approver) { errorField.textContent = "Enter the name of the person reviewing this proposal."; errorField.hidden = false; name.focus(); return; }
  setOperation("proposal", "Recording the policy review…");
  try {
    await api(`/api/proposals/${encodeURIComponent(id)}/resolve`, { approve: button.dataset.proposalAction === "approve", approver });
    await loadProposals();
    toast("Policy review recorded.");
  } catch (error) { errorField.textContent = error.message; errorField.hidden = false; }
  finally { setOperation(""); }
};

document.querySelectorAll("[data-nav]").forEach((link) => {
  link.onclick = () => {
    document.querySelectorAll("[data-nav]").forEach((item) => { item.classList.toggle("active", item === link); item === link ? item.setAttribute("aria-current", "location") : item.removeAttribute("aria-current"); });
    if (link.dataset.nav === "policy") $("policy").open = true;
    $("breadcrumbCurrent").textContent = { inspection: "Inspections", evidence: "Evidence & proof", policy: "Policy review" }[link.dataset.nav];
  };
});

api("/api/state", undefined, "GET").then((next) => { if (!state) applyState(next); }).catch((error) => { setConnection(false); toast(`Could not load the workspace: ${error.message}`); });
loadProposals();
connectState((message) => {
  if (message.type === "state") applyState(message.state);
  if (message.type === "result") render(message.result);
  if (message.type === "resolution" && last?.record_id === message.record_id) render({ ...last, resolution: message.resolution, light: message.light });
}, setConnection);
