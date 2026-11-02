import { API_BASE, parseMessage, publicConnectionState } from "./lib/protocol.js";
import { buildFillPlan } from "./lib/adapter-contract.js";
import { mapGenericFields } from "./lib/generic-adapter.js";

const STORAGE_KEYS = ["token", "connected", "lastCheckedAt"];
const activePreviews = new Map();

chrome.runtime.onInstalled.addListener(() => {
  // Chrome opens the panel only after the student clicks the toolbar action.
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
});

async function ping() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  if (!stored.token) throw new Error("PathAid is not configured");
  const response = await fetch(`${API_BASE}/api/extension/ping`, {
    headers: { "X-PathAid-Token": stored.token },
  });
  const checked = new Date().toISOString();
  await chrome.storage.local.set({ connected: response.ok, lastCheckedAt: checked });
  if (!response.ok) throw new Error("PathAid rejected the local connection");
  return publicConnectionState({ ...stored, connected: true, lastCheckedAt: checked });
}

async function authenticatedGet(path, parameters = {}) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  if (!stored.token) throw new Error("PathAid is not configured");
  const url = new URL(`${API_BASE}${path}`);
  for (const [name, value] of Object.entries(parameters)) url.searchParams.set(name, value);
  const response = await fetch(url, {
    cache: "no-store", headers: { "X-PathAid-Token": stored.token },
  });
  if (!response.ok) throw new Error("PathAid rejected the extension request");
  return response.json();
}

async function portalContext(origin, scholarshipId = null) {
  const parameters = { portal_origin: origin };
  if (scholarshipId) parameters.scholarship_id = scholarshipId;
  return authenticatedGet("/api/extension/context", parameters);
}

async function activeTabPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !/^https?:/.test(tab.url || "")) return null;
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId: tab.id }, func: () => ({ origin: location.origin, formCount: document.forms.length }),
  });
  return { tab, ...injection.result };
}

async function inspectActivePage() {
  const page = await activeTabPage();
  if (!page) {
    return { state: "unsupported", reason: "Open a public scholarship application page." };
  }
  const context = await portalContext(page.origin);
  if (context.state !== "supported") return context;
  if (context.adapter !== "generic") {
    return { state: "unsupported", reason: `The ${context.adapter} adapter is not implemented yet.` };
  }
  await chrome.scripting.executeScript({ target: { tabId: page.tab.id }, files: ["content/generic-runtime.js"] });
  const inspection = await chrome.tabs.sendMessage(page.tab.id, { type: "PATHAID_INSPECT_GENERIC" });
  if (!inspection?.ok || !Array.isArray(inspection.descriptors)) throw new Error("The page could not be inspected safely");
  const profile = await authenticatedGet("/api/extension/profile-values", {
    portal_origin: page.origin, scholarship_id: context.scholarship_id,
  });
  const descriptors = inspection.descriptors.slice(0, 200);
  const mappings = mapGenericFields(descriptors, profile.fields);
  const previewId = crypto.randomUUID();
  activePreviews.set(previewId, {
    tabId: page.tab.id, portalOrigin: page.origin, scholarshipId: context.scholarship_id,
    descriptors, mappings, createdAt: Date.now(),
  });
  return { ...context, formCount: page.formCount, preview: { id: previewId, fields: mappings } };
}

async function fillPreview(message) {
  const preview = activePreviews.get(message.previewId);
  if (!preview || Date.now() - preview.createdAt > 15 * 60 * 1000) {
    activePreviews.delete(message.previewId);
    throw new Error("The preview expired. Inspect the page again.");
  }
  const page = await activeTabPage();
  if (!page || page.tab.id !== preview.tabId || page.origin !== preview.portalOrigin) {
    throw new Error("The active page changed. Inspect it again.");
  }
  const context = await portalContext(page.origin, preview.scholarshipId);
  if (context.state !== "supported" || context.scholarship_id !== preview.scholarshipId) {
    throw new Error("The scholarship context is no longer valid.");
  }
  const approved = new Set(message.approvedFieldIds);
  const mappings = preview.mappings.map(item => ({ ...item, approved: item.status === "mapped" && approved.has(item.fieldId) }));
  const plan = buildFillPlan(preview.descriptors, mappings);
  const response = await chrome.tabs.sendMessage(preview.tabId, { type: "PATHAID_FILL_GENERIC", plan });
  if (!response?.ok) throw new Error("The approved fields could not be filled.");
  activePreviews.delete(message.previewId);
  return response.result;
}

chrome.runtime.onMessage.addListener((raw, _sender, sendResponse) => {
  (async () => {
    const message = parseMessage(raw);
    if (message.type === "CONFIGURE") {
      await chrome.storage.local.set({ token: message.token, connected: false, lastCheckedAt: null });
      return ping();
    }
    if (message.type === "CLEAR_TOKEN") {
      activePreviews.clear();
      await chrome.storage.local.remove(STORAGE_KEYS);
      return publicConnectionState({});
    }
    if (message.type === "GET_STATE") {
      return publicConnectionState(await chrome.storage.local.get(STORAGE_KEYS));
    }
    if (message.type === "PING") return ping();
    if (message.type === "INSPECT_ACTIVE_PAGE") return inspectActivePage();
    return fillPreview(message);
  })().then(
    result => sendResponse({ ok: true, result }),
    error => sendResponse({ ok: false, error: error instanceof Error ? error.message : "Extension request failed" }),
  );
  return true;
});
