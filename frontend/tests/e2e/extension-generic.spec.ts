import path from "node:path";
import { expect, test } from "@playwright/test";

test("generic extension runtime fills only approved safe fields and never submits", async ({ page }) => {
  await page.setContent(`
    <form id="application">
      <label>First name <input name="first_name" autocomplete="given-name" value=""></label>
      <label>Email address <input name="email" type="email" value=""></label>
      <fieldset><legend>Enrollment status</legend>
        <label><input type="radio" name="enrollment" value="full_time"> Full-time</label>
        <label><input type="radio" name="enrollment" value="part_time"> Part-time</label>
      </fieldset>
      <label>Citizenship status <select name="citizenship"><option value="">Choose</option><option value="us_citizen">U.S. citizen</option></select></label>
      <label><input id="certify" type="checkbox" name="certify"> I certify this application is true</label>
      <input type="hidden" name="anti_bot" value="leave-empty">
      <button type="submit">Submit application</button>
    </form>
    <script>window.submitCount = 0; document.querySelector('#application').addEventListener('submit', event => { event.preventDefault(); window.submitCount += 1; });</script>
  `);
  await page.evaluate(() => {
    const target = globalThis as typeof globalThis & { pathAidListener?: Function; chrome?: unknown };
    target.chrome = { runtime: { onMessage: { addListener(listener: Function) { target.pathAidListener = listener; } } } };
  });
  await page.addScriptTag({ path: path.resolve(process.cwd(), "../extension/content/generic-runtime.js") });

  const inspection = await page.evaluate(async () => {
    const target = globalThis as typeof globalThis & { pathAidListener: Function };
    return new Promise<Record<string, unknown>>(resolve => target.pathAidListener({ type: "PATHAID_INSPECT_GENERIC" }, {}, resolve));
  });
  expect(inspection.ok).toBe(true);
  const descriptors = inspection.descriptors as Array<Record<string, unknown>>;
  expect(descriptors.every(item => !("value" in item))).toBe(true);
  const byName = Object.fromEntries(descriptors.map(item => [item.name, item]));

  const fillResult = await page.evaluate(async ({ descriptorsByName }) => {
    const target = globalThis as typeof globalThis & { pathAidListener: Function };
    const plan = [
      { fieldId: descriptorsByName.first_name.fieldId, control: "text", value: "Aidan" },
      { fieldId: descriptorsByName.email.fieldId, control: "email", value: "aidan@example.com" },
      { fieldId: descriptorsByName.enrollment.fieldId, control: "radio", value: "full_time" },
      { fieldId: descriptorsByName.citizenship.fieldId, control: "select", value: "us_citizen" },
      { fieldId: descriptorsByName.certify.fieldId, control: "checkbox", value: true },
    ];
    return new Promise<Record<string, unknown>>(resolve => target.pathAidListener({ type: "PATHAID_FILL_GENERIC", plan }, {}, resolve));
  }, { descriptorsByName: byName });

  expect(fillResult).toEqual({ ok: true, result: { filled: 4, requested: 5 } });
  await expect(page.locator('input[name="first_name"]')).toHaveValue("Aidan");
  await expect(page.locator('input[name="email"]')).toHaveValue("aidan@example.com");
  await expect(page.locator('input[value="full_time"]')).toBeChecked();
  await expect(page.locator('select[name="citizenship"]')).toHaveValue("us_citizen");
  await expect(page.locator("#certify")).not.toBeChecked();
  expect(await page.evaluate(() => (window as typeof window & { submitCount: number }).submitCount)).toBe(0);
});
