/* ============================================================
   LUMINA Profile Page
   ============================================================
   Displays and allows editing of the user's profile:
   - Display name (editable)
   - Masked phone number
   - Verification status
   - Account status
   - Emergency consent status
   - Account deletion entry

   All data comes from real API responses. No mock data.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';
import {
  getProfile,
  updateProfile,
  deleteAccount,
} from '@/lib/api/account';
import type { ProfileResponse } from '@/lib/api/account';

function StatusBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      style={{
        fontSize: 'var(--text-xs)',
        fontWeight: 700,
        letterSpacing: 'var(--tracking-wider)',
        textTransform: 'uppercase',
        color: active ? 'var(--lumina-recovery)' : 'var(--lumina-text-muted)',
      }}
    >
      {label}
    </span>
  );
}

export function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const deleteButtonRef = useRef<HTMLButtonElement | null>(null);
  const wasDialogOpenRef = useRef(false);

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getProfile();
      setProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load profile');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleStartEdit = useCallback(() => {
    if (profile) {
      setEditName(profile.display_name);
      setEditing(true);
      setSaveError(null);
    }
  }, [profile]);

  const handleSave = useCallback(async () => {
    if (!editName.trim()) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateProfile(editName.trim());
      setProfile(updated);
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  }, [editName]);

  const handleCancelEdit = useCallback(() => {
    setEditing(false);
    setSaveError(null);
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
    } else if (wasDialogOpenRef.current) {
      wasDialogOpenRef.current = false;
      deleteButtonRef.current?.focus();
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

  const handleDeleteAccount = useCallback(async () => {
    if (!profile) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount(profile.account_id);
      closeDeleteConfirm();
      navigate('/');
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete account');
    } finally {
      setDeleting(false);
    }
  }, [profile, closeDeleteConfirm, navigate]);

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={7}
        title="Profile"
        subtitle="Your LUMINA account information"
      />

      {loading && (
        <Card style={{ marginBottom: 'var(--space-4)', textAlign: 'center' }}>
          <p
            role="status"
            aria-live="polite"
            style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-muted)' }}
          >
            Loading profile...
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
          <Button variant="secondary" onClick={loadProfile} style={{ marginTop: 'var(--space-3)' }}>
            Retry
          </Button>
        </Card>
      )}

      {!loading && profile && (
        <>
          {/* Display Name */}
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Display Name
            </div>
            {editing ? (
              <div>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={100}
                  aria-label="Display name"
                  style={{
                    width: '100%',
                    padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--lumina-border, #e2e8f0)',
                    fontSize: 'var(--text-base)',
                    marginBottom: 'var(--space-3)',
                  }}
                />
                {saveError && (
                  <p
                    role="alert"
                    style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-warning-text, #856404)', marginBottom: 'var(--space-3)' }}
                  >
                    {saveError}
                  </p>
                )}
                <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                  <Button variant="secondary" onClick={handleCancelEdit} disabled={saving} style={{ flex: 1 }}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleSave}
                    disabled={!editName.trim() || saving}
                    aria-busy={saving}
                    style={{ flex: 1 }}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-base)', color: 'var(--lumina-text)' }}>
                  {profile.display_name || 'Not set'}
                </span>
                <Button variant="ghost" size="sm" onClick={handleStartEdit}>
                  Edit
                </Button>
              </div>
            )}
          </Card>

          {/* Phone & Verification */}
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Phone &amp; Verification
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-2) 0',
                  borderBottom: '1px solid var(--lumina-border-subtle)',
                }}
              >
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                  Phone Number
                </span>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text)', fontFamily: 'var(--font-mono)' }}>
                  {profile.phone_masked || 'Not provided'}
                </span>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-2) 0',
                  borderBottom: '1px solid var(--lumina-border-subtle)',
                }}
              >
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                  Verification Status
                </span>
                <StatusBadge
                  label={profile.phone_verified ? 'Verified' : 'Unverified'}
                  active={profile.phone_verified}
                />
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-2) 0',
                }}
              >
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                  Account Status
                </span>
                <StatusBadge
                  label={profile.account_status}
                  active={profile.account_status === 'ACTIVE'}
                />
              </div>
            </div>
          </Card>

          {/* Emergency Consent */}
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Emergency Consent
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                Automatic emergency assistance
              </span>
              <StatusBadge
                label={profile.emergency_consent === 'GIVEN' ? 'Enabled' : 'Disabled'}
                active={profile.emergency_consent === 'GIVEN'}
              />
            </div>
          </Card>

          {/* Account Info */}
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Account Information
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0' }}>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>Created</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(profile.created_at).toLocaleDateString()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0' }}>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>Last Updated</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(profile.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </Card>

          {/* Security & Sessions */}
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Security &amp; Sessions
            </div>
            <button
              onClick={() => navigate('/security')}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
                padding: 'var(--space-3) 0',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                Device identity &amp; authentication
              </span>
              <span style={{ color: 'var(--lumina-text-muted)', fontSize: 'var(--text-lg)' }}>›</span>
            </button>
          </Card>

          {/* Account Deletion */}
          <Card style={{ marginBottom: 'var(--space-4)', borderLeft: '3px solid var(--lumina-danger)' }}>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--lumina-danger)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Account Deletion
            </div>
            <p
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-muted)',
                lineHeight: 'var(--leading-relaxed)',
                marginBottom: 'var(--space-4)',
              }}
            >
              Deleting your account removes your identity, devices, trusted contact, and help policies.
              Incident evidence is retained for safety continuity.
            </p>
            <Button
              ref={deleteButtonRef}
              variant="danger"
              onClick={openDeleteConfirm}
              style={{ width: '100%' }}
            >
              Delete Account
            </Button>
          </Card>
        </>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-delete-title"
          aria-describedby="profile-delete-description"
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
              id="profile-delete-title"
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
              id="profile-delete-description"
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                marginBottom: 'var(--space-4)',
              }}
            >
              This will permanently remove your account identity, trusted contact, and device bindings.
              Incident evidence is retained for safety continuity.
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
              <Button variant="secondary" onClick={closeDeleteConfirm} disabled={deleting} style={{ flex: 1 }}>
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
