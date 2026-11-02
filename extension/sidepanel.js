const elements = {
  form: document.querySelector("#token-form"), token: document.querySelector("#token"),
  retry: document.querySelector("#retry"), disconnect: document.querySelector("#disconnect"),
  inspect: document.querySelector("#inspect"), status: document.querySelector("#status"),
  connectionHeading: document.querySelector("#connection-heading"), connectionDetail: document.querySelector("#connection-detail"),
  connectionDot: document.querySelector("#connection-dot"), pageHeading: document.querySelector("#page-heading"),
  pageDetail: document.querySelector("#page-detail"), preview: document.querySelector("#preview"),
  previewList: document.querySelector("#preview-list"), fill: document.querySelector("#fill"),
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
  elements.preview.hidden = !currentPreviewId;
  if (!currentPreviewId) return;
  elements.fill.disabled = false;
  for (const field of preview.fields) {
    const row = document.createElement("article");
    row.className = `preview-field ${field.status}`;
    const heading = document.createElement("strong");
    heading.textContent = field.label || "Unlabeled field";
    row.append(heading);
    const detail = document.createElement("span");
    if (field.status === "mapped") {
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
}

elements.form.addEventListener("submit", event => {
  event.preventDefault();
  void perform(async () => { const state = await request({ type: "CONFIGURE", token: elements.token.value.trim() }); elements.token.value = ""; renderConnection(state); });
});
elements.retry.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "PING" }))));
elements.disconnect.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "CLEAR_TOKEN" }))));
elements.inspect.addEventListener("click", () => void perform(async () => {
  const page = await request({ type: "INSPECT_ACTIVE_PAGE" });
  elements.pageHeading.textContent = page.state === "supported" ? page.scholarship_name : page.state === "ambiguous" ? "Scholarship context needed" : "Unsupported page";
  elements.pageDetail.textContent = page.state === "supported" ? `${page.portal_origin} · ${page.adapter} adapter · ${page.formCount} form container(s) detected` : page.reason;
  renderPreview(page.state === "supported" ? page.preview : null);
}));
elements.fill.addEventListener("click", () => void perform(async () => {
  if (!currentPreviewId) throw new Error("Inspect the page before filling.");
  const approvedFieldIds = [...document.querySelectorAll('input[name="approved-field"]:checked')].map(item => item.value);
  const result = await request({ type: "FILL_PREVIEW", previewId: currentPreviewId, approvedFieldIds });
  elements.status.textContent = `${result.filled} of ${result.requested} approved fields filled. Review the complete form before submitting it yourself.`;
  currentPreviewId = null;
  elements.fill.disabled = true;
}));

void perform(async () => {
  const state = await request({ type: "GET_STATE" });
  renderConnection(state);
  // Stored state explains worker restarts, but only a fresh ping may present
  // the local API as currently connected.
  if (state.configured) renderConnection(await request({ type: "PING" }));
});
