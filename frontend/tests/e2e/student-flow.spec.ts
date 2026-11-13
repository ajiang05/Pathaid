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
    school_id: { section: "school", type: "string", label: "Institution identifier", question: "Institution identifier", sensitive: false, optional: true, allow_unknown: true },
    school_city: { section: "school", type: "string", label: "School city", question: "School city", sensitive: false, optional: true, allow_unknown: true },
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
    { scholarship_id: "strong-1", name: "Engineering Scholars Award", sponsor: "Example Foundation", award: "$2,500", deadline: "2027-03-15", match_label: "Strong match", key_reasons: ["All known hard requirements pass."], unknown_fields: [], application_url: "https://example.org/apply", saved_status: null, application_process: "separate_application", official_rules_url: null },
    { scholarship_id: "possible-1", name: "Community Leadership Scholarship", sponsor: "Example University", award: null, deadline: null, match_label: "Possible match", key_reasons: ["Pell status is required but unknown."], unknown_fields: ["pell_eligible"], application_url: "https://example.edu/apply", saved_status: null, application_process: "separate_application", official_rules_url: null },
  ],
  automatically_considered: [
    { scholarship_id: "automatic-1", name: "Campus Merit Award", sponsor: "Example University", award: "$1,000", deadline: null, match_label: "Strong match", key_reasons: ["All known hard requirements pass."], unknown_fields: [], application_url: "https://example.edu/merit", saved_status: null, application_process: "automatically_considered", official_rules_url: null },
  ],
  sweepstakes: [
    { scholarship_id: "sweepstakes-1", name: "Monthly Student Drawing", sponsor: "Example Foundation", award: "$500", deadline: "2027-03-31", match_label: "Strong match", key_reasons: ["All known hard requirements pass."], unknown_fields: [], application_url: "https://example.org/enter", saved_status: null, application_process: "sweepstakes", official_rules_url: "https://example.org/rules" },
  ],
  not_matches: [], profile_completeness: completeness, catalog_status: "ready",
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
  if (path === "/api/home-summary") return route.fulfill({ json: { profile_completeness: completeness, active_sources: 1, paused_sources: 0, due_sources: 0, active_scholarships: 4, last_success_at: "2026-11-01T12:00:00Z", latest_job: { status: "succeeded", stage: "complete", error_code: null, updated_at: "2026-11-01T12:00:00Z" }, alerts: [] } });
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
  await expect(page.getByRole("group", { name: "Pell Grant eligible" }).getByRole("radio", { name: "I don't know" })).toBeChecked();

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

test("profile selects an official college and fills its identifier", async ({ page }) => {
  await page.unroute("**/api/**");
  let localProfile = { ...profile, fields: { ...profile.fields } as Record<string, unknown> };
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/profile-fields") return route.fulfill({ json: registry });
    if (path === "/api/profile") return route.fulfill({ json: localProfile });
    if (path === "/api/institutions") return route.fulfill({ json: [{ unit_id: "166629", name: "University of Massachusetts Amherst", aliases: ["UMass"], city: "Amherst", state: "MA", website_url: "https://www.umass.edu/", source: "NCES IPEDS", source_year: 2025 }] });
    if (path === "/api/institutions/166629/select" && request.method() === "POST") {
      localProfile = { ...localProfile, fields: { ...localProfile.fields, school_id: "166629", school: "University of Massachusetts Amherst", school_city: "Amherst", school_state: "MA" } };
      return route.fulfill({ json: { changed: true, school_revision: 2, institution: { unit_id: "166629", name: "University of Massachusetts Amherst", aliases: ["UMass"], city: "Amherst", state: "MA", website_url: "https://www.umass.edu/", source: "NCES IPEDS", source_year: 2025 }, source_suggestions: [] } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/profile");
  await page.getByLabel("Search for your college").fill("UMass Amherst");
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("button", { name: "Select" }).click();
  await expect(page.getByText("166629", { exact: true })).toBeVisible();
  await expect(page.getByText("Amherst, MA", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("institution identifier was filled automatically");
  await expect(page.getByLabel("Institution identifier")).toHaveCount(0);
});

test("discover groups deterministic matches without inline questions", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strong matches" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engineering Scholars Award", level: 3 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible matches" })).toBeVisible();
  await expect(page.getByText("Community Leadership Scholarship")).toBeVisible();
  await expect(page.getByText("Unknown: Pell Eligible")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Automatically considered" })).toBeVisible();
  const automatic = page.locator("article", { hasText: "Campus Merit Award" });
  await expect(automatic.getByText("No separate application required")).toBeVisible();
  await expect(automatic.getByRole("button", { name: /Apply|Enter/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Verified sweepstakes" })).toBeVisible();
  const sweepstakes = page.locator("article", { hasText: "Monthly Student Drawing" });
  await expect(sweepstakes.getByRole("link", { name: "Official rules" })).toHaveAttribute("href", "https://example.org/rules");
  await expect(page.locator("form")).toHaveCount(0);
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("discover detail shows evidence and save/apply never submits", async ({ page, context }) => {
  await page.unroute("**/api/**");
  let savedStatus: "not_started" | "in_progress" | null = null;
  await context.route("https://example.org/apply", route => route.fulfill({
    contentType: "text/html", body: "<h1>Official application fixture</h1><button>Submit application</button>",
  }));
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/matches") return route.fulfill({ json: matches });
    if (path === "/api/local/status") return route.fulfill({ json: { mode: "local_single_user", database: "sqlite", extension_configured: false, extension_id: null } });
    if (path === "/api/scholarships/strong-1" && request.method() === "GET") return route.fulfill({ json: {
      scholarship_id: "strong-1", name: "Engineering Scholars Award",
      description: "Supports undergraduate engineering students.", sponsor: "Example Foundation",
      award: "$2,500", deadline: "2027-03-15", availability: "verified_open",
      application_process: "separate_application", application_url: "https://example.org/apply",
      official_rules_url: null, source_url: "https://example.org/scholarship",
      source_freshness: "2026-11-01T12:00:00Z", match_label: "Strong match",
      coverage_complete: true,
      criteria: [{ field: "gpa", operator: "gte", truth: "pass", reason: "gpa passes this requirement.", answerable: true, evidence: { snapshot_id: "snapshot-1", excerpt: "Applicants must have a 3.0 GPA." } }],
      unknown_fields: [], unresolved_conditions: [],
      selection_factors: [{ description: "Community service is considered.", evidence: { snapshot_id: "snapshot-1", excerpt: "Community service is considered." } }],
      checklist: [{ label: "Transcript", required: true, evidence: { snapshot_id: "snapshot-1", excerpt: "Upload a transcript." } }],
      coverage: { national: true, states: [], institutions: [] },
      automation_policy: "unknown", ai_assistance_policy: "unknown", saved_status: savedStatus,
    } });
    if (path === "/api/saved-scholarships/strong-1" && request.method() === "PUT") {
      savedStatus = request.postDataJSON().status;
      return route.fulfill({ json: { scholarship_id: "strong-1", status: savedStatus } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/discover");
  await page.locator("article", { hasText: "Engineering Scholars Award" }).getByRole("link", { name: "View details" }).click();
  await expect(page).toHaveURL(/\/scholarships\/strong-1$/);
  await expect(page.getByRole("heading", { name: "Engineering Scholars Award" })).toBeVisible();
  await expect(page.getByText("Applicants must have a 3.0 GPA.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Application materials" })).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved as Not started.");
  expect(savedStatus).toBe("not_started");

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Apply" }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Official application fixture" })).toBeVisible();
  await expect(popup.getByRole("button", { name: "Submit application" })).toBeVisible();
  expect(savedStatus).toBe("in_progress");
  await popup.close();
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
      return route.fulfill({ json: { changed: true, school_revision: 2, institution: { unit_id: "166629", name: "University of Massachusetts Amherst" }, source_suggestions: [{ name: "UMass scholarships", canonical_url: "https://www.umass.edu/financialaid/scholarships", allowed_path_prefix: "/financialaid", adapter: "generic" }] } });
    }
    if (path === "/api/sources" && request.method() === "GET") return route.fulfill({ json: sourceItems });
    if (path === "/api/sources" && request.method() === "POST") {
      const body = request.postDataJSON();
      const item = { ...body, id: "scope-1", hostname: "www.umass.edu", school_revision: 2, status: "proposed", confirmed_at: null, policy_status: "unknown", policy_checked_at: null, last_attempt_at: null, last_success_at: null, last_content_change_at: null, next_scan_at: null, scan_requested_at: null, last_error_code: null, scan_progress: null };
      sourceItems.push(item);
      return route.fulfill({ status: 201, json: item });
    }
    if (path === "/api/sources/scope-1" && request.method() === "PATCH") {
      const body = request.postDataJSON();
      Object.assign(sourceItems[0], body, { status: "proposed", confirmed_at: null, policy_status: "unknown", policy_checked_at: null, next_scan_at: null, scan_requested_at: null });
      return route.fulfill({ json: sourceItems[0] });
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
      Object.assign(sourceItems[0], { scan_requested_at: "2026-11-01T12:01:00Z", scan_progress: { status: "queued", stage: "acquisition", attempt: 0, max_attempts: 3, error_code: null, pages_attempted: 0, snapshots_created: 0, started_at: null, finished_at: null, updated_at: "2026-11-01T12:01:00Z" } });
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
  await page.getByLabel("Scanning policy").selectOption("allowed");
  await expect(page.getByText("Policy: Allowed", { exact: true })).toBeVisible();
  await expect(page.locator(".feedback-toast")).toHaveText(/Scanning policy saved: allowed/);
  await page.getByRole("button", { name: "Scan now" }).click();
  await expect(page.locator(".feedback-toast")).toHaveText(/The source is queued for its next scan/);
  await expect(page.locator(".feedback-toast")).toHaveCSS("position", "fixed");
  await expect(page.locator(".source-card").getByText("Scan: Queued")).toBeVisible();
  await expect(page.locator(".source-card").locator(".scan-spinner")).toBeVisible();

  const sourceCard = page.locator(".source-card");
  await sourceCard.getByRole("button", { name: "Edit" }).click();
  await sourceCard.getByLabel("Source name").fill("UMass AcademicWorks scholarships");
  await sourceCard.getByLabel("Page budget").fill("30");
  await sourceCard.getByRole("button", { name: "Save changes" }).click();
  await expect(sourceCard.getByRole("heading", { name: "UMass AcademicWorks scholarships" })).toBeVisible();
  await expect(sourceCard.getByText("Proposed", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("confirm the boundary and review its policy again");

  await page.getByLabel("Lead title").fill("BigFuture scholarship");
  await page.getByLabel("Exact URL").fill("https://bigfuture.collegeboard.org/scholarships/example");
  await page.getByRole("button", { name: "Save lead" }).click();
  await expect(page.getByText("Lead saved as one URL. Its surrounding domain was not approved.")).toBeVisible();
  await expect(sourceCard).toHaveCount(1);
});

test("settings saves secrets and downloads only an encrypted backup", async ({ page }) => {
  await page.unroute("**/api/**");
  let geminiConfigured = false;
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/settings/status") return route.fulfill({ json: {
      gemini_configured: geminiConfigured,
      extension_token_available: true,
      document_vault_key_available: true,
      extension_configured: true,
      extension_id: "abcdefghijklmnopabcdefghijklmnop",
      backup_format: "AES-256-GCM / scrypt / version 1",
      backup_excludes: ["Keychain secrets", "résumé and transcript ciphertext"],
    } });
    if (path === "/api/settings/gemini-key" && request.method() === "PUT") {
      expect(request.postDataJSON().key).toBe("test-gemini-key");
      geminiConfigured = true;
      return route.fulfill({ json: { configured: true } });
    }
    if (path === "/api/settings/backup" && request.method() === "POST") {
      expect(request.postDataJSON().passphrase).toBe("correct horse battery staple");
      return route.fulfill({
        body: Buffer.from("PATHAID-BACKUP\0encrypted"),
        contentType: "application/octet-stream",
        headers: { "Content-Disposition": 'attachment; filename="pathaid-test.pathaid-backup"' },
      });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await page.getByLabel("New Gemini API key").fill("test-gemini-key");
  await page.getByRole("button", { name: "Save key in Keychain" }).click();
  await expect(page.getByRole("status")).toContainText("Gemini key saved in macOS Keychain.");
  await expect(page.getByLabel("New Gemini API key")).toHaveValue("");

  await page.getByLabel("Backup passphrase").fill("correct horse battery staple");
  await page.getByLabel("Confirm passphrase").fill("correct horse battery staple");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download encrypted backup" }).click();
  await expect((await download).suggestedFilename()).toBe("pathaid-test.pathaid-backup");
  await expect(page.getByRole("status")).toContainText("Encrypted backup downloaded");
  await expect(page.getByLabel("Backup passphrase")).toHaveValue("");
});
