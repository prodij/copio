export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

export function toApiError(response: Response, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(response.status, detail);
  if (Array.isArray(detail)) {
    return new ApiError(response.status, detail.map((d) => (d as { msg?: string }).msg ?? "invalid").join("; "));
  }
  return new ApiError(response.status, response.statusText || "Request failed");
}
