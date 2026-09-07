/* ============================================================
   LUMINA Account API Client
   ============================================================
   Authenticated API calls for account creation, phone
   verification, device binding, and account deletion.

   Every call is honest: real backend responses, real errors,
   no simulated timeouts, no fabricated data.
   ============================================================ */

import { apiGet, apiPost } from './client';
import { generateAuthHeaders, ensureDeviceIdentity } from './device';

async function authHeaders(method: string, path: string): Promise<Record<string, string>> {
  const creds = await ensureDeviceIdentity();
  if (!creds.ok) throw new Error('Device authentication required');
  return generateAuthHeaders(creds.data, method, path);
}

// ---- Types ----

export interface CreateAccountResponse {
  status: string;
  message: string;
}

export interface VerifyPhoneRequestResponse {
  verification_id: string;
  status: string;
  delivery_status: string;
  delivery_message: string;
  expires_at: string | null;
}

export interface VerifyPhoneConfirmResponse {
  verified: boolean;
  user_id: string;
  phone_masked: string;
}

export interface BindDeviceResponse {
  status: string;
  message: string;
}

export interface AccountResponse {
  user_id: string;
  display_name: string;
  phone_masked: string;
  phone_verified: boolean;
  emergency_consent: string;
  account_status: string;
  created_at: string;
}

export interface PrivacyPolicy {
  retention_policy: Record<string, unknown>;
  retention_enforcement: string;
  summary: {
    what_lumina_stores: string[];
    what_lumina_does_not_store: string[];
    what_is_shared: string[];
    ai_data_boundary: string;
  };
}

export interface TrustedContactResponse {
  contact_id: string;
  display_name: string;
  delivery_channel: string;
  destination_masked: string;
  is_configured: boolean;
  automatic_help_enabled: boolean;
}

export interface TrustedContactDetail {
  contact_id: string;
  display_name: string;
  delivery_channel: string;
  enabled: boolean;
  automatic_help_enabled: boolean;
  configured_at: string;
  updated_at: string;
  destination_masked?: string;
}

export interface GetTrustedContactResponse {
  configured: boolean;
  contact: TrustedContactDetail | null;
}

// ---- Account ----

export async function createAccount(
  displayName: string,
  phoneNumber: string,
): Promise<CreateAccountResponse> {
  const path = '/api/account';
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<CreateAccountResponse>(
    path,
    { display_name: displayName, phone_number: phoneNumber },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Phone Verification ----

export async function requestPhoneVerification(
  phoneNumber: string,
): Promise<VerifyPhoneRequestResponse> {
  const path = '/api/account/verify-phone/request';
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<VerifyPhoneRequestResponse>(
    path,
    { phone_number: phoneNumber },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export async function confirmPhoneVerification(
  verificationId: string,
  otp: string,
): Promise<VerifyPhoneConfirmResponse> {
  const path = '/api/account/verify-phone/confirm';
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<VerifyPhoneConfirmResponse>(
    path,
    { verification_id: verificationId, otp },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Device Binding ----

export async function bindDeviceToAccount(
  userId: string,
  deviceId: string,
  deviceLabel: string = '',
): Promise<BindDeviceResponse> {
  const path = '/api/account/bind-device';
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<BindDeviceResponse>(
    path,
    { user_id: userId, device_id: deviceId, device_label: deviceLabel },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Emergency Consent ----

export async function setEmergencyConsent(
  userId: string,
  consent: boolean,
): Promise<{ status: string; consent: string }> {
  const path = `/api/account/${userId}/emergency-consent`;
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<{ status: string; consent: string }>(
    path,
    { consent },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Account Deletion ----

export async function requestAccountDeletion(
  userId: string,
): Promise<{ status: string }> {
  const path = `/api/account/${userId}/deletion-request`;
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<{ status: string }>(path, undefined, headers);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export async function deleteAccount(userId: string): Promise<{ status: string }> {
  const path = `/api/account/${userId}/delete`;
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<{ status: string }>(path, undefined, headers);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Account Info ----

export async function getMyAccount(): Promise<AccountResponse> {
  const path = '/api/account/me';
  const method = 'GET';
  const headers = await authHeaders(method, path);
  const result = await apiGet<AccountResponse>(path, headers);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Privacy Policy (public) ----

export async function getPrivacyPolicy(): Promise<PrivacyPolicy> {
  const result = await apiGet<PrivacyPolicy>('/api/privacy/policy');
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

// ---- Trusted Contact ----

export async function saveTrustedContact(data: {
  display_name: string;
  delivery_channel: 'SMS' | 'EMAIL' | 'NONE';
  destination: string;
  phone_number?: string;
  automatic_help_enabled?: boolean;
}): Promise<TrustedContactResponse> {
  const path = '/api/trusted-contact';
  const method = 'POST';
  const headers = await authHeaders(method, path);
  const result = await apiPost<TrustedContactResponse>(
    path,
    {
      ...data,
      automatic_help_enabled: data.automatic_help_enabled ?? false,
    },
    headers,
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

/**
 * Read the currently configured trusted contact.
 *
 * Reads the existing GET /api/trusted-contact endpoint (no contract change).
 * The backend redacts the destination when producing `destination_masked`,
 * so the client never receives an unmasked number or address.
 */
export async function getTrustedContact(): Promise<GetTrustedContactResponse> {
  const path = '/api/trusted-contact';
  const method = 'GET';
  const headers = await authHeaders(method, path);
  const result = await apiGet<GetTrustedContactResponse>(path, headers);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}
