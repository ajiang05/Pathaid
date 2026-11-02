export const API_BASE = "http://127.0.0.1:8000";
export const MESSAGE_TYPES = Object.freeze([
  "CONFIGURE", "CLEAR_TOKEN", "GET_STATE", "PING", "INSPECT_ACTIVE_PAGE", "FILL_PREVIEW",
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
    return { type: value.type, previewId: value.previewId, approvedFieldIds: [...new Set(value.approvedFieldIds)] };
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
