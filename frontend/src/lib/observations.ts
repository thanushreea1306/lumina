/* ============================================================
   LUMINA Observation Types
   ============================================================
   Maps backend UserObservationType values to human-readable
   labels and descriptions for the safety check UI.
   ============================================================ */

import type { UserObservationType } from '@/types/safety';

export interface ObservationOption {
  type: UserObservationType;
  label: string;
  description: string;
  /** Human-readable prompt for what the user observed */
  prompt: string;
  /** Semantic color category */
  category: 'coercion' | 'financial' | 'access' | 'urgency' | 'other';
}

export const OBSERVATION_OPTIONS: ObservationOption[] = [
  {
    type: 'AUTHORITY_CLAIM',
    label: 'Authority Claim',
    description: 'The caller claimed to be from a government agency, bank, or authority',
    prompt: 'They claimed to be from an authority',
    category: 'coercion',
  },
  {
    type: 'THREAT_OF_ARREST',
    label: 'Threat of Arrest',
    description: 'The caller threatened arrest or legal detention',
    prompt: 'They threatened me with arrest',
    category: 'coercion',
  },
  {
    type: 'THREAT_OF_LEGAL_ACTION',
    label: 'Threat of Legal Action',
    description: 'The caller threatened legal consequences',
    prompt: 'They threatened legal action',
    category: 'coercion',
  },
  {
    type: 'URGENCY',
    label: 'Urgency',
    description: 'The caller pressured for immediate action',
    prompt: 'They pressured me to act immediately',
    category: 'urgency',
  },
  {
    type: 'SECRECY_REQUEST',
    label: 'Secrecy Request',
    description: 'The caller asked to keep the matter secret',
    prompt: 'They asked me to keep this secret',
    category: 'coercion',
  },
  {
    type: 'INDEPENDENT_VERIFICATION_BLOCKED',
    label: 'Verification Blocked',
    description: 'The caller prevented independent verification',
    prompt: 'They prevented me from verifying independently',
    category: 'coercion',
  },
  {
    type: 'MONEY_REQUEST',
    label: 'Money Request',
    description: 'The caller asked for money or a transfer',
    prompt: 'They asked me for money',
    category: 'financial',
  },
  {
    type: 'BANK_TRANSFER_REQUEST',
    label: 'Bank Transfer',
    description: 'The caller requested a bank transfer',
    prompt: 'They asked me to make a bank transfer',
    category: 'financial',
  },
  {
    type: 'OTP_REQUEST',
    label: 'OTP / Code Request',
    description: 'The caller asked for a one-time password or verification code',
    prompt: 'They asked me for an OTP or code',
    category: 'access',
  },
  {
    type: 'PASSWORD_REQUEST',
    label: 'Password Request',
    description: 'The caller asked for a password',
    prompt: 'They asked me for a password',
    category: 'access',
  },
  {
    type: 'REMOTE_ACCESS_REQUEST',
    label: 'Remote Access Request',
    description: 'The caller asked to install remote access software',
    prompt: 'They asked me to install remote access software',
    category: 'access',
  },
  {
    type: 'APP_INSTALL_REQUEST',
    label: 'App Install Request',
    description: 'The caller asked to install an app',
    prompt: 'They asked me to install an app',
    category: 'access',
  },
  {
    type: 'IDENTITY_DOCUMENT_REQUEST',
    label: 'ID Document Request',
    description: 'The caller asked for identity documents',
    prompt: 'They asked me for identity documents',
    category: 'access',
  },
  {
    type: 'CRYPTO_REQUEST',
    label: 'Crypto Transfer',
    description: 'The caller asked for cryptocurrency transfer',
    prompt: 'They asked me to transfer cryptocurrency',
    category: 'financial',
  },
  {
    type: 'GIFT_CARD_REQUEST',
    label: 'Gift Card Request',
    description: 'The caller asked for gift card purchase',
    prompt: 'They asked me to buy gift cards',
    category: 'financial',
  },
  {
    type: 'CALL_BACK_INSTRUCTION',
    label: 'Callback Instruction',
    description: 'The caller instructed to call back on a specific number',
    prompt: 'They told me to call a specific number back',
    category: 'other',
  },
];

export const CATEGORY_COLORS: Record<string, string> = {
  coercion: 'var(--lumina-danger)',
  financial: 'var(--lumina-warning)',
  access: 'var(--lumina-investigation)',
  urgency: 'var(--lumina-action)',
  other: 'var(--lumina-system)',
};

export const CATEGORY_LABELS: Record<string, string> = {
  coercion: 'Coercion / Threats',
  financial: 'Financial',
  access: 'Access / Credentials',
  urgency: 'Pressure / Urgency',
  other: 'Other',
};
