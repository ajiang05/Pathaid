import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { parseMessage, publicConnectionState, validToken } from "../lib/protocol.js";

test("tokens and messages are narrow and validated", () => {
  const token = "a".repeat(64);
  assert.equal(validToken(token), true);
  assert.equal(validToken("short"), false);
  assert.deepEqual(parseMessage({ type: "CONFIGURE", token, ignored: "value" }), { type: "CONFIGURE", token });
  assert.throws(() => parseMessage({ type: "FILL" }), /Unsupported/);
  assert.throws(() => parseMessage({ type: "CONFIGURE", token: "bad" }), /Invalid/);
  const previewId = "123e4567-e89b-12d3-a456-426614174000";
  assert.deepEqual(parseMessage({
    type: "FILL_PREVIEW", previewId, approvedFieldIds: ["first", "first", "email"],
  }), { type: "FILL_PREVIEW", previewId, approvedFieldIds: ["first", "email"] });
  assert.throws(() => parseMessage({ type: "FILL_PREVIEW", previewId: "bad", approvedFieldIds: [] }), /preview/);
  assert.deepEqual(publicConnectionState({ token, connected: true, lastCheckedAt: "now", private: "omit" }), {
    configured: true, connected: true, lastCheckedAt: "now",
  });
});

test("manifest uses only approved permissions and no persistent content script", async () => {
  const manifest = JSON.parse(await readFile(new URL("../manifest.json", import.meta.url), "utf8"));
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions.sort(), ["activeTab", "scripting", "sidePanel", "storage"].sort());
  assert.deepEqual(manifest.host_permissions, ["http://127.0.0.1:8000/*"]);
  assert.equal("content_scripts" in manifest, false);
});

test("foundation exposes no submission or certification action", async () => {
  const worker = await readFile(new URL("../service-worker.js", import.meta.url), "utf8");
  const panel = await readFile(new URL("../sidepanel.html", import.meta.url), "utf8");
  assert.doesNotMatch(worker, /requestSubmit|\.submit\s*\(|\.click\s*\(/);
  assert.doesNotMatch(worker, /console\./);
  assert.doesNotMatch(panel, />\s*(Submit|Certify|Sign)\s*</i);
});

test("on-demand generic runtime never clicks or submits and binds inspected elements", async () => {
  const runtime = await readFile(new URL("../content/generic-runtime.js", import.meta.url), "utf8");
  assert.doesNotMatch(runtime, /requestSubmit|\.submit\s*\(|\.click\s*\(/);
  assert.match(runtime, /registry\.get\(item\.fieldId\)/);
  assert.ok(runtime.indexOf("registry.set(id, registered)") < runtime.indexOf("if (seen.has(id)) return"));
  assert.doesNotMatch(runtime, /localStorage|sessionStorage|chrome\.storage/);
});
