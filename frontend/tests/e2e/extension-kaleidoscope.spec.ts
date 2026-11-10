import path from "node:path";
import { expect, test } from "@playwright/test";

type RuntimeListener = (
  message: unknown,
  sender: unknown,
  respond: (response: Record<string, unknown>) => void,
) => void;

test("Kaleidoscope-style application fills safe answers without rules or submission", async ({ page }) => {
  await page.setContent(`
    <main data-platform="kaleidoscope">
      <h1>Scholarship Application</h1>
      <form id="application">
        <label>Legal first name (Required)<input name="legalFirstName" value=""></label>
        <label>Current grade point average (GPA)<input name="currentGpa" type="number" value=""></label>
        <fieldset><legend>Are you currently enrolled full-time?</legend>
          <label><input type="radio" name="fullTime" value="yes"> Yes</label>
          <label><input type="radio" name="fullTime" value="no"> No</label>
        </fieldset>
        <label>Tell us how you embody our company values<textarea name="sponsorEssay"></textarea></label>
        <label><input id="rules" type="checkbox" name="officialRules"> I agree to the official rules</label>
        <button type="submit">Submit application</button>
      </form>
    </main>
    <script>
      window.submitCount = 0;
      document.querySelector('#application').addEventListener('submit', event => {
        event.preventDefault(); window.submitCount += 1;
      });
    </script>
  `);
  await page.evaluate(() => {
    const target = globalThis as typeof globalThis & { pathAidListener?: RuntimeListener; chrome?: unknown };
    target.chrome = { runtime: { onMessage: { addListener(listener: RuntimeListener) { target.pathAidListener = listener; } } } };
  });
  await page.addScriptTag({ path: path.resolve(process.cwd(), "../extension/content/generic-runtime.js") });

  const inspection = await page.evaluate(async () => {
    const target = globalThis as typeof globalThis & { pathAidListener: RuntimeListener };
    return new Promise<Record<string, unknown>>(resolve => target.pathAidListener({ type: "PATHAID_INSPECT_GENERIC" }, {}, resolve));
  });
  const descriptors = inspection.descriptors as Array<Record<string, unknown>>;
  expect(descriptors.every(item => !("value" in item))).toBe(true);
  const byName = Object.fromEntries(descriptors.map(item => [item.name, item]));

  const result = await page.evaluate(async ({ fields }) => {
    const target = globalThis as typeof globalThis & { pathAidListener: RuntimeListener };
    const plan = [
      { fieldId: fields.legalFirstName.fieldId, control: "text", value: "Aidan" },
      { fieldId: fields.currentGpa.fieldId, control: "number", value: 3.8 },
      { fieldId: fields.fullTime.fieldId, control: "radio", value: false },
      // Even an adversarial plan cannot fill the protected rules control.
      { fieldId: fields.officialRules.fieldId, control: "checkbox", value: true },
    ];
    return new Promise<Record<string, unknown>>(resolve => target.pathAidListener({ type: "PATHAID_FILL_GENERIC", plan }, {}, resolve));
  }, { fields: byName });

  expect(result).toEqual({ ok: true, result: { filled: 3, requested: 4 } });
  await expect(page.locator('input[name="legalFirstName"]')).toHaveValue("Aidan");
  await expect(page.locator('input[name="currentGpa"]')).toHaveValue("3.8");
  await expect(page.locator('input[name="fullTime"][value="no"]')).toBeChecked();
  await expect(page.locator('textarea[name="sponsorEssay"]')).toHaveValue("");
  await expect(page.locator("#rules")).not.toBeChecked();
  expect(await page.evaluate(() => (window as typeof window & { submitCount: number }).submitCount)).toBe(0);
});
