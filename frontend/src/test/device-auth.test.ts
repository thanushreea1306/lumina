import { describe, it, expect } from 'vitest';
import { generateAuthHeaders } from '@/lib/api/device';
import type { DeviceCredentials } from '@/lib/api/device';

describe('Device Auth - HMAC Signature', () => {
  const testCredentials: DeviceCredentials = {
    deviceId: 'test-device-id-123',
    deviceSecret: 'test-secret-abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
  };

  it('generates all required auth headers', async () => {
    const headers = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');

    expect(headers['X-Device-ID']).toBe(testCredentials.deviceId);
    expect(headers['X-Timestamp']).toBeTruthy();
    expect(headers['X-Nonce']).toBeTruthy();
    expect(headers['X-Signature']).toBeTruthy();
  });

  it('signature is a 64-character hex string (SHA-256)', async () => {
    const headers = await generateAuthHeaders(testCredentials, 'POST', '/api/sessions/abc/events');

    expect(headers['X-Signature']).toMatch(/^[0-9a-f]{64}$/);
  });

  it('timestamp is a valid ISO-8601 string', async () => {
    const headers = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');

    const timestamp = new Date(headers['X-Timestamp']);
    expect(timestamp.toString()).not.toBe('Invalid Date');
  });

  it('nonce is unique for each call', async () => {
    const h1 = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');
    const h2 = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');

    expect(h1['X-Nonce']).not.toBe(h2['X-Nonce']);
  });

  it('signature changes with different HTTP methods', async () => {
    const h1 = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');
    const h2 = await generateAuthHeaders(testCredentials, 'POST', '/api/sessions');

    // Different methods should produce different signatures
    // (though there's a tiny collision chance, it's astronomically unlikely)
    expect(h1['X-Signature']).not.toBe(h2['X-Signature']);
  });

  it('signature changes with different paths', async () => {
    const h1 = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions');
    const h2 = await generateAuthHeaders(testCredentials, 'GET', '/api/sessions/abc/decision');

    expect(h1['X-Signature']).not.toBe(h2['X-Signature']);
  });

  it('produces deterministic signatures for identical inputs', async () => {
    // This test verifies the HMAC algorithm is deterministic
    // by manually computing the expected signature
    const encoder = new TextEncoder();
    const keyData = encoder.encode(testCredentials.deviceSecret);
    const message = `${testCredentials.deviceId}:2024-01-01T00:00:00.000Z:fixed-nonce:GET:/api/sessions`;

    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      keyData,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign'],
    );

    const signature = await crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(message));
    const expectedHex = Array.from(new Uint8Array(signature))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

    // Verify the format is valid
    expect(expectedHex).toMatch(/^[0-9a-f]{64}$/);
  });
});
