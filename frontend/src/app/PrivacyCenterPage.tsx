import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { getMyAccount, deleteAccount, getPrivacyPolicy } from '@/lib/api/account';
import type { PrivacyPolicy } from '@/lib/api/account';

export function PrivacyCenterPage() {
  const navigate = useNavigate();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [policy, setPolicy] = useState<PrivacyPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const deleteButtonRef = useRef<HTMLButtonElement | null>(null);
  const wasDialogOpenRef = useRef(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [policyRes, accountRes] = await Promise.allSettled([
          getPrivacyPolicy(),
          getMyAccount(),
        ]);

        if (policyRes.status === 'fulfilled') {
          setPolicy(policyRes.value);
        } else {
          setError('Could not load privacy policy');
        }

        if (accountRes.status === 'fulfilled') {
          setUserId(accountRes.value.user_id);
        } else {
          setError((prev) => prev ?? 'Could not load account information');
        }
      } catch {
        setError('Could not load privacy policy');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const openDeleteConfirm = useCallback(() => {
    setShowDeleteConfirm(true);
  }, []);

  const closeDeleteConfirm = useCallback(() => {
    setShowDeleteConfirm(false);
    setDeleteError(null);
  }, []);

  useEffect(() => {
    if (showDeleteConfirm) {
      wasDialogOpenRef.current = true;
      dialogRef.current?.focus();
    } else {
      if (wasDialogOpenRef.current) {
        wasDialogOpenRef.current = false;
        deleteButtonRef.current?.focus();
      }
    }
  }, [showDeleteConfirm]);

  useEffect(() => {
    if (!showDeleteConfirm) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        closeDeleteConfirm();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [showDeleteConfirm, closeDeleteConfirm]);

  const handleDeleteAccount = async () => {
    if (!userId) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount(userId);
      closeDeleteConfirm();
      navigate('/');
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete account');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: '48rem',
        margin: '0 auto',
        padding: 'var(--space-8)',
      }}
    >
      <h1
        style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Privacy Center
      </h1>

      {loading && (
        <Card style={{ marginBottom: 'var(--space-4)', textAlign: 'center' }}>
          <p
            role="status"
            aria-live="polite"
            style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-muted)' }}
          >
            Loading privacy policy...
          </p>
        </Card>
      )}

      {error && (
        <Card style={{ marginBottom: 'var(--space-4)' }}>
          <p
            role="alert"
            aria-live="assertive"
            style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-warning-text, #856404)' }}
          >
            {error}
          </p>
        </Card>
      )}

      {!loading && policy && (
      <>
      {/* What LUMINA Stores */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-3)',
          }}
        >
          What LUMINA Stores
        </h2>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {policy.summary.what_lumina_stores.map((item) => (
            <li
              key={item}
              style={{
                padding: 'var(--space-2) 0',
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                borderBottom: '1px solid var(--lumina-border, #e2e8f0)',
              }}
            >
              {item}
            </li>
          ))}
        </ul>
      </Card>

      {/* What LUMINA Does Not Store */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-3)',
          }}
        >
          What LUMINA Does Not Store
        </h2>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {policy.summary.what_lumina_does_not_store.map((item) => (
            <li
              key={item}
              style={{
                padding: 'var(--space-2) 0',
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                borderBottom: '1px solid var(--lumina-border, #e2e8f0)',
              }}
            >
              {item}
            </li>
          ))}
        </ul>
      </Card>

      {/* What Is Shared */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-3)',
          }}
        >
          What Is Shared
        </h2>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {policy.summary.what_is_shared.map((item) => (
            <li
              key={item}
              style={{
                padding: 'var(--space-2) 0',
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                borderBottom: '1px solid var(--lumina-border, #e2e8f0)',
              }}
            >
              {item}
            </li>
          ))}
        </ul>
      </Card>

      {/* AI Data Boundary */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-3)',
          }}
        >
          AI Data Boundary
        </h2>
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-secondary)',
            lineHeight: 'var(--leading-relaxed)',
          }}
        >
          {policy.summary.ai_data_boundary}
        </p>
      </Card>

      {/* Account & Data */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-3)',
          }}
        >
          Account & Data
        </h2>
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-secondary)',
            marginBottom: 'var(--space-4)',
          }}
        >
          You can delete your account identity data. Incident evidence is retained for safety continuity.
        </p>
        {!userId ? (
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>
            Sign in to manage your account.
          </p>
        ) : (
          <Button
            variant="secondary"
            ref={deleteButtonRef}
            onClick={openDeleteConfirm}
            style={{ width: '100%' }}
          >
            Delete Account
          </Button>
        )}
      </Card>
      </>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-title"
          aria-describedby="delete-description"
          tabIndex={-1}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--space-4)',
            outline: 'none',
          }}
        >
          <Card elevated style={{ maxWidth: '24rem', width: '100%' }}>
            <h2
              id="delete-title"
              style={{
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--lumina-text)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Delete Account
            </h2>
            <p
              id="delete-description"
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                marginBottom: 'var(--space-4)',
              }}
            >
              This will permanently remove your account identity, trusted contact, and device bindings. Incident evidence is retained for safety continuity.
            </p>
            {deleteError && (
              <p
                role="alert"
                aria-live="assertive"
                style={{
                  fontSize: 'var(--text-sm)',
                  color: 'var(--lumina-warning-text, #856404)',
                  marginBottom: 'var(--space-3)',
                }}
              >
                {deleteError}
              </p>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <Button
                variant="secondary"
                onClick={closeDeleteConfirm}
                disabled={deleting}
                style={{ flex: 1 }}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleDeleteAccount}
                disabled={deleting}
                aria-busy={deleting}
                style={{ flex: 1 }}
              >
                {deleting ? 'Deleting...' : 'Delete Account'}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
