import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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

const registry = {
  fields: {
    school: { type: "text", question: "What school do you attend?", progressive: false, sensitive: false },
    state: { type: "choice", question: "What state do you live in?", progressive: false, sensitive: false, values: ["MA", "CT"] },
    study_level: {
      type: "choice",
      question: "What is your study level?",
      progressive: false,
      sensitive: false,
      values: ["undergraduate", "graduate"],
    },
    enrollment: {
      type: "choice",
      question: "What is your enrollment status?",
      progressive: false,
      sensitive: false,
      values: ["full_time", "part_time"],
    },
    assistance_categories: {
      type: "multi_choice",
      question: "What kinds of support are you looking for?",
      progressive: false,
      sensitive: false,
      values: ["scholarship", "grants", "food"],
    },
  },
};

async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function mockStudentProfileApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/session") return route.fulfill({ json: { csrf_token: "student-csrf" } });
    if (path === "/api/profile-fields") return route.fulfill({ json: registry });
    if (path === "/api/profile") return route.fulfill({ json: profile });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });
}

test("student and administrator login routes have accessible forms", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Log in to PathAid" })).toBeVisible();
  await expectNoAccessibilityViolations(page);

  await page.goto("/admin/login");
  await expect(page.getByRole("heading", { name: "Administrator login" })).toBeVisible();
  await expectNoAccessibilityViolations(page);
});

test("authenticated onboarding and profile routes expose accessible fields", async ({ page }) => {
  await mockStudentProfileApi(page);

  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "Tell us what support fits your situation" })).toBeVisible();
  await expect(page.getByLabel("What school do you attend?")).toHaveValue(profile.fields.school);
  await page.getByLabel("What school do you attend?").selectOption({ label: "Other" });
  const otherSchool = page.getByLabel("Enter your college name");
  await expect(otherSchool).toBeVisible();
  await expect(otherSchool).toHaveAttribute("required", "");
  await otherSchool.fill("Springfield Community College");
  await expectNoAccessibilityViolations(page);

  await page.goto("/profile");
  await expect(page.getByRole("heading", { name: "Profile and privacy" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete my account" })).toBeVisible();
  await expectNoAccessibilityViolations(page);
});

test("administrator scheduled-source route is accessible", async ({ page }) => {
  const source = {
    id: "scheduled-source-1",
    canonical_url: "https://example.edu/scholarships",
    source_type: "discovery_page",
    enabled: true,
    cadence_hours: 24,
    allowed_hostname: "example.edu",
    allowed_path_prefix: "/scholarships",
    discovery_link_limit: 20,
    respect_robots: true,
    next_scan_at: "2026-10-25T12:00:00Z",
    last_attempt_at: "2026-10-24T12:00:00Z",
    last_success_at: "2026-10-24T12:00:00Z",
    last_error_code: null,
    consecutive_failures: 0,
  };

  await page.route("**/api/admin/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/admin/auth/session") {
      return route.fulfill({ json: { csrf_token: "admin-csrf", email: "reviewer@example.com" } });
    }
    if (path === "/api/admin/scheduled-sources") return route.fulfill({ json: [source] });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/admin/sources");
  await expect(page.getByRole("heading", { name: "Scheduled sources" })).toBeVisible();
  await expect(page.getByRole("link", { name: source.canonical_url })).toBeVisible();
  await expectNoAccessibilityViolations(page);
});
