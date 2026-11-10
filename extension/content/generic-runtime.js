(() => {
  if (globalThis.__pathAidGenericRuntime) return;
  globalThis.__pathAidGenericRuntime = true;
  const ATTRIBUTE = "data-pathaid-field-id";
  const BLOCKED = /\b(signature|sign here|certif(?:y|ication)|attest|terms(?: of service)?|i agree|consent|authoriz(?:e|ation)|acknowledge|captcha|mfa|multi[- ]factor|verification code|one[- ]time code|password)\b/i;
  const SAFE = new Set(["text", "email", "tel", "url", "number", "date", "month", "select", "textarea", "radio", "checkbox"]);
  const registry = new Map();

  function control(element) {
    if (element.tagName === "SELECT") return "select";
    if (element.tagName === "TEXTAREA") return "textarea";
    return (element.type || "text").toLowerCase();
  }
  function visible(element) {
    if (element.type === "hidden" || element.disabled || element.readOnly) return false;
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }
  function label(element) {
    const labels = [...(element.labels || [])].map(item => item.textContent || "").join(" ").trim();
    const legend = element.closest("fieldset")?.querySelector(":scope > legend")?.textContent?.trim() || "";
    const groupLabel = ["radio", "checkbox"].includes(control(element)) ? legend : "";
    return (groupLabel || labels || legend || element.getAttribute("aria-label") || element.placeholder || element.name || element.id || "Unlabeled field").slice(0, 240);
  }
  function protectedField(element) {
    return BLOCKED.test(`${label(element)} ${element.name || ""} ${element.autocomplete || ""}`);
  }
  function fieldId(element, index) {
    const grouped = ["radio", "checkbox"].includes(control(element)) && element.name;
    if (grouped) {
      const existing = [...document.querySelectorAll("input")].find(item => item.name === element.name && item.hasAttribute(ATTRIBUTE));
      if (existing) {
        const id = existing.getAttribute(ATTRIBUTE);
        element.setAttribute(ATTRIBUTE, id);
        return id;
      }
    }
    const id = `pathaid-${Date.now().toString(36)}-${index}`;
    element.setAttribute(ATTRIBUTE, id);
    return id;
  }
  function inspect() {
    const descriptors = [];
    const seen = new Set();
    const fields = [...document.querySelectorAll("input,select,textarea")].slice(0, 500);
    fields.forEach((element, index) => {
      const id = fieldId(element, index);
      const registered = registry.get(id) || [];
      if (!registered.includes(element)) registered.push(element);
      registry.set(id, registered);
      if (seen.has(id)) return;
      seen.add(id);
      const type = control(element);
      const isVisible = visible(element);
      descriptors.push({
        fieldId: id, control: type, label: label(element), name: element.name || "",
        autocomplete: element.autocomplete || "", required: element.required === true,
        visible: isVisible && !protectedField(element),
      });
    });
    return descriptors.slice(0, 200);
  }
  function attachmentTargets() {
    return [...registry.entries()].slice(0, 50).flatMap(([id, elements]) => {
      const element = elements.find(item => control(item) === "file");
      if (!element) return [];
      return [{
        fieldId: id, control: "file", label: label(element), name: element.name || "",
        visible: visible(element) && !protectedField(element), accept: element.accept || "",
      }];
    });
  }
  function normalized(value) {
    return String(value).normalize("NFKD").replace(/[^a-zA-Z0-9]+/g, "").toLowerCase();
  }
  function valueMatches(candidate, value) {
    const expected = normalized(value);
    const allowed = value === true ? new Set(["true", "yes", "1"])
      : value === false ? new Set(["false", "no", "0"]) : new Set([expected]);
    return allowed.has(normalized(candidate));
  }
  function setValue(element, value) {
    const type = control(element);
    if (!visible(element) || protectedField(element) || !SAFE.has(type)) return false;
    if (type === "checkbox") {
      if (typeof value !== "boolean") return false;
      element.checked = value;
    } else if (type === "radio") {
      return false;
    } else if (type === "select") {
      const matches = [...element.options].filter(option => valueMatches(option.value, value) || valueMatches(option.textContent, value));
      if (matches.length !== 1) return false;
      element.value = matches[0].value;
    } else {
      const prototype = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (!setter) return false;
      setter.call(element, String(value));
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  function fill(plan) {
    let count = 0;
    for (const item of Array.isArray(plan) ? plan.slice(0, 200) : []) {
      // Resolve the exact elements captured during inspection rather than
      // trusting page-controlled selectors or copied data attributes.
      const fields = (registry.get(item.fieldId) || []).filter(element => element.isConnected);
      if (item.control === "radio") {
        const matches = fields.filter(element => control(element) === "radio" && (valueMatches(element.value, item.value) || valueMatches(label(element), item.value)));
        if (matches.length === 1 && visible(matches[0]) && !protectedField(matches[0])) {
          matches[0].checked = true;
          matches[0].dispatchEvent(new Event("input", { bubbles: true }));
          matches[0].dispatchEvent(new Event("change", { bubbles: true }));
          count += 1;
        }
      } else if (fields.length === 1 && setValue(fields[0], item.value)) count += 1;
    }
    return { filled: count, requested: Array.isArray(plan) ? Math.min(plan.length, 200) : 0 };
  }
  function attach(message) {
    const fields = (registry.get(message.fieldId) || []).filter(element => element.isConnected);
    if (fields.length !== 1 || control(fields[0]) !== "file" || !visible(fields[0]) || protectedField(fields[0])) return false;
    const element = fields[0];
    const accept = (element.accept || "").toLowerCase();
    // Infer legacy PDF messages by filename; current worker messages always
    // carry the response media type explicitly.
    const contentType = typeof message.contentType === "string"
      ? message.contentType.toLowerCase()
      : String(message.filename || "").toLowerCase().endsWith(".pdf") ? "application/pdf" : "";
    const isPdf = contentType === "application/pdf";
    const isText = contentType === "text/plain";
    if (!isPdf && !isText) return false;
    if (accept && isPdf && !accept.includes("application/pdf") && !accept.includes(".pdf")) return false;
    if (accept && isText && !accept.includes("text/plain") && !accept.includes(".txt")) return false;
    if (typeof message.base64 !== "string" || typeof message.filename !== "string") return false;
    const binary = atob(message.base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const transfer = new DataTransfer();
    transfer.items.add(new File([bytes], message.filename, { type: contentType }));
    element.files = transfer.files;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return element.files?.length === 1;
  }
  chrome.runtime.onMessage.addListener((message, _sender, respond) => {
    if (message?.type === "PATHAID_INSPECT_GENERIC") {
      const descriptors = inspect();
      respond({ ok: true, descriptors, attachmentTargets: attachmentTargets() });
    }
    else if (message?.type === "PATHAID_FILL_GENERIC") respond({ ok: true, result: fill(message.plan) });
    else if (message?.type === "PATHAID_ATTACH_DOCUMENT") respond({ ok: true, attached: attach(message) });
  });
})();
