import assert from "node:assert/strict";
import test from "node:test";
import { mapDocumentTargets } from "../lib/document-targets.js";

test("only exact managed-document labels become attachment targets", () => {
  const targets = mapDocumentTargets([
    { fieldId: "resume", control: "file", label: "Upload résumé (Required)", visible: true },
    { fieldId: "transcript", control: "file", label: "Academic transcript", visible: true },
    { fieldId: "essay", control: "file", label: "Upload essay", visible: true },
    { fieldId: "support", control: "file", label: "Supporting document", visible: true },
    { fieldId: "tax", control: "file", label: "Tax document", visible: true },
  ]);
  assert.equal(targets[0].documentType, "resume");
  assert.equal(targets[1].documentType, "transcript");
  assert.equal(targets[2].documentType, "essay");
  assert.equal(targets[3].blockedReason, "unsupported_document_type");
  assert.equal(targets[4].blockedReason, "unsupported_document_type");
  assert.equal(targets.every(item => item.requiresExplicitAction), true);
});
