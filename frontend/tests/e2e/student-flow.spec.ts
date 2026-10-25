import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const profile = {
  fields: {
    school: "University of Massachusetts Amherst",
    state: "MA",
    study_level: "undergraduate",
    enrollment: "full_time",
    assistance_categories: ["scholarship"],
  },
  ai_opt_in: false,
};

const result = {
  program_id: "mass-opportunity",
  revision_id: "revision-1",
  name: "Massachusetts Student Opportunity Grant",
  description: "Support for eligible undergraduate students in Massachusetts.",
  categories: ["scholarship"],
  label: "Likely eligible",
  truth: "true",
  criteria: [{ id: "state", field: "state", operator: "equals", truth: "true", reason: "You reported living in Massachusetts.", answerable: true, evidence: { quote: "Applicants must be Massachusetts residents.", source_url: "https://example.edu/grant" } }],
  missing_fields: [],
  unresolved_conditions: [],
  application_availability: "verified_open",
  application_deadline: "2027-03-15",
  deadline_timezone: "America/New_York",
  deadline_verification: "verified",
  deadline_timezone_verification: "verified",
  assistance_amount: "$2,500",
  amount_verification: "verified",
  award_cycle: "2026-2027",
  award_cycle_verification: "verified",
  checklist: [{ item: "Transcript", description: "Upload an unofficial transcript." }],
  checklist_verification: "verified",
  selection_factors: [],
  verified_at: "2026-10-20T12:00:00Z",
  provider_url: "https://example.edu/grant",
  application_url: "https://example.edu/grant/apply",
  sources: [{ source_url: "https://example.edu/grant" }],
  coverage: {},
  template_explanation: "Your saved profile meets the reviewed residency requirement.",
  availability_section: "Open opportunities",
  relevance: "high",
  ranking_factors: {},
};

async function mockStudentApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/session") return route.fulfill({ json: { csrf_token: "test-csrf" } });
    if (path === "/api/profile") return route.fulfill({ json: profile });
    if (path === "/api/evaluate") return route.fulfill({ json: { categories: ["scholarship"], results: [result] } });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });
}

async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("landing page leads to account creation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /find financial support/i })).toBeVisible();
  await page.getByRole("link", { name: "Build your profile" }).click();
  await expect(page).toHaveURL(/\/signup$/);
  await expect(page.getByRole("heading", { name: "Start finding support" })).toBeVisible();
  await expectNoAccessibilityViolations(page);
});

test("new account enters onboarding with a refreshed session", async ({ page }) => {
  let authenticated = false;
  const profileFields = {
    fields: {
      school: { type: "string", question: "What school do you attend?" },
      state: { type: "choice", question: "What state do you live in?", values: ["MA"] },
      study_level: { type: "choice", question: "What is your study level?", values: ["undergraduate"] },
      enrollment: { type: "choice", question: "What is your enrollment status?", values: ["full_time"] },
      assistance_categories: { type: "multi_choice", question: "What support are you looking for?", values: ["scholarship"] },
    },
  };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/session") {
      return authenticated
        ? route.fulfill({ json: { csrf_token: "test-csrf" } })
        : route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    }
    if (path === "/api/auth/signup") {
      authenticated = true;
      return route.fulfill({ status: 201, json: { csrf_token: "test-csrf" } });
    }
    if (path === "/api/profile-fields") return route.fulfill({ json: profileFields });
    if (path === "/api/profile") return route.fulfill({ json: { fields: {}, ai_opt_in: false } });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/signup");
  await page.getByLabel("Email address").fill("new-student@example.com");
  await page.getByLabel("Password").fill("a-secure-test-password");
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: /tell us what support fits/i })).toBeVisible();
  await expect(page.getByText("Log in to continue.")).not.toBeVisible();
});

test("authenticated student can discover and inspect a reviewed result", async ({ page }) => {
  await mockStudentApi(page);
  await page.goto("/home");
  await expect(page.getByRole("heading", { name: "Your support search starts here" })).toBeVisible();
  await expectNoAccessibilityViolations(page);
  await page.getByRole("link", { name: "Discover support" }).click();
  await expect(page.getByRole("heading", { name: "Open opportunities" })).toBeVisible();
  await expect(page.getByText(result.name)).toBeVisible();
  await expectNoAccessibilityViolations(page);
  await page.getByRole("link", { name: "View details" }).click();
  await expect(page.getByRole("heading", { name: result.name })).toBeVisible();
  await expect(page.getByText("Reviewed eligibility requirements")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open official provider site" })).toHaveAttribute("href", result.application_url);
  await expectNoAccessibilityViolations(page);
});
