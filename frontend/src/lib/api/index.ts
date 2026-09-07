export { apiGet, apiPost, isApiError, isNetworkError, isUnauthorized, isForbidden, isNotFound } from './client';
export {
  generateAuthHeaders,
  registerDevice,
  registerAndStoreDevice,
  ensureDeviceIdentity,
  hasStoredCredentials,
  getStoredCredentials,
  storeCredentials,
  clearStoredCredentials,
} from './device';
export type { DeviceCredentials } from './device';
export {
  createSession,
  appendEvent,
  addObservation,
  getSession,
  getDecision,
  recordOutcome,
  userResponse,
} from './sessions';
export {
  sendAlert,
} from './alert';
export type { SendAlertRequest, SendAlertResponse } from './alert';
export {
  createAccount,
  requestPhoneVerification,
  confirmPhoneVerification,
  bindDeviceToAccount,
  setEmergencyConsent,
  requestAccountDeletion,
  deleteAccount,
  getMyAccount,
  getPrivacyPolicy,
  saveTrustedContact,
  getTrustedContact,
} from './account';
export type {
  CreateAccountResponse,
  VerifyPhoneRequestResponse,
  VerifyPhoneConfirmResponse,
  AccountResponse,
  PrivacyPolicy,
  TrustedContactResponse,
  TrustedContactDetail,
  GetTrustedContactResponse,
} from './account';
