import assert from "node:assert/strict";
import test from "node:test";
import { ADAPTER_CONTRACT, buildFillPlan, defineAdapter, normalizeAttachmentTarget, normalizeDescriptor } from "../lib/adapter-contract.js";

test("adapter contract exposes description and mapping but no action API", () => {
  const adapter = defineAdapter({
    id: "fixture", matches: () => true, inspect: () => [], map: () => [],
  });
  assert.deepEqual(Object.keys(adapter).sort(), ["id", "inspect", "map", "matches"]);
  assert.equal(ADAPTER_CONTRACT.forbiddenMethods.includes("submit"), true);
  assert.equal(ADAPTER_CONTRACT.forbiddenMethods.includes("fill"), true);
  assert.throws(() => defineAdapter({
    id: "unsafe", matches() {}, inspect() {}, map() {}, submit() {},
  }), /cannot expose submit/);
});

test("protected, hidden, and action controls cannot enter a fill plan", () => {
  const descriptors = [
    { fieldId: "name", control: "text", label: "Legal name", visible: true },
    { fieldId: "certify", control: "checkbox", label: "I certify this is true", visible: true },
    { fieldId: "submit", control: "submit", label: "Submit application", visible: true },
    { fieldId: "trap", control: "text", label: "Leave blank", visible: false },
    { fieldId: "password", control: "password", label: "Portal password", visible: true },
  ];
  const mappings = descriptors.map(item => ({
    fieldId: item.fieldId, profileField: "full_name", value: "Student", confidence: "exact", approved: true,
  }));
  assert.deepEqual(buildFillPlan(descriptors, mappings), [{
    fieldId: "name", control: "text", profileField: "full_name", value: "Student", sensitive: false,
  }]);
  assert.equal(normalizeDescriptor(descriptors[1]).blockedReason, "protected_semantic");
});

test("ambiguous, unknown, and non-scalar mappings stay out of fill plans", () => {
  const descriptors = [{ fieldId: "school", control: "text", label: "School", visible: true }];
  assert.deepEqual(buildFillPlan(descriptors, [
    { fieldId: "school", profileField: "school", value: "UMass", confidence: "ambiguous", approved: true },
    { fieldId: "school", profileField: "school", value: null, confidence: "exact", approved: true },
    { fieldId: "school", profileField: "school", value: ["UMass"], confidence: "exact", approved: true },
    { fieldId: "school", profileField: "school", value: "UMass", confidence: "exact", approved: false },
  ]), []);
});

test("attachments use a separate explicit-action contract", () => {
  assert.deepEqual(normalizeAttachmentTarget({
    fieldId: "resume", control: "file", label: "Upload résumé",
    documentType: "resume", visible: true,
  }), {
    fieldId: "resume", control: "file", label: "Upload résumé",
    documentType: "resume", visible: true, requiresExplicitAction: true, blockedReason: null,
  });
  assert.equal(normalizeAttachmentTarget({
    fieldId: "tax", control: "file", label: "Upload tax return",
    documentType: "tax", visible: true,
  }).blockedReason, "unsupported_document_type");
});
