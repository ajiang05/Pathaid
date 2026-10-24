# Launch catalog review record

Status: automated and source-level audit completed locally on October 24, 2026. Human attestation and publication remain pending.

This record identifies the 12 intended MVP launch candidates and the final checks an administrator must make before publication. Automated extraction, deterministic validation, and this engineering audit do not replace the administrator's source-accuracy attestation.

## Queue note

The local review queue contains 13 drafts because the original Federal Pell Grant acquisition retained only a JavaScript loading placeholder. Use revision `17a55d53-8138-430b-ab43-43a6848cce35`, which was extracted from the official Federal Student Aid article, and reject the older Pell draft after confirming the replacement. Do not publish both.

## Candidate audit

| Candidate | Official source | Engineering audit | Final reviewer focus |
|---|---|---|---|
| The Gates Scholarship | [Provider page](https://www.thegatesscholarship.org/scholarship/) | Passed validation after changing the expired 2026 cycle to closed and mapping profile values to the canonical vocabulary. | Confirm the page's displayed status against its September 15, 2026 deadline; keep rule coverage incomplete because high-school standing is not a supported profile field. |
| College Scholarship Program | [Jack Kent Cooke Foundation](https://www.jkcf.org/our-scholarships/college-scholarship-program/how-to-apply/) | Passed with warnings for human-interpreted achievement/need rules and an unstated deadline timezone. | Confirm the November 11, 2026 deadline and $55,000-per-year maximum. |
| Federal Pell Grant | [Federal Student Aid](https://studentaid.gov/articles/dont-miss-out-on-pell-grants/) | Replacement draft passed with an unsupported-logic warning; maximum 2026–27 award is recorded as $7,395. | Review the replacement revision named above and reject the loading-placeholder draft. |
| UMass Amherst Financial Aid Overview | [UMass Amherst](https://www.umass.edu/financialaid/types-aid-undergraduate) | Passed without findings. | Confirm that this broad aid overview is useful as one catalog resource rather than a single award. |
| Angel Fund Emergency Grant | [UMass Amherst](https://www.umass.edu/dean-students/basic-needs/angel-fund-emergency-grant) | Passed after canonicalizing the institution and safely representing enrolled status; immigration-policy circumstances remain human interpreted. | Confirm current availability and keep coverage incomplete. |
| Mass 211 Housing/Shelter Services | [Mass 211](https://mass211.org/housing-shelter) | Passed without findings. | Confirm that the referral service, rather than direct funding, is appropriate for the housing category. |
| Coca-Cola Scholars Program Scholarship | [Foundation page](https://www.coca-colascholarsfoundation.org/apply/) | Passed after correcting the deadline to September 30, 2026 at 5 p.m. America/New_York and removing redundant state coverage. | Confirm the cycle is closed as of the audit date and keep high-school standing human interpreted. |
| MASSGrant Plus | [Massachusetts DHE](https://www.mass.edu/osfa/programs/massgrantplus.asp) | Passed after replacing unsafe citizenship and prior-degree mappings with human-interpreted requirements. | Confirm the listed institutions, income-dependent benefit, and 2026–27 rules; keep coverage incomplete. |
| UMass Amherst Undergraduate Scholarships | [UMass Amherst](https://www.umass.edu/financialaid/undergraduate-scholarships) | Passed after removing the unsupported grants category and canonicalizing full-time enrollment. | Confirm whether the page should remain one umbrella resource or be split into individual awards later. |
| UMass Amherst Food Security Support | [UMass Amherst](https://www.umass.edu/dean-students/basic-needs/food-security) | Passed without findings. | Confirm current pantry and registration instructions. |
| Community Foundation of Western Massachusetts Scholarship Program | [Community Foundation](https://communityfoundation.org/students/scholarships/) | Passed after safely representing full- or part-time enrollment; the source does not state a named deadline timezone. | Confirm the closed March 1, 2026 cycle, regional exceptions, and $3,000 maximum. |
| John and Abigail Adams Scholarship | [Massachusetts DHE](https://www.mass.edu/osfa/programs/adams.asp) | Passed with an unsupported-logic warning for MCAS and Massachusetts high-school requirements. | Confirm current institutional award values and that there is no separate application process. |

## Required publication procedure

1. Sign in at `/admin/login` and open the awaiting-review queue.
2. For each selected draft, compare every rule, checklist item, amount, deadline, link, and coverage field with its retained source.
3. Resolve or consciously accept every warning. Set coverage complete only when no unsupported or unresolved requirement remains.
4. Attest source accuracy and approve, or reject with a short reason. Approval creates the immutable review event and public revision pointer.
5. Reject the superseded Pell loading-placeholder draft.
6. Confirm that exactly 12 programs appear through the public catalog API and student discovery interface.
7. Export the reviewed bundle using `python -m app.catalog_seed export` and store it according to the deployment runbook.

Publication is complete only after those human decisions exist in the database. Never create approval events directly or import a bundle that invents reviewer identity.
