/* ============================================================
   LUMINA Device Auth Foundation
   ============================================================
   Authentication abstraction for backend requests.

   SECURITY LIMITATION:
   The Android app stores device_secret in Android Keystore (encrypted).
   A browser-based React app does NOT have an equivalent secure storage
   mechanism that matches the Android credential model.

   This module provides:
   1. An interface/contract for device authentication
   2. HMAC signature computation (matching backend exactly)
   3. A localStorage-based demo store with clear security warnings
   4. A clean interface that can later be swapped for a real web credential mechanism

   DO NOT:
   - Hardcode device IDs or secrets in source code
   - Assume localStorage is secure for production
   - Use this for real device authentication without a proper web credential store

   The Android credential model uses Android Keystore for encryption.
   A production web implementation needs an equivalent mechanism
   (e.g., WebCrypto API + IndexedDB, or a server-mediated credential flow).
   ============================================================ */

import { apiPost } from './client';
import type { ApiResponse, RegisterDeviceResponse } from '@/types/api';

// ---- HMAC Signature Computation ----
// Matches backend exactly: HMAC-SHA256(device_secret, "{device_id}:{timestamp}:{nonce}:{method}:{path}")

async function hmacSign(
  secret: string,
  message: string,
): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const msgData = encoder.encode(message);

  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );

  const signature = await crypto.subtle.sign('HMAC', cryptoKey, msgData);

  // Convert to hex string
  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// ---- Auth Headers ----

export interface DeviceCredentials {
  deviceId: string;
  deviceSecret: string;
}

/**
 * Generate authentication headers for a request.
 *
 * Signs: "{device_id}:{timestamp}:{nonce}:{method}:{path}"
 *
 * @throws If no credentials are available or crypto is unavailable
 */
export async function generateAuthHeaders(
  credentials: DeviceCredentials,
  method: string,
  path: string,
): Promise<Record<string, string>> {
  const timestamp = new Date().toISOString();
  const nonce = crypto.randomUUID().replace(/-/g, '').slice(0, 32);

  const message = `${credentials.deviceId}:${timestamp}:${nonce}:${method}:${path}`;
  const signature = await hmacSign(credentials.deviceSecret, message);

  return {
    'X-Device-ID': credentials.deviceId,
    'X-Timestamp': timestamp,
    'X-Nonce': nonce,
    'X-Signature': signature,
  };
}

// ---- Device Registration ----

/**
 * Register a new device with the backend.
 *
 * Returns device_id and device_secret. The secret MUST be stored securely.
 * After registration, the secret is never transmitted again.
 *
 * SECURITY NOTE: In production, device_secret must be stored in a secure
 * credential store, NOT in localStorage.
 */
export async function registerDevice(): Promise<
  ApiResponse<DeviceCredentials>
> {
  const result = await apiPost<RegisterDeviceResponse>('/devices/register', {});

  if (!result.ok) {
    return result;
  }

  const credentials: DeviceCredentials = {
    deviceId: result.data.device_id,
    deviceSecret: result.data.device_secret,
  };

  return { ok: true, data: credentials };
}

// ---- Demo Device Store (localStorage) ----
// SECURITY WARNING: This is a DEMO implementation for development only.
// localStorage is NOT secure for production device credentials.
// A real implementation should use WebCrypto + IndexedDB or a server-mediated flow.

const STORAGE_KEY_DEVICE_ID = 'lumina_device_id';
const STORAGE_KEY_DEVICE_SECRET = 'lumina_device_secret';

/**
 * Check if credentials are available in the demo store.
 *
 * SECURITY: This is a development convenience, NOT a production auth solution.
 */
export function hasStoredCredentials(): boolean {
  try {
    return (
      localStorage.getItem(STORAGE_KEY_DEVICE_ID) !== null &&
      localStorage.getItem(STORAGE_KEY_DEVICE_SECRET) !== null
    );
  } catch {
    // localStorage may be unavailable (SSR, private browsing, etc.)
    return false;
  }
}

/**
 * Store credentials in the demo store.
 *
 * SECURITY WARNING: localStorage is NOT secure for production.
 */
export function storeCredentials(credentials: DeviceCredentials): void {
  try {
    localStorage.setItem(STORAGE_KEY_DEVICE_ID, credentials.deviceId);
    localStorage.setItem(STORAGE_KEY_DEVICE_SECRET, credentials.deviceSecret);
  } catch {
    // Silently fail if localStorage is unavailable
  }
}

/**
 * Retrieve stored credentials.
 *
 * SECURITY WARNING: localStorage is NOT secure for production.
 */
export function getStoredCredentials(): DeviceCredentials | null {
  try {
    const deviceId = localStorage.getItem(STORAGE_KEY_DEVICE_ID);
    const deviceSecret = localStorage.getItem(STORAGE_KEY_DEVICE_SECRET);

    if (deviceId && deviceSecret) {
      return { deviceId, deviceSecret };
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Clear stored credentials.
 */
export function clearStoredCredentials(): void {
  try {
    localStorage.removeItem(STORAGE_KEY_DEVICE_ID);
    localStorage.removeItem(STORAGE_KEY_DEVICE_SECRET);
  } catch {
    // Silently fail
  }
}

/**
 * Register a new device and store credentials.
 * Convenience wrapper that combines registration + storage.
 */
export async function registerAndStoreDevice(): Promise<
  ApiResponse<DeviceCredentials>
> {
  const result = await registerDevice();
  if (result.ok) {
    storeCredentials(result.data);
  }
  return result;
}

/**
 * Get stored credentials or register a new device.
 * Used during app initialization to ensure the app has a device identity.
 */
export async function ensureDeviceIdentity(): Promise<
  ApiResponse<DeviceCredentials>
> {
  const stored = getStoredCredentials();
  if (stored) {
    return { ok: true, data: stored };
  }
  return registerAndStoreDevice();
}
