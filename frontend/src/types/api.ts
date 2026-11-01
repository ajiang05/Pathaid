export type UnknownValue = { status: "unknown" };
export type ProfileValue = string | number | boolean | string[] | UnknownValue;
export type ProfileFields = Record<string, ProfileValue | undefined>;

export type FieldSpec = {
  section: string;
  type: "string" | "email" | "choice" | "multi_choice" | "boolean" | "integer" | "number" | "date" | "month";
  label: string;
  question: string;
  values?: string[];
  sensitive: boolean;
  optional: boolean;
  allow_unknown: boolean;
  maximum?: number;
};

export type FieldSection = { id: string; label: string };
export type FieldRegistry = { fields: Record<string, FieldSpec>; sections: FieldSection[]; unknown_answer: UnknownValue };
export type Experience = {
  id?: string;
  kind: "activity" | "employment" | "volunteering" | "membership" | "leadership" | "honor";
  organization: string;
  title: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  current: boolean;
  hours?: number | null;
  leadership: boolean;
  tags: string[];
};
export type Completeness = { known: number; unknown: number; unanswered: number; total: number; percent_known: number };
export type Profile = {
  fields: ProfileFields;
  experiences: Experience[];
  completeness: Completeness;
  school_revision: number;
  school_changed: boolean;
};

export type MatchResult = {
  scholarship_id: string;
  name: string;
  sponsor: string;
  award: string | null;
  deadline: string | null;
  match_label: "Strong match" | "Possible match";
  key_reasons: string[];
  unknown_fields: string[];
};
export type MatchesResponse = {
  results: MatchResult[];
  not_matches: MatchResult[];
  profile_completeness: Completeness;
  catalog_status: "ready" | "awaiting_approved_sources";
};
