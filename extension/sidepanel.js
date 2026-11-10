const elements = {
  form: document.querySelector("#token-form"), token: document.querySelector("#token"),
  retry: document.querySelector("#retry"), disconnect: document.querySelector("#disconnect"),
  inspect: document.querySelector("#inspect"), status: document.querySelector("#status"),
  connectionHeading: document.querySelector("#connection-heading"), connectionDetail: document.querySelector("#connection-detail"),
  connectionDot: document.querySelector("#connection-dot"), pageHeading: document.querySelector("#page-heading"),
  pageDetail: document.querySelector("#page-detail"), preview: document.querySelector("#preview"),
  previewList: document.querySelector("#preview-list"), fill: document.querySelector("#fill"),
  attachments: document.querySelector("#attachments"), attachmentList: document.querySelector("#attachment-list"),
};
let currentPreviewId = null;

async function request(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) throw new Error(response?.error || "Extension request failed");
  return response.result;
}

function renderConnection(state) {
  elements.connectionHeading.textContent = state.connected ? "Connected" : state.configured ? "Connection unavailable" : "Disconnected";
  elements.connectionDetail.textContent = state.connected ? "Connected to PathAid on this Mac." : state.configured ? "The saved token could not reach or authenticate PathAid." : "Paste the installation token copied from PathAid on this Mac.";
  elements.connectionDot.classList.toggle("connected", state.connected);
  elements.inspect.disabled = !state.connected;
  elements.form.hidden = state.configured;
  elements.retry.hidden = !state.configured;
  elements.disconnect.hidden = !state.configured;
}

async function perform(action) {
  elements.status.textContent = "";
  try { return await action(); }
  catch (error) { elements.status.textContent = error instanceof Error ? error.message : "The action failed."; return null; }
}

function renderPreview(preview) {
  currentPreviewId = preview?.id || null;
  elements.previewList.replaceChildren();
  elements.attachmentList.replaceChildren();
  elements.preview.hidden = !currentPreviewId;
  elements.attachments.hidden = true;
  if (!currentPreviewId) return;
  elements.fill.disabled = false;
  const profileFields = (preview.profileFields || []).filter(field => ["string", "number", "boolean"].includes(typeof field.value));
  const profileByName = new Map(profileFields.map(field => [field.name, field]));
  for (const field of preview.fields) {
    const row = document.createElement("article");
    row.className = `preview-field ${field.status}`;
    const heading = document.createElement("strong");
    heading.textContent = field.label || "Unlabeled field";
    row.append(heading);
    const detail = document.createElement("span");
    if (field.correctable) {
      const mappingLabel = document.createElement("label");
      mappingLabel.textContent = "Profile source";
      const select = document.createElement("select");
      select.name = "profile-mapping";
      select.dataset.fieldId = field.fieldId;
      select.dataset.original = field.profileField || "";
      const empty = document.createElement("option");
      empty.value = ""; empty.textContent = "Leave empty";
      select.append(empty);
      for (const profileField of profileFields) {
        const option = document.createElement("option");
        option.value = profileField.name;
        option.textContent = `${profileField.label}${profileField.sensitive ? " (sensitive)" : ""}`;
        select.append(option);
      }
      select.value = field.profileField || "";
      mappingLabel.append(select);
      row.append(mappingLabel);
      const choice = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox"; checkbox.name = "approved-field";
      checkbox.value = field.fieldId; checkbox.checked = field.status === "mapped";
      checkbox.disabled = !select.value;
      const valueText = document.createTextNode("");
      choice.append(checkbox, valueText);
      row.append(choice);
      const updateSelection = () => {
        const selected = profileByName.get(select.value);
        checkbox.disabled = !selected;
        if (!selected) checkbox.checked = false;
        valueText.textContent = selected ? ` Fill ${selected.label}: ${String(selected.value)}` : " No value will be filled";
        detail.textContent = selected
          ? selected.sensitive ? "Sensitive profile value" : field.learned && select.value === field.profileField ? "Learned profile mapping" : "Reviewed profile mapping"
          : "This field will remain empty";
        detail.className = selected?.sensitive ? "sensitive" : "";
      };
      select.addEventListener("change", updateSelection);
      updateSelection();
    } else if (field.status === "mapped") {
      const choice = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox"; checkbox.name = "approved-field"; checkbox.value = field.fieldId; checkbox.checked = true;
      choice.append(checkbox, document.createTextNode(` ${field.profileLabel}: ${String(field.value)}`));
      row.append(choice);
      detail.textContent = field.sensitive ? "Sensitive profile value" : "Exact profile mapping";
      if (field.sensitive) detail.className = "sensitive";
    } else {
      detail.textContent = field.status === "ambiguous" ? `Ambiguous — ${field.reason}` : `Skipped — ${field.reason}`;
    }
    row.append(detail);
    elements.previewList.append(row);
  }
  const attachments = preview.attachments || [];
  elements.attachments.hidden = attachments.length === 0;
  for (const attachment of attachments) {
    const row = document.createElement("article");
    row.className = "preview-field";
    const heading = document.createElement("strong");
    heading.textContent = attachment.label;
    const detail = document.createElement("span");
    detail.textContent = attachment.available
      ? attachment.documentType === "essay" ? "Choose one student-written essay to attach as a text file." : `${attachment.originalName} · decrypted only for this attachment`
      : `No ${attachment.documentType} is stored in PathAid Documents.`;
    let essaySelect = null;
    if (attachment.documentType === "essay" && attachment.available) {
      essaySelect = document.createElement("select");
      essaySelect.setAttribute("aria-label", `Essay for ${attachment.label}`);
      for (const essay of attachment.essayOptions || []) {
        const option = document.createElement("option");
        option.value = essay.id;
        option.textContent = `${essay.title} (${essay.word_count} words)`;
        essaySelect.append(option);
      }
    }
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = !attachment.available;
    button.textContent = `Attach ${attachment.documentType}`;
    button.addEventListener("click", () => void perform(async () => {
      if (!currentPreviewId) throw new Error("Inspect the page before attaching a document.");
      const result = await request({
        type: "ATTACH_DOCUMENT", previewId: currentPreviewId,
        fieldId: attachment.fieldId, documentType: attachment.documentType,
        ...(essaySelect ? { essayId: essaySelect.value } : {}),
      });
      elements.status.textContent = `${result.filename} attached. Review the file and complete the application yourself.`;
      button.disabled = true;
    }));
    row.append(heading, detail);
    if (essaySelect) row.append(essaySelect);
    row.append(button);
    elements.attachmentList.append(row);
  }
}

elements.form.addEventListener("submit", event => {
  event.preventDefault();
  void perform(async () => { const state = await request({ type: "CONFIGURE", token: elements.token.value.trim() }); elements.token.value = ""; renderConnection(state); });
});
elements.retry.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "PING" }))));
elements.disconnect.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "CLEAR_TOKEN" }))));
elements.inspect.addEventListener("click", () => void perform(async () => {
  const page = await request({ type: "INSPECT_ACTIVE_PAGE" });
  elements.pageHeading.textContent = page.state === "supported" ? page.scholarship_name
    : page.state === "policy_blocked" ? "Automation disabled by official rules"
      : page.state === "ambiguous" ? "Scholarship context needed" : "Unsupported page";
  elements.pageDetail.textContent = page.state === "supported" ? `${page.portal_origin} · ${page.adapter} adapter · ${page.formCount} form container(s) detected` : page.reason;
  renderPreview(page.state === "supported" ? page.preview : null);
}));
elements.fill.addEventListener("click", () => void perform(async () => {
  if (!currentPreviewId) throw new Error("Inspect the page before filling.");
  const approvedFieldIds = [...document.querySelectorAll('input[name="approved-field"]:checked')].map(item => item.value);
  const corrections = [...document.querySelectorAll('select[name="profile-mapping"]')]
    .filter(item => item.value !== item.dataset.original)
    .map(item => ({ fieldId: item.dataset.fieldId, profileField: item.value || null }));
  const result = await request({ type: "FILL_PREVIEW", previewId: currentPreviewId, approvedFieldIds, corrections });
  elements.status.textContent = `${result.filled} of ${result.requested} approved fields filled. Review the complete form before submitting it yourself.`;
  elements.fill.disabled = true;
}));

void perform(async () => {
  const state = await request({ type: "GET_STATE" });
  renderConnection(state);
  // Stored state explains worker restarts, but only a fresh ping may present
  // the local API as currently connected.
  if (state.configured) renderConnection(await request({ type: "PING" }));
});
