import { expect, test, type Route } from "@playwright/test";

const completeness = { known: 5, unknown: 1, unanswered: 25, total: 31, percent_known: 16 };
const profile = {
  fields: { school: "University of Massachusetts Amherst", school_state: "MA", current_state: "MA", permanent_state: "NY", study_level: "undergraduate", pell_eligible: { status: "unknown" } },
  experiences: [], completeness, school_revision: 1, school_changed: false,
};
const choice = (section: string, label: string) => ({ section, type: "choice", label, question: label, values: ["MA", "NY", "CA"], sensitive: false, optional: true, allow_unknown: true });
const registry = {
  fields: {
    school: { section: "school", type: "string", label: "Current college or university", question: "Current college or university", sensitive: false, optional: false, allow_unknown: true, maximum: 120 },
    school_state: choice("school", "School state"), current_state: choice("current_residence", "Current residence state"), permanent_state: choice("permanent_residence", "Permanent or home state"),
    pell_eligible: { section: "eligibility", type: "boolean", label: "Pell Grant eligible", question: "Pell Grant eligible", sensitive: true, optional: true, allow_unknown: true },
  },
  sections: [
    { id: "school", label: "Current school" }, { id: "current_residence", label: "Current residence" },
    { id: "permanent_residence", label: "Permanent or home residence" }, { id: "eligibility", label: "Optional eligibility information" },
  ],
  unknown_answer: { status: "unknown" },
};
const matches = {
  results: [
    { scholarship_id: "strong-1", name: "Engineering Scholars Award", sponsor: "Example Foundation", award: "$2,500", deadline: "2027-03-15", match_label: "Strong match", key_reasons: ["All known hard requirements pass."], unknown_fields: [] },
    { scholarship_id: "possible-1", name: "Community Leadership Scholarship", sponsor: "Example University", award: null, deadline: null, match_label: "Possible match", key_reasons: ["Pell status is required but unknown."], unknown_fields: ["pell_eligible"] },
  ], not_matches: [], profile_completeness: completeness, catalog_status: "ready",
};

async function fulfillApi(route: Route) {
  const path = new URL(route.request().url()).pathname;
  if (path === "/api/profile-fields") return route.fulfill({ json: registry });
  if (path === "/api/profile") {
    if (route.request().method() === "DELETE") return route.fulfill({ status: 204 });
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      return route.fulfill({ json: { ...profile, fields: body.fields, experiences: body.experiences } });
    }
    return route.fulfill({ json: profile });
  }
  if (path === "/api/matches") return route.fulfill({ json: matches });
  return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
}

test.beforeEach(async ({ page }) => page.route("**/api/**", fulfillApi));

test("root opens the accountless local home", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole("heading", { name: "Your scholarship search" })).toBeVisible();
  await expect(page.getByText("Private on this Mac")).toBeVisible();
  await expect(page.getByRole("link", { name: /log in|sign up/i })).toHaveCount(0);
});

test("profile separates locations, unknown answers, and structured experiences", async ({ page }) => {
  await page.goto("/profile");
  await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Current school" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Current residence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Permanent or home residence" })).toBeVisible();
  await expect(page.getByLabel("Current residence state", { exact: true })).toHaveValue("MA");
  await expect(page.getByLabel("Permanent or home state", { exact: true })).toHaveValue("NY");
  await expect(page.getByLabel("Pell Grant eligible answer status")).toHaveValue("unknown");

  await page.getByRole("button", { name: "Add experience" }).click();
  await page.getByLabel("Experience 1 type").selectOption("volunteering");
  await page.getByLabel("Experience 1 organization").fill("Community Food Bank");
  await page.getByLabel("Experience 1 title").fill("Volunteer coordinator");
  await page.getByLabel("Experience 1 tags").fill("service, food security");
  const patch = page.waitForRequest(request => request.url().endsWith("/api/profile") && request.method() === "PATCH");
  await page.getByRole("button", { name: "Save profile" }).click();
  const body = (await patch).postDataJSON();
  expect(body.fields.current_state).toBe("MA");
  expect(body.fields.permanent_state).toBe("NY");
  expect(body.fields.pell_eligible).toEqual({ status: "unknown" });
  expect(body.experiences[0]).toMatchObject({ kind: "volunteering", organization: "Community Food Bank", leadership: false, tags: ["service", "food security"] });
  await expect(page.getByRole("status")).toHaveText("Profile saved locally.");
});

test("discover groups deterministic matches without inline questions", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strong matches" })).toBeVisible();
  await expect(page.getByText("Engineering Scholars Award")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible matches" })).toBeVisible();
  await expect(page.getByText("Community Leadership Scholarship")).toBeVisible();
  await expect(page.getByText("Unknown: Pell Eligible")).toBeVisible();
  await expect(page.locator("form")).toHaveCount(0);
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
