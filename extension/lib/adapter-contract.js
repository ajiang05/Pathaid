const SAFE_CONTROLS = new Set([
  "text", "email", "tel", "url", "number", "date", "month",
  "select", "textarea", "radio", "checkbox",
]);
const FORBIDDEN_METHODS = new Set([
  "click", "fill", "attach", "setValue", "submit", "requestSubmit",
  "sign", "certify", "attest", "acceptTerms",
]);
const BLOCKED_SEMANTICS = /\b(signature|sign here|certif(?:y|ication)|attest|terms(?: of service)?|i agree|consent|authoriz(?:e|ation)|acknowledge|captcha|mfa|multi[- ]factor|verification code|one[- ]time code|password)\b/i;
const DOCUMENT_TYPES = Object.freeze(["resume", "transcript", "essay"]);

export function defineAdapter(adapter) {
  if (!adapter || typeof adapter !== "object" || typeof adapter.id !== "string") {
    throw new Error("Adapter requires an identifier");
  }
  for (const method of FORBIDDEN_METHODS) {
    if (method in adapter) throw new Error(`Adapter cannot expose ${method}`);
  }
  for (const method of ["matches", "inspect", "map"]) {
    if (typeof adapter[method] !== "function") throw new Error(`Adapter requires ${method}`);
  }
  return Object.freeze({ id: adapter.id, matches: adapter.matches, inspect: adapter.inspect, map: adapter.map });
}

export function normalizeDescriptor(raw) {
  const control = typeof raw?.control === "string" ? raw.control : "";
  const label = typeof raw?.label === "string" ? raw.label.trim().slice(0, 240) : "";
  const blockedReason = !raw?.visible ? "not_visible"
    : !SAFE_CONTROLS.has(control) ? "unsupported_control"
      : BLOCKED_SEMANTICS.test(`${label} ${raw?.name || ""} ${raw?.autocomplete || ""}`) ? "protected_semantic"
        : null;
  return Object.freeze({
    fieldId: typeof raw?.fieldId === "string" ? raw.fieldId : "",
    control, label,
    name: typeof raw?.name === "string" ? raw.name.slice(0, 240) : "",
    autocomplete: typeof raw?.autocomplete === "string" ? raw.autocomplete.slice(0, 120) : "",
    required: raw?.required === true,
    visible: raw?.visible === true,
    blockedReason,
  });
}

export function buildFillPlan(descriptors, mappings) {
  const byId = new Map(descriptors.map(item => {
    const descriptor = normalizeDescriptor(item);
    return [descriptor.fieldId, descriptor];
  }));
  const plan = [];
  const planned = new Set();
  for (const mapping of mappings) {
    const descriptor = byId.get(mapping?.fieldId);
    if (!descriptor || !descriptor.fieldId || descriptor.blockedReason || planned.has(descriptor.fieldId)) continue;
    if (mapping.approved !== true || mapping.confidence !== "exact" || typeof mapping.profileField !== "string") continue;
    if (!["string", "number", "boolean"].includes(typeof mapping.value)) continue;
    plan.push(Object.freeze({
      fieldId: descriptor.fieldId,
      control: descriptor.control,
      profileField: mapping.profileField,
      value: mapping.value,
      sensitive: mapping.sensitive === true,
    }));
    planned.add(descriptor.fieldId);
  }
  return Object.freeze(plan);
}

export function normalizeAttachmentTarget(raw) {
  const label = typeof raw?.label === "string" ? raw.label.trim().slice(0, 240) : "";
  const documentType = DOCUMENT_TYPES.includes(raw?.documentType) ? raw.documentType : null;
  const blockedReason = !raw?.visible ? "not_visible"
    : raw?.control !== "file" ? "unsupported_control"
      : !documentType ? "unsupported_document_type"
        : BLOCKED_SEMANTICS.test(`${label} ${raw?.name || ""}`) ? "protected_semantic"
          : null;
  return Object.freeze({
    fieldId: typeof raw?.fieldId === "string" ? raw.fieldId : "",
    control: typeof raw?.control === "string" ? raw.control : "",
    label,
    documentType,
    visible: raw?.visible === true,
    requiresExplicitAction: true,
    blockedReason,
  });
}

export const ADAPTER_CONTRACT = Object.freeze({
  methods: Object.freeze(["matches", "inspect", "map"]),
  forbiddenMethods: Object.freeze([...FORBIDDEN_METHODS]),
  safeControls: Object.freeze([...SAFE_CONTROLS]),
  documentTypes: DOCUMENT_TYPES,
});
