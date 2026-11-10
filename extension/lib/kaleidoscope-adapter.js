import { defineAdapter, normalizeDescriptor } from "./adapter-contract.js";
import { mapGenericFields } from "./generic-adapter.js";

// Kaleidoscope sponsors can customize their applications. These aliases cover
// only common reusable learner-profile questions whose meaning is exact.
const QUESTION_FIELDS = Object.freeze({
  "legal first name": "first_name",
  "legal last name": "last_name",
  "current gpa": "gpa",
  "current grade point average gpa": "gpa",
  "what is your current gpa": "gpa",
  "anticipated graduation date": "expected_graduation",
  "anticipated graduation month": "expected_graduation",
  "what is your intended major": "major",
  "intended college major": "major",
  "current college or university": "school",
});

const BOOLEAN_QUESTIONS = Object.freeze({
  "are you eligible for a pell grant": {
    profileField: "pell_eligible", transform: value => value,
  },
  "are you a first generation college student": {
    profileField: "first_generation_student", transform: value => value,
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

export function mapKaleidoscopeFields(descriptors, profileFields) {
  const profile = new Map(profileFields.map(field => [field.name, field]));
  const generic = mapGenericFields(descriptors, profileFields);
  return descriptors.slice(0, 200).map((raw, index) => {
    const descriptor = normalizeDescriptor(raw);
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

export const kaleidoscopeAdapter = defineAdapter({
  id: "kaleidoscope",
  matches: context => context?.adapter === "kaleidoscope",
  inspect: descriptors => descriptors.map(normalizeDescriptor),
  map: mapKaleidoscopeFields,
});
