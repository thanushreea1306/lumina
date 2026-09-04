/* ============================================================
   API path / HMAC contract regression test (CP-07).
   ============================================================
   Guarantees the canonical URL contract:
     - base = VITE_API_BASE_URL (origin WITHOUT /api), empty in tests
     - module paths carry the leading /api prefix
     - resolved fetch URL NEVER becomes /api/api/...
     - the path passed to generateAuthHeaders (HMAC-signed) equals the
       final pathname actually sent to fetch.

   This test inspects the real fetch() URL (not a wrapper), so it would
   have caught the CP-07 double-/api prefix bug.
   ============================================================ */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as incidents from '@/lib/api/incidents';
import * as sessions from '@/lib/api/sessions';
import type { DeviceCredentials } from '@/lib/api/device';

// Hoisted helpers accessible from the vi.mock factory and the tests.
const { authPaths, fetchUrls } = vi.hoisted(() => ({
  authPaths: [] as string[],
  fetchUrls: [] as string[],
}));

// Mock the device module so we can record exactly which path each call
// signs. The real base-resolution logic in client.ts / incidents.ts is
// left intact (VITE_API_BASE_URL is unset in tests, so the base is empty).
vi.mock('@/lib/api/device', () => ({
  generateAuthHeaders: async (
    _c: DeviceCredentials,
    _m: string,
    path: string,
  ) => {
    authPaths.push(path);
    return {
      'X-Device-ID': 'test-device-id-123',
      'X-Timestamp': '2024-01-01T00:00:00.000Z',
      'X-Nonce': 'fixed-test-nonce-00000000000000000000000000000000',
      'X-Signature': '00'.repeat(32),
    };
  },
}));

function pathnameOf(url: string): string {
  // Relative paths (dev, empty base) resolve against a throwaway origin.
  return new URL(url, 'http://lumina.test').pathname;
}

describe('API URL pathname + HMAC consistency (CP-07 regression)', () => {
  const creds: DeviceCredentials = {
    deviceId: 'test-device-id-123',
    deviceSecret: 'x'.repeat(64),
  };

  beforeEach(() => {
    authPaths.length = 0;
    fetchUrls.length = 0;

    // Capture every fetch() URL that the API modules issue.
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      fetchUrls.push(String(input));
      return new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  function expectConsistent(
    fetchUrl: string,
    authPath: string | undefined,
    expectedPathname: string,
  ): void {
    const sentPathname = pathnameOf(fetchUrl);
    // The contract: never a duplicated prefix.
    expect(sentPathname).toBe(expectedPathname);
    expect(sentPathname).not.toMatch(/\/api\/api/);
    expect(authPath).toBeDefined();
    // HMAC must be computed over the exact final pathname actually sent.
    expect(authPath).toBe(sentPathname);
  }

  it('createIncident builds /api/incidents and signs the same path', async () => {
    await incidents.createIncident(creds);
    expect(fetchUrls).toHaveLength(1);
    expectConsistent(fetchUrls[0], authPaths[0], '/api/incidents');
  });

  it('addTranscript builds /api/incidents/:id/transcript and signs it', async () => {
    const req = { text: 'hello', speaker: 'scammer' };
    await incidents.addIncidentTranscript(creds, 'inc-1', req as never);
    expect(fetchUrls).toHaveLength(1);
    expectConsistent(
      fetchUrls[0],
      authPaths[0],
      '/api/incidents/inc-1/transcript',
    );
  });

  it('uploadIncidentAudio builds /api/incidents/:id/audio (multipart) and signs it', async () => {
    const file = new File(['audio-bytes'], 'call.wav', { type: 'audio/wav' });
    await incidents.uploadIncidentAudio(creds, 'inc-1', file);
    expect(fetchUrls).toHaveLength(1);
    expectConsistent(fetchUrls[0], authPaths[0], '/api/incidents/inc-1/audio');
  });

  it('createSession builds /api/sessions and signs the same path', async () => {
    await sessions.createSession(creds);
    expect(fetchUrls).toHaveLength(1);
    expectConsistent(fetchUrls[0], authPaths[0], '/api/sessions');
  });

  it('getSession builds /api/sessions/:id and signs the same path', async () => {
    await sessions.getSession(creds, 'sess-1');
    expect(fetchUrls).toHaveLength(1);
    expectConsistent(fetchUrls[0], authPaths[0], '/api/sessions/sess-1');
  });

  it('listIncidents signs the pathname, not the ?limit query', async () => {
    await incidents.listIncidents(creds, 25);
    expect(fetchUrls).toHaveLength(1);
    const sentPathname = pathnameOf(fetchUrls[0]);
    // URL keeps the query, HMAC is computed over the bare pathname.
    expect(sentPathname).toBe('/api/incidents');
    expect(fetchUrls[0]).toContain('?limit=25');
    expect(authPaths[0]).toBe('/api/incidents');
    expect(authPaths[0]).toBe(sentPathname);
    expect(authPaths[0]).not.toMatch(/\/api\/api/);
  });
});

describe('DEFAULT_BASE_URL normalization (VITE_API_BASE_URL /api suffix guard)', () => {
  // Reproduce the exact normalization logic from client.ts.
  // import.meta.env is resolved at Vite build time, so we test the
  // regex directly to verify it strips trailing /api as expected.
  const normalize = (raw: string) => raw.replace(/\/api\/?$/, '');

  it('strips trailing /api from a misconfigured env var', () => {
    // This is the exact production misconfiguration: VITE_API_BASE_URL
    // was set to "https://lumina-backend-sw45.onrender.com/api"
    const result = normalize('https://lumina-backend-sw45.onrender.com/api');
    expect(result).toBe('https://lumina-backend-sw45.onrender.com');
    expect(result).not.toMatch(/\/api$/);
  });

  it('strips trailing /api/ (with trailing slash)', () => {
    const result = normalize('https://lumina-backend-sw45.onrender.com/api/');
    expect(result).toBe('https://lumina-backend-sw45.onrender.com');
  });

  it('leaves a correct base URL unchanged', () => {
    const result = normalize('https://lumina-backend-sw45.onrender.com');
    expect(result).toBe('https://lumina-backend-sw45.onrender.com');
  });

  it('empty string stays empty (dev mode)', () => {
    const result = normalize('');
    expect(result).toBe('');
  });

  it('URL with /api in path but not as suffix is untouched', () => {
    const result = normalize('https://api.example.com');
    expect(result).toBe('https://api.example.com');
  });
});
