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
    { scholarship_id: "strong-1", name: "Engineering Scholars Award", sponsor: "Example Foundation", award: "$2,500", deadline: "2027-03-15", match_label: "Strong match", key_reasons: ["All known hard requirements pass."], unknown_fields: [], application_url: "https://example.org/apply", saved_status: null },
    { scholarship_id: "possible-1", name: "Community Leadership Scholarship", sponsor: "Example University", award: null, deadline: null, match_label: "Possible match", key_reasons: ["Pell status is required but unknown."], unknown_fields: ["pell_eligible"], application_url: "https://example.edu/apply", saved_status: null },
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
  await expect(page.getByRole("heading", { name: "Engineering Scholars Award", level: 3 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible matches" })).toBeVisible();
  await expect(page.getByText("Community Leadership Scholarship")).toBeVisible();
  await expect(page.getByText("Unknown: Pell Eligible")).toBeVisible();
  await expect(page.locator("form")).toHaveCount(0);
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("save persists a scholarship into the three-state saved workflow", async ({ page }) => {
  await page.unroute("**/api/**");
  let savedStatus: "not_started" | "in_progress" | "already_applied" | null = null;
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/matches") {
      return route.fulfill({ json: { ...matches, results: matches.results.map(item => ({ ...item, saved_status: item.scholarship_id === "strong-1" ? savedStatus : null })) } });
    }
    if (path === "/api/saved-scholarships/strong-1" && request.method() === "PUT") {
      savedStatus = request.postDataJSON().status;
      return route.fulfill({ json: {
        scholarship_id: "strong-1", status: savedStatus, name: "Engineering Scholars Award",
        sponsor: "Example Foundation", award: "$2,500", deadline: "2027-03-15",
        application_url: "https://example.org/apply", availability: "verified_open",
        source_status: "active", source_freshness: "2026-11-01T12:00:00Z",
        created_at: "2026-11-02T12:00:00Z", updated_at: "2026-11-02T12:00:00Z",
      } });
    }
    if (path === "/api/saved-scholarships" && request.method() === "GET") {
      const items = savedStatus ? [{
        scholarship_id: "strong-1", status: savedStatus, name: "Engineering Scholars Award",
        sponsor: "Example Foundation", award: "$2,500", deadline: "2027-03-15",
        application_url: "https://example.org/apply", availability: "verified_open",
        source_status: "active", source_freshness: "2026-11-01T12:00:00Z",
        created_at: "2026-11-02T12:00:00Z", updated_at: "2026-11-02T12:00:00Z",
      }] : [];
      return route.fulfill({ json: { items } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/discover");
  await page.locator("article", { hasText: "Engineering Scholars Award" }).getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved as Not started.")).toBeVisible();
  await page.getByRole("link", { name: "Saved" }).first().click();
  await expect(page.getByRole("heading", { name: "Saved" })).toBeVisible();
  await expect(page.locator(".saved-list").getByText("Engineering Scholars Award")).toBeVisible();
  await page.getByLabel("Status for Engineering Scholars Award").selectOption("already_applied");
  await page.getByRole("tab", { name: /Already applied/ }).click();
  await expect(page.locator(".saved-list").getByRole("heading", { name: "Engineering Scholars Award" })).toBeVisible();
});

test("source registry requires confirmation and keeps manual leads isolated", async ({ page }) => {
  await page.unroute("**/api/**");
  let localProfile = { ...profile, fields: { ...profile.fields } as Record<string, unknown> };
  const sourceItems: Record<string, unknown>[] = [];
  const leadItems: Record<string, unknown>[] = [];
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/profile") return route.fulfill({ json: localProfile });
    if (path === "/api/institutions") return route.fulfill({ json: [{ unit_id: "166629", name: "University of Massachusetts Amherst", aliases: ["UMass"], city: "Amherst", state: "MA", website_url: "https://www.umass.edu/", source: "NCES IPEDS", source_year: 2025 }] });
    if (path === "/api/institutions/166629/select") {
      localProfile = { ...localProfile, fields: { ...localProfile.fields, school_id: "166629", school: "University of Massachusetts Amherst", school_city: "Amherst", school_state: "MA" } };
      return route.fulfill({ json: { changed: true, school_revision: 2 } });
    }
    if (path === "/api/sources" && request.method() === "GET") return route.fulfill({ json: sourceItems });
    if (path === "/api/sources" && request.method() === "POST") {
      const body = request.postDataJSON();
      const item = { ...body, id: "scope-1", hostname: "www.umass.edu", school_revision: 2, status: "proposed", confirmed_at: null, policy_status: "unknown", policy_checked_at: null, last_attempt_at: null, last_success_at: null, last_content_change_at: null, next_scan_at: null, scan_requested_at: null, last_error_code: null };
      sourceItems.push(item);
      return route.fulfill({ status: 201, json: item });
    }
    if (path === "/api/sources/scope-1/confirm") {
      Object.assign(sourceItems[0], { status: "active", confirmed_at: "2026-11-01T12:00:00Z", next_scan_at: null });
      return route.fulfill({ json: sourceItems[0] });
    }
    if (path === "/api/sources/scope-1/policy") {
      Object.assign(sourceItems[0], { policy_status: "allowed", policy_checked_at: "2026-11-01T12:00:30Z", next_scan_at: "2026-11-01T12:00:30Z" });
      return route.fulfill({ json: sourceItems[0] });
    }
    if (path === "/api/sources/scope-1/scan-now") {
      Object.assign(sourceItems[0], { scan_requested_at: "2026-11-01T12:01:00Z" });
      return route.fulfill({ json: sourceItems[0] });
    }
    if (path === "/api/leads" && request.method() === "GET") return route.fulfill({ json: leadItems });
    if (path === "/api/leads" && request.method() === "POST") {
      const body = request.postDataJSON();
      const item = { id: "lead-1", title: body.title, canonical_url: body.url, hostname: "bigfuture.collegeboard.org", status: "unverified", official_url: null, official_hostname: null, last_attempt_at: null, verified_at: null, last_error_code: null };
      leadItems.push(item);
      return route.fulfill({ status: 201, json: item });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
  await page.getByLabel("Find a U.S. college or university").fill("UMass");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText("NCES 2025")).toBeVisible();
  await page.getByRole("button", { name: "Select" }).click();
  await expect(page.getByText(/is now your current school/)).toBeVisible();

  await page.getByLabel("Source name").fill("UMass scholarships");
  await page.getByLabel("Directory URL").fill("https://www.umass.edu/financialaid/undergraduate-scholarships");
  await page.getByLabel("Allowed path prefix").fill("/financialaid");
  await page.getByRole("button", { name: "Save unconfirmed proposal" }).click();
  await expect(page.getByText("Proposed", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Scan now" })).toHaveCount(0);
  await page.getByRole("button", { name: "Confirm boundary" }).click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Scan now" })).toBeDisabled();
  await page.getByRole("button", { name: "Record policy review" }).click();
  await expect(page.getByText("Policy: Allowed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Scan now" }).click();
  await expect(page.getByRole("status")).toHaveText("The source is queued for its next scan.");

  await page.getByLabel("Lead title").fill("BigFuture scholarship");
  await page.getByLabel("Exact URL").fill("https://bigfuture.collegeboard.org/scholarships/example");
  await page.getByRole("button", { name: "Save lead" }).click();
  await expect(page.getByText("Lead saved as one URL. Its surrounding domain was not approved.")).toBeVisible();
  await expect(page.locator(".source-card")).toHaveCount(1);
});
