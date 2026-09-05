import { useState, useRef, useEffect, useCallback } from 'react';
import type { RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import {
  createAccount,
  requestPhoneVerification,
  confirmPhoneVerification,
  saveTrustedContact,
  setEmergencyConsent,
} from '@/lib/api/account';

type OnboardingStep = 'welcome' | 'account' | 'phone' | 'verify' | 'device' | 'trusted-contact' | 'consent' | 'ready';

const STEP_ORDER: OnboardingStep[] = ['welcome', 'account', 'phone', 'verify', 'device', 'trusted-contact', 'consent', 'ready'];

interface AccountData {
  displayName: string;
  phoneNumber: string;
}

interface TrustedContactData {
  name: string;
  phone: string;
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<OnboardingStep>('welcome');
  const [account, setAccount] = useState<AccountData>({ displayName: '', phoneNumber: '' });
  const [trustedContact, setTrustedContact] = useState<TrustedContactData>({ name: '', phone: '' });
  const [emergencyConsent, setEmergencyConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [verificationId, setVerificationId] = useState('');
  const [userId, setUserId] = useState('');
  const [deliveryStatus, setDeliveryStatus] = useState('');
  const [deliveryMessage, setDeliveryMessage] = useState('');
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);

  const focusStepHeading = useCallback(() => {
    requestAnimationFrame(() => {
      stepHeadingRef.current?.focus();
    });
  }, []);

  useEffect(() => {
    focusStepHeading();
  }, [step, focusStepHeading]);

  const goToStep = useCallback((next: OnboardingStep) => {
    setStep(next);
  }, []);

  const renderStep = () => {
    switch (step) {
      case 'welcome':
        return <WelcomeStep headingRef={stepHeadingRef} onNext={() => goToStep('account')} />;
      case 'account':
        return (
          <AccountStep
            headingRef={stepHeadingRef}
            account={account}
            onChange={setAccount}
            onNext={() => goToStep('phone')}
            onBack={() => goToStep('welcome')}
          />
        );
      case 'phone':
        return (
          <PhoneStep
            headingRef={stepHeadingRef}
            displayName={account.displayName}
            phoneNumber={account.phoneNumber}
            deliveryStatus={deliveryStatus}
            deliveryMessage={deliveryMessage}
            onNext={() => goToStep('verify')}
            onBack={() => goToStep('account')}
            loading={loading}
            setLoading={setLoading}
            setError={setError}
            onVerificationSent={(vid, ds, dm) => {
              setVerificationId(vid);
              setDeliveryStatus(ds);
              setDeliveryMessage(dm);
            }}
          />
        );
      case 'verify':
        return (
          <VerifyStep
            headingRef={stepHeadingRef}
            verificationId={verificationId}
            onNext={(uid) => {
              setUserId(uid);
              goToStep('device');
            }}
            onBack={() => goToStep('phone')}
            setError={setError}
          />
        );
      case 'device':
        return <DeviceStep headingRef={stepHeadingRef} deviceLabel="" onNext={() => goToStep('trusted-contact')} />;
      case 'trusted-contact':
        return (
          <TrustedContactStep
            headingRef={stepHeadingRef}
            contact={trustedContact}
            onChange={setTrustedContact}
            onNext={() => goToStep('consent')}
            onBack={() => goToStep('device')}
            setError={setError}
            setLoading={setLoading}
            loading={loading}
          />
        );
      case 'consent':
        return (
          <ConsentStep
            headingRef={stepHeadingRef}
            consent={emergencyConsent}
            onChange={setEmergencyConsent}
            userId={userId}
            onNext={() => goToStep('ready')}
            onBack={() => goToStep('trusted-contact')}
            setError={setError}
            setLoading={setLoading}
            loading={loading}
          />
        );
      case 'ready':
        return <ReadyStep headingRef={stepHeadingRef} onComplete={() => navigate('/home')} />;
      default:
        return null;
    }
  };

  const stepNumber = STEP_ORDER.indexOf(step) + 1;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 7rem)',
        padding: 'var(--space-8)',
        animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) both',
      }}
    >
      {step !== 'welcome' && step !== 'ready' && (
        <p
          role="status"
          aria-live="polite"
          aria-atomic="true"
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-3)',
            letterSpacing: 'var(--tracking-wider)',
            textTransform: 'uppercase',
          }}
        >
          Step {stepNumber} of {STEP_ORDER.length}
        </p>
      )}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            marginBottom: 'var(--space-4)',
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--lumina-warning-bg, #fff3cd)',
            color: 'var(--lumina-warning-text, #856404)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {error}
        </div>
      )}
      {renderStep()}
    </div>
  );
}

// ---- Welcome Step ----

function WelcomeStep({ onNext, headingRef }: { onNext: () => void; headingRef?: RefObject<HTMLHeadingElement> }) {
  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%', textAlign: 'center' }}>
      <h1
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-3xl)',
          fontWeight: 900,
          letterSpacing: 'var(--tracking-wider)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Welcome to LUMINA
      </h1>
      <p
        style={{
          fontSize: 'var(--text-base)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: 'var(--space-6)',
        }}
      >
        LUMINA helps you understand suspicious digital incidents and decide what to do next.
      </p>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Your information stays under your control. LUMINA only collects what is needed for safety and the features you choose.
      </p>
      <Button variant="primary" onClick={onNext} style={{ width: '100%' }}>
        Get Started
      </Button>
    </Card>
  );
}

// ---- Account Step ----

function AccountStep({
  headingRef,
  account,
  onChange,
  onNext,
  onBack,
}: {
  headingRef?: RefObject<HTMLHeadingElement>;
  account: AccountData;
  onChange: (data: AccountData) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Create Account
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Your phone number identifies your LUMINA account. It is not automatically a trusted contact.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <div>
          <label
            htmlFor="displayName"
            style={{
              display: 'block',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--lumina-text)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Display Name
          </label>
          <input
            id="displayName"
            type="text"
            value={account.displayName}
            onChange={(e) => onChange({ ...account, displayName: e.target.value })}
            placeholder="Your name"
            aria-required="true"
            autoComplete="name"
            style={{
              width: '100%',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border, #e2e8f0)',
              fontSize: 'var(--text-base)',
            }}
          />
        </div>
        <div>
          <label
            htmlFor="phoneNumber"
            style={{
              display: 'block',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--lumina-text)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Phone Number
          </label>
          <input
            id="phoneNumber"
            type="tel"
            value={account.phoneNumber}
            onChange={(e) => onChange({ ...account, phoneNumber: e.target.value })}
            placeholder="+919876543210"
            aria-required="true"
            autoComplete="tel"
            style={{
              width: '100%',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border, #e2e8f0)',
              fontSize: 'var(--text-base)',
            }}
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={onBack} style={{ flex: 1 }}>
          Back
        </Button>
        <Button
          variant="primary"
          onClick={onNext}
          disabled={!account.displayName.trim() || !account.phoneNumber.trim()}
          style={{ flex: 2 }}
        >
          Continue
        </Button>
      </div>
    </Card>
  );
}

// ---- Phone Step (real API) ----

function PhoneStep({
  headingRef,
  displayName,
  phoneNumber,
  deliveryStatus,
  deliveryMessage,
  onNext,
  onBack,
  loading,
  setLoading,
  setError,
  onVerificationSent,
}: {
  headingRef?: RefObject<HTMLHeadingElement>;
  displayName: string;
  phoneNumber: string;
  deliveryStatus: string;
  deliveryMessage: string;
  onNext: () => void;
  onBack: () => void;
  loading: boolean;
  setLoading: (v: boolean) => void;
  setError: (msg: string) => void;
  onVerificationSent: (vid: string, ds: string, dm: string) => void;
}) {
  const handleSend = async () => {
    setLoading(true);
    setError('');
    try {
      await createAccount(displayName, phoneNumber);
      const result = await requestPhoneVerification(phoneNumber);
      onVerificationSent(result.verification_id, result.delivery_status, result.delivery_message);
      if (result.delivery_status === 'SENT' || result.delivery_status === 'DELIVERED') {
        onNext();
      } else {
        setError(result.delivery_message || 'Verification code could not be sent. Please try again.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send verification code');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Verify Phone
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        We'll send a verification code to {phoneNumber}.
      </p>
      {deliveryStatus && (
        <p
          role="status"
          aria-live="polite"
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-secondary)',
            marginBottom: 'var(--space-4)',
            padding: 'var(--space-2)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--lumina-accent-soft, rgba(0,0,0,0.04))',
          }}
        >
          {deliveryMessage || `Delivery status: ${deliveryStatus}`}
        </p>
      )}
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={onBack} disabled={loading} style={{ flex: 1 }}>
          Back
        </Button>
        <Button
          variant="primary"
          onClick={handleSend}
          disabled={loading}
          aria-busy={loading}
          style={{ flex: 2 }}
        >
          {loading ? 'Sending...' : 'Send Verification Code'}
        </Button>
      </div>
    </Card>
  );
}

// ---- Verify Step (real API) ----

function VerifyStep({
  headingRef,
  verificationId,
  onNext,
  onBack,
  setError,
}: {
  headingRef?: RefObject<HTMLHeadingElement>;
  verificationId: string;
  onNext: (userId: string) => void;
  onBack: () => void;
  setError: (msg: string) => void;
}) {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await confirmPhoneVerification(verificationId, otp);
      if (result.verified) {
        onNext(result.user_id);
      } else {
        setError('Invalid verification code. Please try again.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Enter Code
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Enter the 6-digit code sent to your phone.
      </p>
      <div>
        <label
          htmlFor="otp"
          style={{
            display: 'block',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-2)',
          }}
        >
          Verification Code
        </label>
        <input
          id="otp"
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
          placeholder="000000"
          maxLength={6}
          autoComplete="one-time-code"
          aria-required="true"
          style={{
            width: '100%',
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--lumina-border, #e2e8f0)',
            fontSize: 'var(--text-base)',
            textAlign: 'center',
            letterSpacing: '0.5em',
          }}
        />
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={onBack} disabled={loading} style={{ flex: 1 }}>
          Back
        </Button>
        <Button
          variant="primary"
          onClick={handleVerify}
          disabled={otp.length !== 6 || loading}
          aria-busy={loading}
          style={{ flex: 2 }}
        >
          {loading ? 'Verifying...' : 'Verify'}
        </Button>
      </div>
    </Card>
  );
}

// ---- Device Step ----

function DeviceStep({ headingRef, deviceLabel, onNext }: { headingRef?: RefObject<HTMLHeadingElement>; deviceLabel: string; onNext: () => void }) {
  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Device Security
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        This device is securely linked to your LUMINA account. Your device identity is protected by cryptographic authentication.
      </p>
      {deviceLabel && (
        <p
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-4)',
          }}
        >
          Device label: {deviceLabel}
        </p>
      )}
      <Button variant="primary" onClick={onNext} style={{ width: '100%' }}>
        Continue
      </Button>
    </Card>
  );
}

// ---- Trusted Contact Step (real API) ----

function TrustedContactStep({
  headingRef,
  contact,
  onChange,
  onNext,
  onBack,
  setError,
  setLoading,
  loading,
}: {
  headingRef?: RefObject<HTMLHeadingElement>;
  contact: TrustedContactData;
  onChange: (data: TrustedContactData) => void;
  onNext: () => void;
  onBack: () => void;
  setError: (msg: string) => void;
  setLoading: (v: boolean) => void;
  loading: boolean;
}) {
  const handleSave = async () => {
    setLoading(true);
    setError('');
    try {
      await saveTrustedContact({
        display_name: contact.name,
        delivery_channel: 'SMS',
        destination: contact.phone,
        phone_number: contact.phone,
        automatic_help_enabled: false,
      });
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save trusted contact');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Trusted Contact
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Choose someone you trust. LUMINA can contact them if you ask for help.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <div>
          <label
            htmlFor="contactName"
            style={{
              display: 'block',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--lumina-text)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Contact Name
          </label>
          <input
            id="contactName"
            type="text"
            value={contact.name}
            onChange={(e) => onChange({ ...contact, name: e.target.value })}
            placeholder="Name of trusted person"
            autoComplete="name"
            style={{
              width: '100%',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border, #e2e8f0)',
              fontSize: 'var(--text-base)',
            }}
          />
        </div>
        <div>
          <label
            htmlFor="contactPhone"
            style={{
              display: 'block',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--lumina-text)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Phone Number
          </label>
          <input
            id="contactPhone"
            type="tel"
            value={contact.phone}
            onChange={(e) => onChange({ ...contact, phone: e.target.value })}
            placeholder="+919876543210"
            autoComplete="tel"
            style={{
              width: '100%',
              padding: 'var(--space-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border, #e2e8f0)',
              fontSize: 'var(--text-base)',
            }}
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={onBack} disabled={loading} style={{ flex: 1 }}>
          Back
        </Button>
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!contact.name.trim() || !contact.phone.trim() || loading}
          aria-busy={loading}
          style={{ flex: 2 }}
        >
          {loading ? 'Saving...' : 'Continue'}
        </Button>
      </div>
    </Card>
  );
}

// ---- Consent Step (real API) ----

function ConsentStep({
  headingRef,
  consent,
  onChange,
  userId,
  onNext,
  onBack,
  setError,
  setLoading,
  loading,
}: {
  headingRef?: RefObject<HTMLHeadingElement>;
  consent: boolean;
  onChange: (v: boolean) => void;
  userId: string;
  onNext: () => void;
  onBack: () => void;
  setError: (msg: string) => void;
  setLoading: (v: boolean) => void;
  loading: boolean;
}) {
  const handleContinue = async () => {
    setLoading(true);
    setError('');
    try {
      await setEmergencyConsent(userId, consent);
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update consent');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        Emergency Consent
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        By enabling emergency assistance, you allow LUMINA to contact your trusted contact when the configured emergency policy is triggered.
      </p>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Manual help (I'M TRAPPED) is always available. Automatic help is off by default.
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
        <input
          id="emergencyConsent"
          type="checkbox"
          checked={consent}
          onChange={(e) => onChange(e.target.checked)}
          style={{ width: '1.25rem', height: '1.25rem', accentColor: 'var(--lumina-accent, #7c3aed)' }}
        />
        <label
          htmlFor="emergencyConsent"
          style={{
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--lumina-text)',
          }}
        >
          Enable automatic emergency assistance
        </label>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={onBack} disabled={loading} style={{ flex: 1 }}>
          Back
        </Button>
        <Button
          variant="primary"
          onClick={handleContinue}
          disabled={loading}
          aria-busy={loading}
          style={{ flex: 2 }}
        >
          {loading ? 'Saving...' : 'Continue'}
        </Button>
      </div>
    </Card>
  );
}

// ---- Ready Step ----

function ReadyStep({ headingRef, onComplete }: { headingRef?: RefObject<HTMLHeadingElement>; onComplete: () => void }) {
  return (
    <Card elevated style={{ maxWidth: '32rem', width: '100%', textAlign: 'center' }}>
      <h2
        ref={headingRef}
        tabIndex={-1}
        style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          outline: 'none',
        }}
      >
        You're Ready
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          marginBottom: 'var(--space-6)',
        }}
      >
        LUMINA is configured and ready to help. You can always update your settings later.
      </p>
      <Button variant="primary" onClick={onComplete} style={{ width: '100%' }}>
        Start Using LUMINA
      </Button>
    </Card>
  );
}
