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
