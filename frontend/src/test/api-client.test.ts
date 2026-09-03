import { describe, it, expect } from 'vitest';
import {
  isApiError,
  isNetworkError,
  isUnauthorized,
  isForbidden,
  isNotFound,
} from '@/lib/api/client';
import type { ApiResponse } from '@/types/api';

describe('API error type guards', () => {
  const successResult: ApiResponse<string> = { ok: true, data: 'hello' };
  const unauthorizedResult: ApiResponse<string> = { ok: false, status: 401, error: 'Unauthorized' };
  const forbiddenResult: ApiResponse<string> = { ok: false, status: 403, error: 'Forbidden' };
  const notFoundResult: ApiResponse<string> = { ok: false, status: 404, error: 'Not found' };
  const networkResult: ApiResponse<string> = { ok: false, status: 0, error: 'Network error' };
  const serverError: ApiResponse<string> = { ok: false, status: 500, error: 'Internal server error' };

  describe('isApiError', () => {
    it('returns false for successful responses', () => {
      expect(isApiError(successResult)).toBe(false);
    });

    it('returns true for failed responses', () => {
      expect(isApiError(unauthorizedResult)).toBe(true);
      expect(isApiError(forbiddenResult)).toBe(true);
      expect(isApiError(notFoundResult)).toBe(true);
      expect(isApiError(networkResult)).toBe(true);
      expect(isApiError(serverError)).toBe(true);
    });
  });

  describe('isNetworkError', () => {
    it('returns true only for status 0', () => {
      expect(isNetworkError(networkResult)).toBe(true);
      expect(isNetworkError(unauthorizedResult)).toBe(false);
      expect(isNetworkError(successResult)).toBe(false);
    });
  });

  describe('isUnauthorized', () => {
    it('returns true only for status 401', () => {
      expect(isUnauthorized(unauthorizedResult)).toBe(true);
      expect(isUnauthorized(forbiddenResult)).toBe(false);
      expect(isUnauthorized(successResult)).toBe(false);
    });
  });

  describe('isForbidden', () => {
    it('returns true only for status 403', () => {
      expect(isForbidden(forbiddenResult)).toBe(true);
      expect(isForbidden(unauthorizedResult)).toBe(false);
      expect(isForbidden(successResult)).toBe(false);
    });
  });

  describe('isNotFound', () => {
    it('returns true only for status 404', () => {
      expect(isNotFound(notFoundResult)).toBe(true);
      expect(isNotFound(unauthorizedResult)).toBe(false);
      expect(isNotFound(successResult)).toBe(false);
    });
  });
});
