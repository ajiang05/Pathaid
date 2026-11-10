import { normalizeAttachmentTarget } from "./adapter-contract.js";

const LABEL_TYPES = Object.freeze({
  resume: "resume",
  "upload resume": "resume",
  "attach resume": "resume",
  "resume pdf": "resume",
  transcript: "transcript",
  "academic transcript": "transcript",
  "upload transcript": "transcript",
  "upload academic transcript": "transcript",
  "attach transcript": "transcript",
  essay: "essay",
  "essay file": "essay",
  "upload essay": "essay",
  "attach essay": "essay",
});

function normalized(value) {
  return String(value || "").normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/\b(required|optional)\b/gi, " ")
    .replace(/[^a-zA-Z0-9]+/g, " ").trim().toLowerCase();
}

export function mapDocumentTargets(rawTargets) {
  return rawTargets.slice(0, 50).map(raw => normalizeAttachmentTarget({
    ...raw,
    documentType: LABEL_TYPES[normalized(raw.label)] || null,
  }));
}
