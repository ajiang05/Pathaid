export type FieldSpec = {
  type: "string" | "choice" | "multi_choice" | "boolean" | "integer" | "number";
  question: string;
  values?: string[];
  sensitive: boolean;
  progressive: boolean;
};

export type ProfileFields = Record<string, string | number | boolean | string[] | null>;
export type Profile = { fields: ProfileFields; ai_opt_in: boolean };
export type FieldRegistry = { fields: Record<string, FieldSpec>; unknown_answer: null };

export type Evidence = { snapshot_id?: string; quote?: string; source_url?: string | null };
export type Criterion = { id:string; field:string; operator:string; truth:string; reason:string; answerable:boolean; evidence:Evidence };
export type MissingField = { field:string; question:string; answer_type:string; values?:unknown[] | null; sensitive:boolean };
export type ProgramResult = {
  program_id:string; revision_id:string; name:string; description:string; categories:string[];
  label:string; truth:string; criteria:Criterion[]; missing_fields:MissingField[];
  unresolved_conditions:string[]; application_availability:string; application_deadline:string|null;
  deadline_timezone:string|null; deadline_verification:string; deadline_timezone_verification:string;
  assistance_amount:string|null; amount_verification:string; award_cycle:string|null; award_cycle_verification:string;
  checklist:Record<string,unknown>[]; checklist_verification:string; selection_factors:Record<string,unknown>[];
  verified_at:string|null; provider_url:string; application_url:string|null; sources:Record<string,unknown>[];
  coverage:Record<string,unknown>; template_explanation:string; availability_section:string|null;
  relevance:string|null; ranking_factors:Record<string,string>;
};
export type Evaluation = { categories:string[]; results:ProgramResult[] };

export type ProgramDetail = {
  id:string; revision_id:string; slug:string; name:string; description:string; categories:string[];
  coverage:Record<string,unknown>; assistance_amount:string|null; application_deadline:string|null;
  deadline_timezone:string|null; application_availability:string; verified_at:string|null;
  checklist:Record<string,unknown>[]; eligibility_tree:Record<string,unknown>; coverage_complete:boolean;
  award_cycle:string|null; selection_factors:Record<string,unknown>[]; provider_url:string;
  application_url:string|null; sources:Array<{id:string;source_url:string;acquired_at:string;acquisition_method:string}>;
};
