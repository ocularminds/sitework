import { $, api, conditionName, dateTime, esc, hydrateIcons, icon, inspectionMessage, measurementName, measurementValue, proofMarkup, safeUrl, sceneName } from "./ui.mjs";

hydrateIcons();
const id = new URLSearchParams(location.search).get("id") || "";
let busy = false;
let verifiable = !!id && !id.startsWith("mock-") && !id.startsWith("no-decision-");
$("id").textContent = id || "No dossier selected";

function controls() {
  ["offline", "pinned", "tamper"].forEach((name) => { $(name).disabled = busy || !verifiable; });
}

async function verify(mode) {
  if (busy || !verifiable) return;
  busy = true;
  controls();
  $("proof").textContent = mode === "pinned" ? "Checking against Decionis’s published key…" : "Verifying the saved signed artifacts…";
  try {
    const result = await api(`/api/dossiers/${encodeURIComponent(id)}/verify?mode=${mode}`);
    $("proof").innerHTML = proofMarkup(result);
    $("verificationBadge").textContent = result.verified ? "Signature valid" : "Invalid";
    $("verificationBadge").className = `badge ${result.verified ? "badge-blue" : "badge-red"}`;
  } catch (error) { $("proof").textContent = `Verification failed: ${error.message}`; }
  finally { busy = false; controls(); }
}
$("offline").onclick = () => verify("offline");
$("pinned").onclick = () => verify("pinned");
$("tamper").onclick = async () => {
  if (busy || !verifiable) return;
  busy = true;
  controls();
  $("proof").textContent = "Changing one byte in a copy, then verifying the altered copy…";
  try {
    const result = await api(`/api/dossiers/${encodeURIComponent(id)}/tamper`);
    $("proof").innerHTML = `Copy changed at <code>${esc(result.pointer)}</code>: “${esc(result.before)}” → “${esc(result.after)}” (${esc(result.bytes_changed)} byte)<br>${proofMarkup(result.result)}`;
  } catch (error) { $("proof").textContent = `Tamper test failed: ${error.message}`; }
  finally { busy = false; controls(); }
};

function renderRecord(record) {
  const verdict = record.exchange?.result || {};
  const evidence = record.evidence;
  const mock = record.gate_mode === "mock";
  verifiable = verifiable && !mock && !!verdict.dossier_id;
  $("mock").hidden = !mock;
  $("recordMode").textContent = mock ? "MOCK GATE" : "Decionis record";
  $("recordMode").className = `badge ${mock ? "badge-red" : "badge-neutral"}`;
  $("recordStatus").textContent = dateTime(record.created_at);
  const verdictColor = verdict.decision === "ALLOW" ? "var(--blue)" : ["ESCALATE", "REVIEW_REQUIRED"].includes(verdict.decision) ? "var(--amber)" : "var(--red)";
  const explanation = inspectionMessage({ ...evidence, verdict: verdict.decision ? verdict : null, failure: verdict.error ? verdict : null });
  $("summary").innerHTML = `<div><span class="summary-decision" style="color:${verdictColor}">${esc(verdict.decision || "NO DECISION")}</span><span>${esc(explanation)}</span></div>
    <div class="summary-context">${[sceneName(evidence.scene), conditionName(evidence.condition), record.jurisdiction, `Policy ${verdict.policy_version || "—"}`].map((text) => `<span class="badge badge-neutral">${esc(text)}</span>`).join("")}</div>
    <p class="muted small" style="margin-top:12px">${esc(evidence.action)}</p>
    <details class="disclosure"><summary>${icon("chevron", "chevron")}Decision details</summary><code style="white-space:pre-wrap">${esc([verdict.reason, verdict.grant_error, verdict.error].filter(Boolean).join("\n"))}</code></details>
    ${record.regrounded_from ? `<p class="small muted">Re-evaluated from <a href="/dossier?id=${encodeURIComponent(record.regrounded_from)}">${esc(record.regrounded_from.slice(0, 12))}…</a></p>` : ""}
    ${record.resolution ? `<div class="resolution" style="margin:14px 0 0"><strong style="color:var(--${record.resolution.release ? "blue" : "red"})">${record.resolution.release ? "Released" : "Kept on hold"} by ${esc(record.resolution.approver)}</strong>${esc(dateTime(record.resolution.at))}${record.resolution.note ? ` · ${esc(record.resolution.note)}` : ""}</div>` : ""}`;
  $("evidencePanel").hidden = false;
  $("evidenceCount").textContent = `${evidence.measurements.length} measurements`;
  const rows = evidence.measurements.map((measurement) => {
    const value = measurementValue(measurement);
    return `<tr><td class="measure-name">${esc(measurementName(measurement.kind))}</td><td class="num measure-value">${esc(value.value)} <small>${esc(value.unit)}</small></td><td class="num">${Number.isFinite(measurement.confidence) ? `${(measurement.confidence * 100).toFixed(0)}%` : "—"}</td><td class="muted">${esc(measurement.method)}</td></tr>`;
  }).join("");
  const citations = evidence.citations.map((citation) => {
    const url = safeUrl(citation.url);
    return `<p>${esc(citation.requirement)}<br>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(citation.source_domain)} ${icon("external")}</a>` : esc(citation.source_domain)}<br><code class="muted">SHA-256 ${esc(citation.content_sha256)}</code></p>`;
  }).join("");
  $("evidence").innerHTML = `<div class="table-wrap"><table><caption class="sr-only">Recorded measurements and confidence</caption><thead><tr><th scope="col">Measurement</th><th scope="col" class="num">Value</th><th scope="col" class="num">Confidence</th><th scope="col">Method</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">No measurements recorded.</td></tr>'}</tbody></table></div>
    <div class="evidence-citations">${citations || '<p class="warning">No approved citation was included in this evidence.</p>'}</div>
    ${evidence.errors.length ? `<ul class="error-list" style="padding:0">${evidence.errors.map((error) => `<li>${esc(error)}</li>`).join("")}</ul>` : ""}
    <details class="disclosure evidence-provenance"><summary>${icon("chevron", "chevron")}Capture provenance & models</summary><div>Frame hashes: ${evidence.frame_sha256.map((hash) => `<code>${esc(hash)}</code>`).join("<br>") || "none"}<br>Models called: <code>${esc(JSON.stringify(evidence.models))}</code></div></details>`;
  const facts = Object.entries(record.exchange?.request?.context || {}).filter(([key]) => key.startsWith("sitework_"));
  $("factsPanel").hidden = !facts.length;
  $("facts").innerHTML = facts.map(([key, value]) => `<tr><td><code>${esc(key)}</code></td><td>${esc(JSON.stringify(value))}</td></tr>`).join("");
  if (!verifiable) $("proof").textContent = "This record has no signed Decionis dossier to verify.";
}

async function load() {
  if (!id) {
    $("summary").innerHTML = '<div class="empty-document"><h3>Select a decision dossier</h3><p class="muted">Open a dossier from an inspection or policy proposal to review its evidence.</p><a class="btn btn-sm" href="/" style="margin-top:14px">Go to workspace</a></div>';
    $("recordStatus").textContent = "No record selected";
    return;
  }
  try {
    const response = await fetch(`/api/dossiers/${encodeURIComponent(id)}`);
    if (response.status === 404) {
      $("summary").textContent = "No local inspection record was found. For a policy proposal or another Decionis decision, you can still verify its signed dossier below.";
      $("recordStatus").textContent = "No local inspection";
    } else {
      if (!response.ok) throw new Error("The inspection record could not be loaded.");
      renderRecord(await response.json());
    }
  } catch (error) { $("summary").textContent = error.message; $("recordStatus").textContent = "Record unavailable"; }
  controls();
}
load();
