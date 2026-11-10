import assert from "node:assert/strict";
import test from "node:test";
import { webcrypto } from "node:crypto";
import { formSignatures } from "../lib/form-signatures.js";

globalThis.crypto ??= webcrypto;

test("form signatures are deterministic and exclude current values", async () => {
  const descriptors = [
    { control: "text", label: " First Name ", name: "given_name", required: true, value: "should-not-matter" },
    { control: "number", label: "GPA", name: "gpa", required: false },
  ];
  const first = await formSignatures(descriptors);
  const second = await formSignatures([{ ...descriptors[0], label: "first-name", value: "different" }, descriptors[1]]);
  assert.deepEqual(first, second);
  assert.match(first.formSignature, /^[a-f0-9]{64}$/);
  assert.equal(first.fieldSignatures.length, 2);
  assert.notEqual(first.fieldSignatures[0], first.fieldSignatures[1]);
});

test("form shape changes invalidate learned mapping scope", async () => {
  const one = await formSignatures([{ control: "text", label: "First name", name: "first" }]);
  const two = await formSignatures([{ control: "text", label: "Email", name: "email" }]);
  assert.notEqual(one.formSignature, two.formSignature);
});
