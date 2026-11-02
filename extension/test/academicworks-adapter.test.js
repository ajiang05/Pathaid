import assert from "node:assert/strict";
import test from "node:test";
import { academicWorksAdapter, mapAcademicWorksFields } from "../lib/academicworks-adapter.js";

const profile = [
  { name: "first_name", label: "First name", value: "Aidan", sensitive: false },
  { name: "gpa", label: "GPA", value: 3.8, sensitive: false },
  { name: "credits_completed", label: "Credits completed", value: 72, sensitive: false },
  { name: "enrollment", label: "Enrollment status", value: "full_time", sensitive: false },
  { name: "pell_eligible", label: "Pell Grant eligible", value: true, sensitive: true },
  { name: "citizenship_status", label: "Citizenship status", value: "permanent_resident", sensitive: true },
];

test("AcademicWorks adapter matches only its resolved portal context", () => {
  assert.equal(academicWorksAdapter.matches({ adapter: "academicworks" }), true);
  assert.equal(academicWorksAdapter.matches({ adapter: "generic" }), false);
});

test("AcademicWorks exact questions map values and safe yes/no transforms", () => {
  const result = mapAcademicWorksFields([
    { fieldId: "first", control: "text", label: "First name", visible: true },
    { fieldId: "gpa", control: "number", label: "What is your current cumulative GPA? (Required)", visible: true },
    { fieldId: "credits", control: "number", label: "How many credit hours have you completed?", visible: true },
    { fieldId: "enrollment", control: "radio", label: "Are you currently enrolled full-time?", visible: true },
    { fieldId: "pell", control: "radio", label: "Are you eligible for a Federal Pell Grant?", visible: true },
    { fieldId: "citizenship", control: "select", label: "Are you a U.S. citizen or permanent resident?", visible: true },
  ], profile);
  assert.deepEqual(result.map(item => item.value), ["Aidan", 3.8, 72, true, true, true]);
  assert.deepEqual(result.map(item => item.profileField), [
    "first_name", "gpa", "credits_completed", "enrollment", "pell_eligible", "citizenship_status",
  ]);
  assert.equal(result[4].sensitive, true);
  assert.equal(result.every(item => item.status === "mapped" && item.approved === false), true);
});

test("AcademicWorks custom and protected questions remain untouched", () => {
  const result = mapAcademicWorksFields([
    { fieldId: "essay", control: "textarea", label: "Describe how this award will change your life", visible: true },
    { fieldId: "certify", control: "checkbox", label: "I certify that these answers are true", visible: true },
    { fieldId: "unknown", control: "number", label: "Current cumulative GPA", visible: true },
  ], profile.filter(field => field.name !== "gpa"));
  assert.equal(result[0].status, "skipped");
  assert.equal(result[1].status, "skipped");
  assert.equal(result[2].status, "skipped");
});
