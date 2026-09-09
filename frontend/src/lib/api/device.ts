/* ============================================================
   LUMINA Device Auth Foundation
   ============================================================
   Authentication abstraction for backend requests.

   SECURITY MODEL:
   The Android app stores device_secret in Android Keystore (encrypted).
   A browser-based React app does NOT have an equivalent secure storage
   mechanism that matches the Android credential model, so the web product
   persists its device credentials in localStorage.

   This module provides:
   1. An interface/contract for device authentication
   2. HMAC signature computation (matching backend exactly)
   3. localStorage-based credential persistence (the web product's actual
      device identity store)
   4. A clean interface that can later be swapped for a stronger web
      credential mechanism (e.g., WebCrypto + IndexedDB)

   SECURITY LIMITATION (stated honestly, not hidden):
   - localStorage is not a hardened credential store: it is readable by
     scripts from the same origin and can be exfiltrated by an XSS. This is a
     browser-platform limitation, distinct from Android Keystore.
   - The backend treats the device secret as a shared secret; anyone holding it
     can act as the device. The web store should be treated accordingly.
   - A production web implementation needs a stronger mechanism; the interface
     below is intentionally small so the storage backend can be swapped.

   DO NOT:
   - Hardcode device IDs or secrets in source code
   - Assume localStorage is equivalent to Android Keystore security
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
  const result = await apiPost<RegisterDeviceResponse>('/api/devices/register', {});

  if (!result.ok) {
    return result;
  }

  const credentials: DeviceCredentials = {
    deviceId: result.data.device_id,
    deviceSecret: result.data.device_secret,
  };

  return { ok: true, data: credentials };
}

// ---- Web Device Credential Store (localStorage) ----
// The React web product's device identity store. localStorage is more
// accessible to same-origin scripts than Android Keystore — this is a stated
// browser-platform limitation, and the store interface is small so a stronger
// backing store (WebCrypto + IndexedDB) can replace it without touching the
// API layer.

const STORAGE_KEY_DEVICE_ID = 'lumina_device_id';
const STORAGE_KEY_DEVICE_SECRET = 'lumina_device_secret';

/**
 * Check if credentials are available in the web credential store.
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
 * Store credentials in the web credential store.
 *
 * LIMITATION: localStorage is not equivalent to Android Keystore; anyone with
 * script access to this origin can read these values.
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
