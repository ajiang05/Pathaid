import assert from "node:assert/strict";
import test from "node:test";
import { mapGenericFields } from "../lib/generic-adapter.js";

const profile = [
  { name: "first_name", label: "First name", value: "Aidan", sensitive: false },
  { name: "email", label: "Email address", value: "aidan@example.com", sensitive: true },
  { name: "gpa", label: "GPA", value: 3.8, sensitive: false },
  { name: "current_state", label: "Current residence state", value: "MA", sensitive: false },
  { name: "permanent_state", label: "Permanent state", value: "NY", sensitive: false },
  { name: "race", label: "Race", value: ["asian", "white"], sensitive: true },
];

test("generic adapter maps only exact semantic labels or autocomplete tokens", () => {
  const result = mapGenericFields([
    { fieldId: "first", control: "text", label: "Unhelpful", autocomplete: "given-name", visible: true },
    { fieldId: "email", control: "email", label: "Email address", visible: true },
    { fieldId: "gpa", control: "number", label: "GPA", visible: true },
  ], profile);
  assert.deepEqual(result.map(item => item.profileField), ["first_name", "email", "gpa"]);
  assert.equal(result[1].sensitive, true);
  assert.equal(result.every(item => item.confidence === "exact" && item.approved === false), true);
});

test("ambiguous locations and protected controls remain unfilled", () => {
  const result = mapGenericFields([
    { fieldId: "state", control: "select", label: "State", visible: true },
    { fieldId: "certify", control: "checkbox", label: "I certify this is true", visible: true },
    { fieldId: "mystery", control: "text", label: "Favorite quotation", visible: true },
    { fieldId: "race", control: "checkbox", label: "Race", visible: true },
  ], profile);
  assert.equal(result[0].status, "ambiguous");
  assert.equal(result[1].status, "skipped");
  assert.equal(result[2].status, "skipped");
  assert.equal(result[3].status, "skipped");
  assert.match(result[3].reason, /multi-value/);
});
