import { $, api, connectState, dateTime, hydrateIcons, icon, presentation } from "./ui.mjs";

hydrateIcons();
let light = { color: "off", label: "NO INSPECTION" };
let mode = "live";
let connected = false;
let loaded = false;

function render() {
  const p = presentation(light, { connected: connected || !loaded, mock: mode === "mock" });
  document.body.className = `light-page ${p.color}`;
  $("mock").hidden = mode !== "mock";
  $("label").textContent = p.label;
  $("signalKicker").textContent = p.kicker;
  $("signalIcon").innerHTML = icon(p.icon);
  $("sub").textContent = !connected && loaded ? "The current hold status cannot be confirmed. Reconnect to the workspace."
    : mode === "mock" ? "Test environment. This signal does not authorize a live release."
      : p.color === "blue" ? "A named person recorded this release. It is not an automatic gate approval."
        : p.color === "green" ? "Decionis allowed the action and the execution was finalized."
          : p.color === "amber" ? "Keep the hold in place. A named person must review the evidence."
            : p.color === "red" ? "Keep the hold in place. Check the inspection workspace for details."
              : "Waiting for an inspection from the workspace.";
}

function applyState(state) {
  light = state.light;
  mode = state.gate_mode;
  loaded = true;
  $("updated").textContent = `Updated ${dateTime(new Date().toISOString(), true)}`;
  render();
}

connectState((message) => {
  if (message.type === "state") applyState(message.state);
  if (message.type === "result" || message.type === "resolution") {
    light = message.light || message.result?.light;
    $("updated").textContent = `Updated ${dateTime(new Date().toISOString(), true)}`;
    render();
  }
}, (value) => {
  connected = value;
  $("connection").dataset.status = value ? "connected" : "disconnected";
  $("connectionLabel").textContent = value ? "Workspace connected" : "Connection lost · reconnecting";
  render();
});
api("/api/state", undefined, "GET").then((state) => { if (!loaded) applyState(state); }).catch(() => { loaded = true; render(); });

$("fullscreen").onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { $("fullscreenLabel").textContent = "Full screen unavailable"; }
};
document.addEventListener("fullscreenchange", () => {
  $("fullscreen").setAttribute("aria-pressed", String(!!document.fullscreenElement));
  $("fullscreenLabel").textContent = document.fullscreenElement ? "Exit full screen" : "Full screen";
});
