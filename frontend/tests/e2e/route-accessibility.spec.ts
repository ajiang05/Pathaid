import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const completeness = { known: 0, unknown: 0, unanswered: 1, total: 1, percent_known: 0 };

async function mockLocalApi(page: Page) {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/profile-fields") return route.fulfill({ json: { fields: { school: { section: "school", type: "string", label: "Current college or university", question: "Current college or university", sensitive: false, optional: false, allow_unknown: true, maximum: 120 } }, sections: [{ id: "school", label: "Current school" }], unknown_answer: { status: "unknown" } } });
    if (path === "/api/profile") return route.fulfill({ json: { fields: {}, experiences: [], completeness, school_revision: 0, school_changed: false } });
    if (path === "/api/home-summary") return route.fulfill({ json: { profile_completeness: completeness, active_sources: 0, paused_sources: 0, due_sources: 0, active_scholarships: 0, last_success_at: null, latest_job: null, alerts: [{ code: "school_missing", message: "Select your current school.", href: "/sources" }] } });
    if (path === "/api/matches") return route.fulfill({ json: { results: [], not_matches: [], profile_completeness: completeness, catalog_status: "awaiting_approved_sources" } });
    if (path === "/api/sources" || path === "/api/leads") return route.fulfill({ json: [] });
    if (path === "/api/documents") return route.fulfill({ json: { items: [] } });
    if (path === "/api/essays") return route.fulfill({ json: { items: [] } });
    if (path === "/api/essays/analysis-settings") return route.fulfill({ json: { full_text_analysis_enabled: false, data_tier: "unknown", notice_acknowledged: false, notice: "Full essay text stays local until enabled.", gemini_key_configured: false } });
    if (path === "/api/settings/status") return route.fulfill({ json: { gemini_configured: false, extension_token_available: true, document_vault_key_available: true, extension_configured: false, extension_id: null, backup_format: "AES-256-GCM / scrypt / version 1", backup_excludes: ["Keychain secrets", "managed documents"] } });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });
}

async function expectAccessible(page: Page) {
  const report = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(report.violations).toEqual([]);
}

test.beforeEach(async ({ page }) => mockLocalApi(page));

for (const route of ["/home", "/profile", "/discover", "/sources", "/documents", "/settings", "/privacy"]) {
  test(`${route} has no automated accessibility violations`, async ({ page }) => {
    await page.goto(route);
    await page.locator(".skeleton-panel").waitFor({ state: "detached" }).catch(() => undefined);
    await expectAccessible(page);
  });
}

test("removed account and administrator routes are not product surfaces", async ({ page }) => {
  for (const route of ["/login", "/signup", "/onboarding", "/admin/login"]) {
    const response = await page.goto(route);
    expect(response?.status()).toBe(404);
  }
});
