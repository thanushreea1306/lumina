/* ============================================================
   LUMINA API Client Foundation
   ============================================================
   Base HTTP client with typed error handling.
   No fake data. No silent fallbacks. Real errors surfaced.
   ============================================================ */

import type { ApiResponse } from '@/types/api';

// ---- Configuration ----
// Canonical API contract:
//   VITE_API_BASE_URL contains the backend ORIGIN WITHOUT the /api prefix
//   (e.g. https://lumina-backend-sw45.onrender.com). Every API module path
//   includes the leading /api prefix (e.g. /api/incidents/...), and the
//   resolved URL is base + path = origin + /api/...
//
//   In development VITE_API_BASE_URL is unset, so the base is empty and the
//   resulting same-origin /api/... path is forwarded by the Vite proxy to
//   the backend (no rewrite, so the /api prefix is preserved).
//
//   IMPORTANT: base must NOT include the /api suffix. Adding it here (with
//   paths that also carry /api) produced /api/api/... and broke HMAC, since
//   the signature is computed over the final request pathname.
//
//   Defense-in-depth: strip a trailing /api suffix if the env var was
//   accidentally set with one (e.g. VITE_API_BASE_URL ending in /api).
//   This prevents the double-/api regression that shipped as a misconfigured
//   Vercel env var and caused production session creation to return 404.
const _rawBase = import.meta.env.VITE_API_BASE_URL || '';
export const DEFAULT_BASE_URL = _rawBase.replace(/\/api\/?$/, '');

// ---- Fetch wrapper ----
async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown;
    headers?: Record<string, string>;
    baseUrl?: string;
  } = {},
): Promise<ApiResponse<T>> {
  const { body, headers = {}, baseUrl = DEFAULT_BASE_URL } = options;

  try {
    const url = `${baseUrl}${path}`;
    const fetchOptions: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      signal: AbortSignal.timeout(15_000),
    };

    if (body !== undefined) {
      fetchOptions.body = JSON.stringify(body);
    }

    const response = await fetch(url, fetchOptions);

    if (!response.ok) {
      let errorDetail: string;
      try {
        const errorBody = await response.json();
        errorDetail = errorBody.detail ?? `HTTP ${response.status}`;
      } catch {
        errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      }

      return {
        ok: false,
        status: response.status,
        error: errorDetail,
      };
    }

    const data: T = await response.json();
    return { ok: true, data };
  } catch (err) {
    // Network failure, timeout, or abort
    const message =
      err instanceof Error ? err.message : 'Network request failed';
    return {
      ok: false,
      status: 0,
      error: message,
    };
  }
}

// ---- Public API ----

export async function apiGet<T>(
  path: string,
  headers?: Record<string, string>,
): Promise<ApiResponse<T>> {
  return request<T>('GET', path, { headers });
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<ApiResponse<T>> {
  return request<T>('POST', path, { body, headers });
}

// ---- Convenience error type guards ----
export function isApiError(result: ApiResponse<unknown>): result is { ok: false; status: number; error: string } {
  return !result.ok;
}

export function isNetworkError(result: ApiResponse<unknown>): boolean {
  return !result.ok && result.status === 0;
}

export function isUnauthorized(result: ApiResponse<unknown>): boolean {
  return !result.ok && result.status === 401;
}

export function isForbidden(result: ApiResponse<unknown>): boolean {
  return !result.ok && result.status === 403;
}

export function isNotFound(result: ApiResponse<unknown>): boolean {
  return !result.ok && result.status === 404;
}
