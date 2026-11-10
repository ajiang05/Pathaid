type ExtensionResponse = { ok?: boolean } | undefined;
type ChromeRuntime = {
  lastError?: { message?: string };
  sendMessage: (
    extensionId: string,
    message: { type: "OPEN_APPLICATION"; scholarshipId: string },
    callback: (response: ExtensionResponse) => void,
  ) => void;
};

export async function openWithApplicationCopilot(extensionId: string | null, scholarshipId: string): Promise<boolean> {
  const runtime = (globalThis as typeof globalThis & { chrome?: { runtime?: ChromeRuntime } }).chrome?.runtime;
  if (!extensionId || !runtime?.sendMessage) return false;
  return new Promise(resolve => {
    runtime.sendMessage(extensionId, { type: "OPEN_APPLICATION", scholarshipId }, response => {
      resolve(!runtime.lastError && response?.ok === true);
    });
  });
}
