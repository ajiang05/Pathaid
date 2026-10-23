import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const revisionId = "revision-awaiting-review";

const run = {
  id: "run-1",
  parent_run_id: null,
  target_program_id: null,
  draft_revision_id: revisionId,
  scheduled_source_id: "scheduled-source-1",
  scheduled_scan_id: "scheduled-scan-1",
  discovered_candidate_id: "candidate-1",
  source_url: "https://example.edu/scholarship",
  source_method: "webpage",
  state: "awaiting_review",
  error_code: null,
  error_message: null,
  created_at: "2026-10-22T12:00:00Z",
  completed_at: "2026-10-22T12:01:00Z",
};

const proposedDraft = {
  name: "Example University Scholarship",
  description: "A reviewed scholarship for undergraduate students.",
  provider_url: run.source_url,
  categories: ["scholarship"],
};

const review = {
  revision: {
    id: revisionId,
    status: "draft",
    validation_status: "valid",
    provider_url: run.source_url,
    name: proposedDraft.name,
    description: proposedDraft.description,
  },
  proposed_draft: proposedDraft,
  ingestion_run_id: run.id,
  sources: [
    {
      id: "source-snapshot-1",
      source_url: run.source_url,
      source_text: "Applicants must be enrolled undergraduate students.",
      acquired_at: "2026-10-22T12:00:30Z",
    },
  ],
  review_events: [],
};

async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("administrator reviews retained evidence before publishing a draft", async ({ page }) => {
  let approvalBody: unknown;

  await page.route("**/api/admin/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === "/api/admin/auth/session") {
      return route.fulfill({ json: { csrf_token: "admin-csrf", email: "reviewer@example.com" } });
    }
    if (path === "/api/admin/ingestion-runs") {
      return route.fulfill({ json: [run] });
    }
    if (path === `/api/admin/revisions/${revisionId}`) {
      return route.fulfill({ json: review });
    }
    if (path === `/api/admin/revisions/${revisionId}/approve` && request.method() === "POST") {
      approvalBody = request.postDataJSON();
      return route.fulfill({ json: { status: "published" } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/admin/ingestion");
  await expect(page.getByRole("heading", { name: "Ingestion runs" })).toBeVisible();
  await expect(page.getByText("Awaiting Review")).toBeVisible();
  await expect(page.getByText("Scheduled", { exact: true })).toBeVisible();
  await expectNoAccessibilityViolations(page);

  await page.getByRole("link", { name: "Review draft" }).click();
  await expect(page.getByRole("heading", { name: proposedDraft.name })).toBeVisible();
  await expect(page.getByText(review.sources[0].source_text)).toBeVisible();

  const approve = page.getByRole("button", { name: "Approve and publish" });
  await expect(approve).toBeDisabled();
  await page.getByLabel("I verified the proposal against the retained source").check();
  await expect(approve).toBeEnabled();
  await expectNoAccessibilityViolations(page);

  await approve.click();
  await expect(page.getByRole("status")).toHaveText("Revision published.");
  expect(approvalBody).toEqual({ source_accurate: true, coverage_complete: false, notes: "" });
});
