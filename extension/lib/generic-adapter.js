import { defineAdapter, normalizeDescriptor } from "./adapter-contract.js";

const AUTOCOMPLETE_FIELDS = Object.freeze({
  "given-name": "first_name", "family-name": "last_name", email: "email",
  tel: "phone", bday: "date_of_birth",
});
const LABEL_ALIASES = Object.freeze({
  first_name: ["first name", "given name"],
  last_name: ["last name", "family name", "surname"],
  email: ["email", "email address"],
  phone: ["phone", "phone number", "telephone", "mobile phone"],
  date_of_birth: ["date of birth", "birth date", "dob"],
  school: ["school", "college", "university", "current college or university"],
  school_city: ["school city", "college city"],
  school_state: ["school state", "college state"],
  current_city: ["current city", "current residence city"],
  current_state: ["current state", "current residence state"],
  current_postal_code: ["current zip code", "current postal code", "current residence zip code"],
  permanent_city: ["permanent city", "home city", "permanent residence city"],
  permanent_state: ["permanent state", "home state", "permanent residence state"],
  permanent_postal_code: ["permanent zip code", "home zip code", "permanent postal code"],
  study_level: ["study level", "student level"],
  enrollment: ["enrollment", "enrollment status"],
  class_year: ["class year", "year in school"],
  degree_type: ["degree", "degree type"],
  major: ["major", "field of study", "academic major"],
  minor: ["minor", "academic minor"],
  gpa: ["gpa", "grade point average"],
  gpa_scale: ["gpa scale", "grade point scale"],
  credits_completed: ["credits completed", "completed credits"],
  expected_graduation: ["expected graduation", "graduation date", "graduation month"],
  income_range: ["household income range", "income range"],
  pell_eligible: ["pell grant eligible", "pell eligible"],
  student_aid_index: ["student aid index", "sai"],
  ethnicity: ["ethnicity"], race: ["race"], gender: ["gender"],
  disability_status: ["disability status", "person with a disability"],
  first_generation_student: ["first generation college student", "first generation student"],
  citizenship_status: ["citizenship status", "citizenship or residency status"],
  veteran_status: ["veteran status", "active duty or veteran"],
});
const AMBIGUOUS_LABEL = /^(address|street|city|state|zip|zip code|postal code|country|name)$/;

function normalized(value) {
  return String(value || "").normalize("NFKD").replace(/[^a-zA-Z0-9]+/g, " ").trim().toLowerCase();
}

function aliasesFor(label) {
  const key = normalized(label);
  return Object.entries(LABEL_ALIASES)
    .filter(([, aliases]) => aliases.includes(key))
    .map(([field]) => field);
}

export function mapGenericFields(descriptors, profileFields) {
  const profile = new Map(profileFields.map(field => [field.name, field]));
  return descriptors.slice(0, 200).map(raw => {
    const descriptor = normalizeDescriptor(raw);
    if (!descriptor.fieldId || descriptor.blockedReason) {
      return { fieldId: descriptor.fieldId, label: descriptor.label, status: "skipped", reason: descriptor.blockedReason || "invalid_field" };
    }
    const autocomplete = descriptor.autocomplete.split(/\s+/).find(token => token in AUTOCOMPLETE_FIELDS);
    const candidates = autocomplete ? [AUTOCOMPLETE_FIELDS[autocomplete]] : aliasesFor(descriptor.label || descriptor.name);
    const available = [...new Set(candidates)].filter(name => profile.has(name));
    if (available.length === 1) {
      const field = profile.get(available[0]);
      if (!["string", "number", "boolean"].includes(typeof field.value)) {
        return {
          fieldId: descriptor.fieldId, label: descriptor.label, status: "skipped",
          reason: "This field requires a dedicated multi-value adapter.",
        };
      }
      return {
        fieldId: descriptor.fieldId, label: descriptor.label, status: "mapped",
        profileField: field.name, profileLabel: field.label, value: field.value,
        sensitive: field.sensitive === true, confidence: "exact", approved: false,
      };
    }
    const ambiguous = available.length > 1 || AMBIGUOUS_LABEL.test(normalized(descriptor.label || descriptor.name));
    return {
      fieldId: descriptor.fieldId, label: descriptor.label,
      status: ambiguous ? "ambiguous" : "skipped",
      reason: ambiguous ? "More than one profile field could apply." : "No exact saved profile mapping.",
    };
  });
}

export const genericAdapter = defineAdapter({
  id: "generic",
  matches: context => context?.adapter === "generic",
  inspect: descriptors => descriptors.map(normalizeDescriptor),
  map: mapGenericFields,
});
