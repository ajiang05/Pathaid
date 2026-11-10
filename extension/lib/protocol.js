export const API_BASE = "http://127.0.0.1:8000";
export const MESSAGE_TYPES = Object.freeze([
  "CONFIGURE", "CLEAR_TOKEN", "GET_STATE", "PING", "INSPECT_ACTIVE_PAGE", "FILL_PREVIEW", "ATTACH_DOCUMENT",
]);

export function validToken(value) {
  return typeof value === "string" && /^[A-Za-z0-9_-]{43,256}$/.test(value);
}

export function parseMessage(value) {
  if (!value || typeof value !== "object" || !MESSAGE_TYPES.includes(value.type)) {
    throw new Error("Unsupported extension request");
  }
  if (value.type === "CONFIGURE" && !validToken(value.token)) {
    throw new Error("Invalid installation token");
  }
  if (value.type === "FILL_PREVIEW") {
    if (typeof value.previewId !== "string" || !/^[a-f0-9-]{36}$/.test(value.previewId)) {
      throw new Error("Invalid preview identifier");
    }
    if (!Array.isArray(value.approvedFieldIds) || value.approvedFieldIds.length > 200 || value.approvedFieldIds.some(item => typeof item !== "string" || item.length > 120)) {
      throw new Error("Invalid approved field list");
    }
    if (!Array.isArray(value.corrections) || value.corrections.length > 200 || value.corrections.some(item => (
      !item || typeof item !== "object" || typeof item.fieldId !== "string" || item.fieldId.length > 120
      || (item.profileField !== null && (typeof item.profileField !== "string" || item.profileField.length > 80))
    ))) {
      throw new Error("Invalid mapping corrections");
    }
    const correctionIds = value.corrections.map(item => item.fieldId);
    if (correctionIds.length !== new Set(correctionIds).size) throw new Error("Duplicate mapping correction");
    return {
      type: value.type, previewId: value.previewId,
      approvedFieldIds: [...new Set(value.approvedFieldIds)],
      corrections: value.corrections.map(item => ({ fieldId: item.fieldId, profileField: item.profileField })),
    };
  }
  if (value.type === "ATTACH_DOCUMENT") {
    if (typeof value.previewId !== "string" || !/^[a-f0-9-]{36}$/.test(value.previewId)) throw new Error("Invalid preview identifier");
    if (typeof value.fieldId !== "string" || value.fieldId.length > 120) throw new Error("Invalid attachment field");
    if (!["resume", "transcript", "essay"].includes(value.documentType)) throw new Error("Invalid document type");
    if (value.documentType === "essay" && (typeof value.essayId !== "string" || !value.essayId)) throw new Error("Essay selection required");
    return { type: value.type, previewId: value.previewId, fieldId: value.fieldId, documentType: value.documentType, ...(value.essayId ? { essayId: value.essayId } : {}) };
  }
  return value.type === "CONFIGURE" ? { type: value.type, token: value.token } : { type: value.type };
}

export function publicConnectionState(stored) {
  return {
    configured: validToken(stored.token),
    connected: stored.connected === true,
    lastCheckedAt: typeof stored.lastCheckedAt === "string" ? stored.lastCheckedAt : null,
  };
}
