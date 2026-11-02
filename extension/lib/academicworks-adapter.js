import { defineAdapter, normalizeDescriptor } from "./adapter-contract.js";
import { mapGenericFields } from "./generic-adapter.js";

// Award Management questions are configured by each institution. Keep this
// list intentionally narrow: only exact, common question wording is safe to
// associate with a saved profile field without asking the student to correct it.
const QUESTION_FIELDS = Object.freeze({
  "current cumulative gpa": "gpa",
  "what is your current cumulative gpa": "gpa",
  "cumulative grade point average": "gpa",
  "number of credits completed": "credits_completed",
  "how many credit hours have you completed": "credits_completed",
  "expected graduation date": "expected_graduation",
  "what is your expected graduation date": "expected_graduation",
  "current academic major": "major",
  "what is your current academic major": "major",
  "current academic minor": "minor",
  "what is your current academic minor": "minor",
});

const BOOLEAN_QUESTIONS = Object.freeze({
  "are you eligible for a federal pell grant": {
    profileField: "pell_eligible", transform: value => value,
  },
  "are you a first generation college student": {
    profileField: "first_generation_student", transform: value => value,
  },
  "are you a veteran or active duty service member": {
    profileField: "veteran_status", transform: value => value,
  },
  "do you have a disability": {
    profileField: "disability_status", transform: value => value,
  },
  "are you currently enrolled full time": {
    profileField: "enrollment", transform: value => value === "full_time",
  },
  "are you a u s citizen or permanent resident": {
    profileField: "citizenship_status",
    transform: value => ["us_citizen", "permanent_resident"].includes(value),
  },
});

function normalized(value) {
  return String(value || "").normalize("NFKD")
    .replace(/\b(required|optional)\b/gi, " ")
    .replace(/[^a-zA-Z0-9]+/g, " ").trim().toLowerCase();
}

function mapped(descriptor, profileField, value) {
  return {
    fieldId: descriptor.fieldId, label: descriptor.label, status: "mapped",
    profileField: profileField.name, profileLabel: profileField.label, value,
    sensitive: profileField.sensitive === true, confidence: "exact", approved: false,
  };
}

export function mapAcademicWorksFields(descriptors, profileFields) {
  const profile = new Map(profileFields.map(field => [field.name, field]));
  const generic = mapGenericFields(descriptors, profileFields);
  return descriptors.slice(0, 200).map((raw, index) => {
    const descriptor = normalizeDescriptor(raw);
    // Protected, hidden, and unsupported controls must retain the central
    // contract's decision rather than being rescued by a portal-specific rule.
    if (!descriptor.fieldId || descriptor.blockedReason) return generic[index];
    const question = normalized(descriptor.label);
    const directName = QUESTION_FIELDS[question];
    const directField = directName ? profile.get(directName) : null;
    if (directField && ["string", "number", "boolean"].includes(typeof directField.value)) {
      return mapped(descriptor, directField, directField.value);
    }
    const booleanRule = BOOLEAN_QUESTIONS[question];
    const booleanField = booleanRule ? profile.get(booleanRule.profileField) : null;
    if (booleanField && ["string", "boolean"].includes(typeof booleanField.value)) {
      return mapped(descriptor, booleanField, booleanRule.transform(booleanField.value));
    }
    return generic[index];
  });
}

export const academicWorksAdapter = defineAdapter({
  id: "academicworks",
  matches: context => context?.adapter === "academicworks",
  inspect: descriptors => descriptors.map(normalizeDescriptor),
  map: mapAcademicWorksFields,
});
