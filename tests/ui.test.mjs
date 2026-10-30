import test from "node:test";
import assert from "node:assert/strict";
import { inspectionMessage, limitText, matchesSelection, measurementName, measurementValue, presentation, released, safeUrl, sourceName } from "../static/ui.mjs";

test("a disconnected workspace cannot display a stale green release", () => {
  const status = presentation({ color: "green", label: "ALLOW" }, { connected: false });
  assert.equal(status.color, "off");
  assert.equal(status.label, "CONNECTION LOST");
});

test("an ALLOW whose execution was not confirmed stays closed", () => {
  const status = presentation({ color: "red", label: "NOT RELEASED" });
  assert.equal(status.color, "red");
  assert.equal(status.title, "Hold stays closed");
});

test("mock data cannot present itself as a live release", () => {
  const status = presentation({ color: "green", label: "ALLOW" }, { mock: true });
  assert.equal(status.color, "red");
  assert.equal(status.label, "MOCK GATE");
});

test("a human release retains its separate attribution and blue signal", () => {
  const status = presentation({ color: "blue", label: "RELEASED BY ADA INSPECTOR" });
  assert.equal(status.color, "blue");
  assert.equal(status.label, "RELEASED BY ADA INSPECTOR");
  assert.equal(status.kicker, "Released by a person");
});

test("unknown signals cannot claim a release", () => {
  for (const light of [null, {}, { color: "unknown", label: "ALLOW" }]) {
    assert.equal(presentation(light).color, "off");
    assert.equal(presentation(light).label, "NO INSPECTION");
  }
});

test("result context matches scene, condition and jurisdiction together", () => {
  const result = { scene: "decking", condition: "clean", jurisdiction: "US" };
  assert.equal(matchesSelection(result, "decking", "clean", "US"), true);
  assert.equal(matchesSelection(result, "trench", "clean", "US"), false);
  assert.equal(matchesSelection(result, "decking", "rain", "US"), false);
  assert.equal(matchesSelection(result, "decking", "clean", "SE"), false);
});

test("a zero measurement and a negative sound detection remain evidence", () => {
  assert.deepEqual(measurementValue({ kind: "gap_mm", value: 0 }), { value: "0", unit: "mm" });
  assert.deepEqual(measurementValue({ kind: "seat_audio", value: false }), { value: "Not detected", unit: "" });
});

test("operator guidance distinguishes an unconfirmed release from missing calibration", () => {
  const record = { verdict: { decision: "ALLOW", grant_error: "CLAIM_UNRESOLVED" }, errors: ["fiducial[0]: marker not found"] };
  assert.match(inspectionMessage(record), /did not complete the release/);
  assert.match(inspectionMessage({ ...record, verdict: { decision: "ESCALATE" } }), /calibration marker was not found/);
});

test("citation links reject executable schemes and embedded credentials", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,test", "file:///etc/passwd", "https://name:secret@example.com", "not a url"]) {
    assert.equal(safeUrl(url), "");
  }
  assert.equal(safeUrl("https://www.osha.gov/laws-regs"), "https://www.osha.gov/laws-regs");
});

test("a green release says it was finalized, not that the physical effect was confirmed", () => {
  assert.equal(presentation({ color: "green", label: "ALLOW" }).kicker, "Release finalized");
  const stored = { verdict: { decision: "ALLOW", should_execute: true, grant_claimed: true, grant_finalized: true }, citations: [{}] };
  assert.equal(released(stored), true);
  assert.match(inspectionMessage(stored), /claimed its single-use grant and finalized it/);
  assert.equal(released({ verdict: { ...stored.verdict, grant_finalized: false } }), false);
});

test("limits read as ranges with units", () => {
  assert.equal(limitText({ min: 3.175, max: 6.35 }, "gap_mm"), "3.175–6.35 mm");
  assert.equal(limitText({ min: null, max: 34 }, "slope_deg"), "≤ 34°");
  assert.equal(limitText({ min: 2 }, "depth_mm"), "≥ 2 mm");
  assert.equal(limitText({}, "gap_mm"), "No numeric limit");
});

test("angles are named for the scene, and sources without their scheme", () => {
  assert.equal(measurementName("angle_deg", "decking"), "Board angle");
  assert.equal(measurementName("angle_deg", "plumbing"), "Pipe alignment");
  assert.equal(measurementName("slope_deg", "trench"), "Wall slope");
  assert.equal(sourceName("file:decking-ok.mp4"), "decking-ok.mp4");
  assert.equal(sourceName("camera:0"), "Camera 0");
});

test("a re-decided ALLOW says a fresh inspection is needed to release", () => {
  const record = { regrounded_from: "r1", verdict: { decision: "ALLOW", grant_error: "not claimed: re-decided evidence" }, citations: [{}] };
  assert.match(inspectionMessage(record), /re-decision never releases the hold/);
});
