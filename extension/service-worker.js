import { API_BASE, parseMessage, publicConnectionState } from "./lib/protocol.js";
import { buildFillPlan, normalizeDescriptor } from "./lib/adapter-contract.js";
import { genericAdapter } from "./lib/generic-adapter.js";
import { academicWorksAdapter } from "./lib/academicworks-adapter.js";
import { kaleidoscopeAdapter } from "./lib/kaleidoscope-adapter.js";
import { formSignatures } from "./lib/form-signatures.js";
import { mapDocumentTargets } from "./lib/document-targets.js";

const STORAGE_KEYS = ["token", "connected", "lastCheckedAt"];
const activePreviews = new Map();
const adapters = Object.freeze([academicWorksAdapter, kaleidoscopeAdapter, genericAdapter]);

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

async function authenticatedPut(path, payload) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  if (!stored.token) throw new Error("PathAid is not configured");
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT", cache: "no-store",
    headers: { "X-PathAid-Token": stored.token, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("PathAid rejected the mapping update");
  return response.json();
}

async function authenticatedDownload(path, parameters = {}) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  if (!stored.token) throw new Error("PathAid is not configured");
  const url = new URL(`${API_BASE}${path}`);
  for (const [name, value] of Object.entries(parameters)) url.searchParams.set(name, value);
  const response = await fetch(url, {
    cache: "no-store", headers: { "X-PathAid-Token": stored.token },
  });
  if (!response.ok) throw new Error("The encrypted document is unavailable");
  return {
    bytes: new Uint8Array(await response.arrayBuffer()),
    filename: decodeURIComponent(response.headers.get("X-PathAid-Filename") || "document.pdf"),
    contentType: response.headers.get("Content-Type")?.split(";", 1)[0] || "application/octet-stream",
  };
}

function base64Bytes(bytes) {
  const chunks = [];
  for (let index = 0; index < bytes.length; index += 0x8000) {
    chunks.push(String.fromCharCode(...bytes.subarray(index, index + 0x8000)));
  }
  return btoa(chunks.join(""));
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
  const adapter = adapters.find(candidate => candidate.matches(context));
  if (!adapter) {
    return { state: "unsupported", reason: `The ${context.adapter} adapter is not implemented yet.` };
  }
  await chrome.scripting.executeScript({ target: { tabId: page.tab.id }, files: ["content/generic-runtime.js"] });
  const inspection = await chrome.tabs.sendMessage(page.tab.id, { type: "PATHAID_INSPECT_GENERIC" });
  if (!inspection?.ok || !Array.isArray(inspection.descriptors)) throw new Error("The page could not be inspected safely");
  const profile = await authenticatedGet("/api/extension/profile-values", {
    portal_origin: page.origin, scholarship_id: context.scholarship_id,
  });
  const documents = await authenticatedGet("/api/extension/documents", {
    portal_origin: page.origin, scholarship_id: context.scholarship_id,
  });
  const descriptors = inspection.descriptors.slice(0, 200);
  const signatures = await formSignatures(descriptors);
  const learned = await authenticatedGet("/api/extension/mappings", {
    portal_origin: page.origin, scholarship_id: context.scholarship_id,
    form_signature: signatures.formSignature,
  });
  const learnedBySignature = new Map(learned.mappings.map(item => [item.field_signature, item.profile_field]));
  const profileByName = new Map(profile.fields.map(item => [item.name, item]));
  const mappings = adapter.map(descriptors, profile.fields).map((mapping, index) => {
    const fieldSignature = signatures.fieldSignatures[index];
    const learnedName = learnedBySignature.get(fieldSignature);
    const learnedField = profileByName.get(learnedName);
    const correctable = !normalizeDescriptor(descriptors[index]).blockedReason;
    if (correctable && learnedField && ["string", "number", "boolean"].includes(typeof learnedField.value)) {
      return {
        fieldId: mapping.fieldId, label: mapping.label, status: "mapped",
        profileField: learnedField.name, profileLabel: learnedField.label,
        value: learnedField.value, sensitive: learnedField.sensitive === true,
        confidence: "exact", approved: false, learned: true,
        fieldSignature, correctable,
      };
    }
    return { ...mapping, fieldSignature, correctable };
  });
  const availableDocuments = new Map(documents.items.map(item => [item.document_type, item]));
  const attachments = mapDocumentTargets(Array.isArray(inspection.attachmentTargets) ? inspection.attachmentTargets : [])
    .filter(target => !target.blockedReason)
    .map(target => ({
      ...target,
      available: target.documentType === "essay" ? documents.essays.length > 0 : availableDocuments.has(target.documentType),
      originalName: availableDocuments.get(target.documentType)?.original_name || null,
      essayOptions: target.documentType === "essay" ? documents.essays : [],
    }));
  const previewId = crypto.randomUUID();
  activePreviews.set(previewId, {
    tabId: page.tab.id, portalOrigin: page.origin, scholarshipId: context.scholarship_id,
    descriptors, mappings, attachments, profileFields: profile.fields, formSignature: signatures.formSignature,
    createdAt: Date.now(),
  });
  return {
    ...context, formCount: page.formCount,
    preview: { id: previewId, fields: mappings, attachments, profileFields: profile.fields },
  };
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
  const profileByName = new Map(preview.profileFields.map(item => [item.name, item]));
  const byFieldId = new Map(preview.mappings.map(item => [item.fieldId, item]));
  const corrections = new Map(message.corrections.map(item => [item.fieldId, item.profileField]));
  const savedMappings = [];
  for (const correction of message.corrections) {
    const original = byFieldId.get(correction.fieldId);
    if (!original?.correctable) throw new Error("A mapping correction is no longer valid.");
    const field = correction.profileField === null ? null : profileByName.get(correction.profileField);
    if (correction.profileField !== null && (!field || !["string", "number", "boolean"].includes(typeof field.value))) {
      throw new Error("A corrected profile field is unavailable.");
    }
    savedMappings.push({ field_signature: original.fieldSignature, profile_field: correction.profileField });
  }
  const approved = new Set(message.approvedFieldIds);
  const mappings = preview.mappings.map(item => {
    if (!corrections.has(item.fieldId)) return { ...item, approved: item.status === "mapped" && approved.has(item.fieldId) };
    const field = profileByName.get(corrections.get(item.fieldId));
    if (!field) return { ...item, status: "skipped", approved: false };
    return {
      ...item, status: "mapped", profileField: field.name, profileLabel: field.label,
      value: field.value, sensitive: field.sensitive === true, confidence: "exact",
      approved: approved.has(item.fieldId),
    };
  });
  const plan = buildFillPlan(preview.descriptors, mappings);
  const response = await chrome.tabs.sendMessage(preview.tabId, { type: "PATHAID_FILL_GENERIC", plan });
  if (!response?.ok) throw new Error("The approved fields could not be filled.");
  if (savedMappings.length) {
    await authenticatedPut("/api/extension/mappings", {
      portal_origin: preview.portalOrigin, scholarship_id: preview.scholarshipId,
      form_signature: preview.formSignature, mappings: savedMappings,
    });
  }
  return response.result;
}

async function attachDocument(message) {
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
  const target = preview.attachments.find(item => (
    item.fieldId === message.fieldId && item.documentType === message.documentType
  ));
  if (!target?.available || target.requiresExplicitAction !== true) {
    throw new Error("The selected document target is unavailable.");
  }
  const contentPath = message.documentType === "essay"
    ? `/api/extension/essays/${encodeURIComponent(message.essayId)}/content`
    : `/api/extension/documents/${encodeURIComponent(message.documentType)}/content`;
  const document = await authenticatedDownload(
    contentPath,
    { portal_origin: preview.portalOrigin, scholarship_id: preview.scholarshipId },
  );
  let response;
  try {
    response = await chrome.tabs.sendMessage(preview.tabId, {
      type: "PATHAID_ATTACH_DOCUMENT", fieldId: target.fieldId,
      filename: document.filename, contentType: document.contentType, base64: base64Bytes(document.bytes),
    });
  } finally {
    document.bytes.fill(0);
  }
  if (!response?.ok || response.attached !== true) throw new Error("The document could not be attached to this field.");
  return { attached: true, documentType: message.documentType, filename: document.filename };
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
    if (message.type === "ATTACH_DOCUMENT") return attachDocument(message);
    return fillPreview(message);
  })().then(
    result => sendResponse({ ok: true, result }),
    error => sendResponse({ ok: false, error: error instanceof Error ? error.message : "Extension request failed" }),
  );
  return true;
});

chrome.runtime.onMessageExternal.addListener((raw, sender, sendResponse) => {
  (async () => {
    if (!raw || raw.type !== "OPEN_APPLICATION" || typeof raw.scholarshipId !== "string" || raw.scholarshipId.length > 36) {
      throw new Error("Unsupported web application request");
    }
    if (!["http://127.0.0.1:3000", "http://localhost:3000"].includes(sender.origin || "")) {
      throw new Error("Web application origin is not allowed");
    }
    // Create the extension-owned tab immediately from the user's Apply click.
    // The web page supplies no URL; only the authenticated backend may release
    // the retained official destination.
    const tab = await chrome.tabs.create({ url: "about:blank", active: true });
    if (!tab.id) throw new Error("Application tab could not be created");
    try {
      await chrome.sidePanel.open({ tabId: tab.id });
      const prepared = await authenticatedPut(`/api/extension/applications/${encodeURIComponent(raw.scholarshipId)}/prepare`, {});
      await chrome.tabs.update(tab.id, { url: prepared.application_url });
      return { opened: true, scholarshipId: prepared.scholarship_id };
    } catch (error) {
      await chrome.tabs.remove(tab.id).catch(() => undefined);
      throw error;
    }
  })().then(
    result => sendResponse({ ok: true, result }),
    error => sendResponse({ ok: false, error: error instanceof Error ? error.message : "Application could not be opened" }),
  );
  return true;
});
