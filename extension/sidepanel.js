const elements = {
  form: document.querySelector("#token-form"), token: document.querySelector("#token"),
  retry: document.querySelector("#retry"), disconnect: document.querySelector("#disconnect"),
  inspect: document.querySelector("#inspect"), status: document.querySelector("#status"),
  connectionHeading: document.querySelector("#connection-heading"), connectionDetail: document.querySelector("#connection-detail"),
  connectionDot: document.querySelector("#connection-dot"), pageHeading: document.querySelector("#page-heading"),
  pageDetail: document.querySelector("#page-detail"),
};

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

elements.form.addEventListener("submit", event => {
  event.preventDefault();
  void perform(async () => { const state = await request({ type: "CONFIGURE", token: elements.token.value.trim() }); elements.token.value = ""; renderConnection(state); });
});
elements.retry.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "PING" }))));
elements.disconnect.addEventListener("click", () => void perform(async () => renderConnection(await request({ type: "CLEAR_TOKEN" }))));
elements.inspect.addEventListener("click", () => void perform(async () => {
  const page = await request({ type: "INSPECT_ACTIVE_PAGE" });
  elements.pageHeading.textContent = page.state === "supported" ? "Supported public page" : "Unsupported page";
  elements.pageDetail.textContent = page.state === "supported" ? `${page.origin} · ${page.formCount} form container(s) detected` : page.reason;
}));

void perform(async () => {
  const state = await request({ type: "GET_STATE" });
  renderConnection(state);
  // Stored state explains worker restarts, but only a fresh ping may present
  // the local API as currently connected.
  if (state.configured) renderConnection(await request({ type: "PING" }));
});
