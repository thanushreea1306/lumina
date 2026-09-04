/* ============================================================
   LUMINA Help Request API Client
   ============================================================
   Client-side API for the "I'M TRAPPED — GET HELP" feature.

   When the victim presses the help button, this sends an
   authenticated request to the backend which:
   1. Records a HELP_REQUESTED timeline entry
   2. Generates a Help Story from incident evidence
   3. Returns the Help Story for trusted contact delivery
   ============================================================ */

import { DEFAULT_BASE_URL } from './client';
import { generateAuthHeaders, ensureDeviceIdentity } from './device';
import type { HelpRequestResponse } from '@/types/incident';

async function authHeaders(method: string, path: string): Promise<Record<string, string>> {
  const creds = await ensureDeviceIdentity();
  if (!creds.ok) throw new Error('Device authentication required');
  return generateAuthHeaders(creds.data, method, path);
}

/**
 * Request help — the victim presses "I'M TRAPPED — GET HELP".
 *
 * This is an authenticated, owner-bound, idempotent request.
 * The same request does not create duplicate evidence.
 */
export async function requestHelp(
  incidentId: string,
  reason?: string,
): Promise<HelpRequestResponse> {
  const path = `/api/incidents/${incidentId}/help-request`;
  const method = 'POST';
  const headers = await authHeaders(method, path);

  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reason: reason || 'Victim pressed I\'M TRAPPED — GET HELP',
      send_to_trusted_contact: true,
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Help request failed (${response.status}): ${detail}`);
  }

  return response.json();
}
