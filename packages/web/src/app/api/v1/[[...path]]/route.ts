import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL || "http://localhost:8000/api/v1";

async function proxyRequest(request: NextRequest) {
  const url = new URL(request.url);
  // Strip /api/v1 prefix since API_BASE already includes it
  const path = url.pathname.replace(/^\/api\/v1/, "");
  const targetUrl = `${API_BASE}${path}${url.search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.body,
    // @ts-expect-error - duplex is required for streaming body
    duplex: "half",
  });

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
