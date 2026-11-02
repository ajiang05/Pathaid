import { API_BASE, parseMessage, publicConnectionState } from "./lib/protocol.js";

const STORAGE_KEYS = ["token", "connected", "lastCheckedAt"];

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

async function portalContext(origin) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  if (!stored.token) throw new Error("PathAid is not configured");
  const url = new URL(`${API_BASE}/api/extension/context`);
  url.searchParams.set("portal_origin", origin);
  const response = await fetch(url, { headers: { "X-PathAid-Token": stored.token } });
  if (!response.ok) throw new Error("PathAid rejected the portal context");
  return response.json();
}

async function inspectActivePage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !/^https?:/.test(tab.url || "")) {
    return { state: "unsupported", reason: "Open a public scholarship application page." };
  }
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    // This intentionally returns only non-sensitive page metadata. Form values
    // and page text are neither read nor persisted by the foundation feature.
    func: () => ({ origin: location.origin, formCount: document.forms.length }),
  });
  const context = await portalContext(injection.result.origin);
  if (context.state !== "supported") return context;
  return { ...context, formCount: injection.result.formCount };
}

chrome.runtime.onMessage.addListener((raw, _sender, sendResponse) => {
  (async () => {
    const message = parseMessage(raw);
    if (message.type === "CONFIGURE") {
      await chrome.storage.local.set({ token: message.token, connected: false, lastCheckedAt: null });
      return ping();
    }
    if (message.type === "CLEAR_TOKEN") {
      await chrome.storage.local.remove(STORAGE_KEYS);
      return publicConnectionState({});
    }
    if (message.type === "GET_STATE") {
      return publicConnectionState(await chrome.storage.local.get(STORAGE_KEYS));
    }
    if (message.type === "PING") return ping();
    return inspectActivePage();
  })().then(
    result => sendResponse({ ok: true, result }),
    error => sendResponse({ ok: false, error: error instanceof Error ? error.message : "Extension request failed" }),
  );
  return true;
});
