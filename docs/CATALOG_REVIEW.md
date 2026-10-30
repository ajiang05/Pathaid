# Launch catalog review record

Status: automated and source-level audit updated locally on October 30, 2026. Human attestation and publication remain pending for 10 programs; Gates and Pell are already published.

This record identifies the 12 intended MVP launch candidates and the final checks an administrator must make before publication. Automated extraction, deterministic validation, and this engineering audit do not replace the administrator's source-accuracy attestation.

## Queue note

The local review queue contains extra drafts because live integration checks produced stronger replacements. Use only the revision IDs named in the candidate table below. The final repair set includes Pell and Gates replacements from earlier controlled runs, Adams from prompt 1.3.0, four prompt-1.3.0 replacements for legacy-schema drafts, and two source-backed correction drafts created through the invalid-draft recovery workflow. Reject each older draft after confirming its replacement. Publish only one revision for each program.

## Candidate audit

| Candidate | Official source | Engineering audit | Final reviewer focus |
|---|---|---|---|
| The Gates Scholarship | [Provider page](https://www.thegatesscholarship.org/scholarship/) | Replacement revision `0e9b57b5-48d2-4e51-8c08-4f325384049f` passed after the prompt mapped exact profile values, represented high-school standing as unsupported, and recorded the page's stale open-status conflict. | Confirm the displayed status against its September 15, 2026 deadline; keep rule coverage incomplete and reject the older Gates draft. |
| College Scholarship Program | [Jack Kent Cooke Foundation](https://www.jkcf.org/our-scholarships/college-scholarship-program/how-to-apply/) | Revision `558ebe25-c7c4-4811-ba68-7f8014974727` passed with warnings for human-interpreted achievement/need rules and an unstated deadline timezone. | Confirm the November 11, 2026 deadline and $55,000-per-year maximum. |
| Federal Pell Grant | [Federal Student Aid](https://studentaid.gov/articles/dont-miss-out-on-pell-grants/) | Published revision `17a55d53-8138-430b-ab43-43a6848cce35` passed with an unsupported-logic warning; maximum 2026–27 award is recorded as $7,395. | Reject the superseded loading-placeholder draft. |
| UMass Amherst Financial Aid Overview | [UMass Amherst](https://www.umass.edu/financialaid/types-aid-undergraduate) | Replacement revision `e257d466-de0d-4eee-a762-56cdaa36c22d` passed with program-specific eligibility preserved as unsupported and unresolved. | Confirm that this broad aid overview is useful as one catalog resource rather than a single award; keep coverage incomplete. |
| Angel Fund Emergency Grant | [UMass Amherst](https://www.umass.edu/dean-students/basic-needs/angel-fund-emergency-grant) | Correction revision `700dfafc-51f0-4963-8e28-77c3c36c71f4` passed after replacing an all-study-level tautology with an unsupported enrolled-student requirement. Immigration-policy circumstances remain human interpreted. | Confirm current availability and keep coverage incomplete. |
| Mass 211 Housing/Shelter Services | [Mass 211](https://mass211.org/housing-shelter) | Replacement revision `e3eb83f9-b123-4ec9-94c6-0146e0b79be2` passed with referral-specific eligibility explicitly unsupported and dependent resource rules unresolved. | Confirm that the referral service, rather than direct funding, is appropriate for the housing category; keep coverage incomplete. |
| Coca-Cola Scholars Program Scholarship | [Foundation page](https://www.coca-colascholarsfoundation.org/apply/) | Revision `71a2338a-18eb-4589-af52-03ea7715d460` passed after correcting the deadline to September 30, 2026 at 5 p.m. America/New_York and removing redundant state coverage. | Confirm the cycle is closed as of the audit date and keep high-school standing human interpreted. |
| MASSGrant Plus | [Massachusetts DHE](https://www.mass.edu/osfa/programs/massgrantplus.asp) | Revision `a807666c-26cd-4eff-8a3f-c1f5db31c191` passed after replacing unsafe citizenship and prior-degree mappings with human-interpreted requirements. | Confirm the listed institutions, income-dependent benefit, and 2026–27 rules; keep coverage incomplete. |
| UMass Amherst Undergraduate Scholarships | [UMass Amherst](https://www.umass.edu/financialaid/undergraduate-scholarships) | Replacement revision `b03cea23-14cf-4582-aa52-6c17e9e3949f` passed with undergraduate/full-time enrollment modeled and satisfactory academic progress preserved as unsupported. | Confirm whether the page should remain one umbrella resource or be split into individual awards later; keep coverage incomplete. |
| UMass Amherst Food Security Support | [UMass Amherst](https://www.umass.edu/dean-students/basic-needs/food-security) | Replacement revision `b6ca5b35-122f-4a47-92d5-472ba4936a6f` passed current validation. | Confirm current pantry and registration instructions and whether the umbrella page has complete eligibility coverage. |
| Community Foundation of Western Massachusetts Scholarship Program | [Community Foundation](https://communityfoundation.org/students/scholarships/) | Correction revision `5b9bcd67-e15a-44db-bd6b-50007be0a944` passed after replacing an all-study-level tautology with one complete unsupported enrollment/institution requirement. The source does not state a named deadline timezone. | Confirm the closed March 1, 2026 cycle, regional exceptions, and $3,000 maximum; keep coverage incomplete. |
| John and Abigail Adams Scholarship | [Massachusetts DHE](https://www.mass.edu/osfa/programs/adams.asp) | Replacement revision `9bdca1d9-7303-4ca8-9b0c-7be713494ab2` passed after prompt 1.3.0 preserved every stated mandatory requirement. MCAS/high-school standing, complex residency/citizenship, annual FAFSA/MASFA, eligible program/institution, prior-degree, and loan/refund rules remain safely unsupported; full-time enrollment is modeled. | Confirm current institutional award values and the no-application process; keep coverage incomplete and reject the older Adams drafts. |

## Required publication procedure

1. Sign in at `/admin/login` and open the awaiting-review queue.
2. For each selected draft, compare every rule, checklist item, amount, deadline, link, and coverage field with its retained source.
3. Resolve or consciously accept every warning. Set coverage complete only when no unsupported or unresolved requirement remains.
4. Attest source accuracy and approve, or reject with a short reason. Approval creates the immutable review event and public revision pointer.
5. Reject every awaiting draft whose revision ID is not the selected ID in the table, including superseded Pell, Gates, Adams, and legacy-schema drafts.
6. Confirm that exactly 12 programs appear through the public catalog API and student discovery interface.
7. Export the reviewed bundle using `python -m app.catalog_seed export` and store it according to the deployment runbook.

Publication is complete only after those human decisions exist in the database. Never create approval events directly or import a bundle that invents reviewer identity.
