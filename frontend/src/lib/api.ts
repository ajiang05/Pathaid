export class ApiError extends Error {
  constructor(public status:number, message:string, public field?:string) { super(message); }
}

export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response = await fetch(path, { credentials:"same-origin", ...init });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message ?? "The request could not be completed.";
    throw new ApiError(response.status, message, detail?.field);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function readable(value:string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function dateLabel(value:string|null) {
  if (!value) return "Not verified";
  return new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", timeZone:"UTC" }).format(new Date(value));
}
