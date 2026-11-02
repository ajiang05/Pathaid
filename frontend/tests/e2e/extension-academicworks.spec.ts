import path from "node:path";
import { expect, test } from "@playwright/test";

type RuntimeListener = (
  message: unknown,
  sender: unknown,
  respond: (response: Record<string, unknown>) => void,
) => void;

test("AcademicWorks-style application fills reviewed answers without certification or submission", async ({ page }) => {
  await page.setContent(`
    <main data-portal="blackbaud-award-management">
      <h1>General Application</h1>
      <form id="general-application">
        <label>What is your current cumulative GPA? (Required)
          <input name="answers[academic_gpa]" type="number" value="">
        </label>
        <fieldset><legend>Are you currently enrolled full-time? (Required)</legend>
          <label><input type="radio" name="answers[full_time]" value="yes"> Yes</label>
          <label><input type="radio" name="answers[full_time]" value="no"> No</label>
        </fieldset>
        <label>Are you a U.S. citizen or permanent resident?
          <select name="answers[citizenship]"><option value="">Choose</option><option value="yes">Yes</option><option value="no">No</option></select>
        </label>
        <label>Describe how this award will change your life
          <textarea name="answers[essay]"></textarea>
        </label>
        <label><input id="certify" type="checkbox" name="certification"> I certify that my answers are true</label>
        <button type="submit">Finish and Submit</button>
      </form>
    </main>
    <script>
      window.submitCount = 0;
      document.querySelector('#general-application').addEventListener('submit', event => {
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
      { fieldId: fields["answers[academic_gpa]"].fieldId, control: "number", value: 3.8 },
      { fieldId: fields["answers[full_time]"].fieldId, control: "radio", value: true },
      { fieldId: fields["answers[citizenship]"].fieldId, control: "select", value: true },
      // An adversarial plan entry still cannot cross the runtime safety boundary.
      { fieldId: fields.certification.fieldId, control: "checkbox", value: true },
    ];
    return new Promise<Record<string, unknown>>(resolve => target.pathAidListener({ type: "PATHAID_FILL_GENERIC", plan }, {}, resolve));
  }, { fields: byName });

  expect(result).toEqual({ ok: true, result: { filled: 3, requested: 4 } });
  await expect(page.locator('input[name="answers[academic_gpa]"]')).toHaveValue("3.8");
  await expect(page.locator('input[name="answers[full_time]"][value="yes"]')).toBeChecked();
  await expect(page.locator('select[name="answers[citizenship]"]')).toHaveValue("yes");
  await expect(page.locator('textarea[name="answers[essay]"]')).toHaveValue("");
  await expect(page.locator("#certify")).not.toBeChecked();
  expect(await page.evaluate(() => (window as typeof window & { submitCount: number }).submitCount)).toBe(0);
});
