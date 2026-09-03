/* ============================================================
   LUMINA API Client Foundation
   ============================================================
   Base HTTP client with typed error handling.
   No fake data. No silent fallbacks. Real errors surfaced.
   ============================================================ */

import type { ApiResponse } from '@/types/api';

// ---- Configuration ----
const DEFAULT_BASE_URL = '/api';

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
