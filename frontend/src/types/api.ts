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
  application_url: string;
  saved_status: SavedStatus | null;
  application_process: "separate_application" | "automatically_considered" | "sweepstakes";
  official_rules_url: string | null;
};
export type MatchesResponse = {
  results: MatchResult[];
  automatically_considered: MatchResult[];
  sweepstakes: MatchResult[];
  not_matches: MatchResult[];
  profile_completeness: Completeness;
  catalog_status: "ready" | "awaiting_approved_sources";
};

export type SavedStatus = "not_started" | "in_progress" | "already_applied";
export type SavedScholarship = {
  scholarship_id: string;
  status: SavedStatus;
  name: string;
  sponsor: string;
  award: string | null;
  deadline: string | null;
  application_url: string;
  availability: string;
  source_status: "active" | "inactive";
  source_freshness: string;
  created_at: string;
  updated_at: string;
};
export type SavedResponse = { items: SavedScholarship[] };

export type Institution = {
  unit_id: string;
  name: string;
  aliases: string[];
  city: string;
  state: string;
  website_url: string | null;
  source: "NCES IPEDS";
  source_year: number;
};

export type SourceScope = {
  id: string;
  name: string;
  ownership: "school" | "sponsor";
  adapter: "generic" | "academicworks" | "kaleidoscope";
  canonical_url: string;
  hostname: string;
  allowed_path_prefix: string;
  institution_unit_id: string | null;
  school_revision: number | null;
  status: "proposed" | "active" | "paused" | "inactive" | "policy_blocked";
  confirmed_at: string | null;
  max_depth: number;
  page_budget: number;
  requests_per_minute: number;
  scan_interval_hours: number;
  policy_status: "unknown" | "allowed" | "blocked";
  last_attempt_at: string | null;
  last_success_at: string | null;
  next_scan_at: string | null;
  scan_requested_at: string | null;
  last_error_code: string | null;
};

export type ManualLead = {
  id: string;
  title: string;
  canonical_url: string;
  hostname: string;
  status: "unverified" | "official_verified" | "unavailable" | "rejected";
  official_url: string | null;
  official_hostname: string | null;
  last_attempt_at: string | null;
  verified_at: string | null;
  last_error_code: string | null;
};
