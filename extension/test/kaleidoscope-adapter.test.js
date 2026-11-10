import assert from "node:assert/strict";
import test from "node:test";
import { kaleidoscopeAdapter, mapKaleidoscopeFields } from "../lib/kaleidoscope-adapter.js";

const profile = [
  { name: "first_name", label: "First name", value: "Aidan", sensitive: false },
  { name: "last_name", label: "Last name", value: "Jiang", sensitive: false },
  { name: "gpa", label: "GPA", value: 3.8, sensitive: false },
  { name: "major", label: "Major", value: "Computer Science", sensitive: false },
  { name: "enrollment", label: "Enrollment", value: "part_time", sensitive: false },
  { name: "pell_eligible", label: "Pell eligible", value: false, sensitive: true },
];

test("Kaleidoscope adapter matches only its resolved portal context", () => {
  assert.equal(kaleidoscopeAdapter.matches({ adapter: "kaleidoscope" }), true);
  assert.equal(kaleidoscopeAdapter.matches({ adapter: "generic" }), false);
});

test("Kaleidoscope maps exact learner questions and preserves false answers", () => {
  const result = mapKaleidoscopeFields([
    { fieldId: "first", control: "text", label: "Legal first name (Required)", visible: true },
    { fieldId: "last", control: "text", label: "Legal last name", visible: true },
    { fieldId: "gpa", control: "number", label: "Current grade point average (GPA)", visible: true },
    { fieldId: "major", control: "text", label: "What is your intended major?", visible: true },
    { fieldId: "enrollment", control: "radio", label: "Are you currently enrolled full-time?", visible: true },
    { fieldId: "pell", control: "select", label: "Are you eligible for a Pell Grant?", visible: true },
  ], profile);
  assert.deepEqual(result.map(item => item.value), ["Aidan", "Jiang", 3.8, "Computer Science", false, false]);
  assert.deepEqual(result.map(item => item.profileField), [
    "first_name", "last_name", "gpa", "major", "enrollment", "pell_eligible",
  ]);
  assert.equal(result[5].sensitive, true);
  assert.equal(result.every(item => item.status === "mapped" && item.approved === false), true);
});

test("Kaleidoscope leaves sponsor-specific and protected questions untouched", () => {
  const result = mapKaleidoscopeFields([
    { fieldId: "essay", control: "textarea", label: "Tell us how you embody our company values", visible: true },
    { fieldId: "college", control: "text", label: "First choice college next year", visible: true },
    { fieldId: "terms", control: "checkbox", label: "I agree to the official rules", visible: true },
  ], profile);
  assert.equal(result.every(item => item.status === "skipped"), true);
});
