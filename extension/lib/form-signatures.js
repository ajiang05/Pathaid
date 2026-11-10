function normalized(value) {
  return String(value || "").normalize("NFKD")
    .replace(/[^a-zA-Z0-9]+/g, " ").trim().toLowerCase();
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function formSignatures(descriptors) {
  // Sign metadata only. Existing form answers and profile values never enter a
  // signature or the learned-mapping table.
  const shape = descriptors.slice(0, 200).map((item, index) => JSON.stringify([
    index, item.control || "", normalized(item.label), normalized(item.name),
    normalized(item.autocomplete), item.required === true,
  ]));
  return {
    formSignature: await sha256(JSON.stringify(shape)),
    fieldSignatures: await Promise.all(shape.map(item => sha256(item))),
  };
}
