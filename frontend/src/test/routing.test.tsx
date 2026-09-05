import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WelcomePage } from '@/app/WelcomePage';
import { ConsentPage } from '@/app/ConsentPage';
import { HomePage } from '@/app/HomePage';
import { SessionPage } from '@/app/SessionPage';
import { EvidencePage } from '@/app/EvidencePage';
import { HistoryPage } from '@/app/HistoryPage';
import { SettingsPage } from '@/app/SettingsPage';
import { RecoveryPage } from '@/app/RecoveryPage';
import { AccessibilityPage } from '@/app/AccessibilityPage';
import { SecurityPage } from '@/app/SecurityPage';
import { TrustedContactPage } from '@/app/TrustedContactPage';
import { PrivacyCenterPage } from '@/app/PrivacyCenterPage';
import appTsxSource from '../App.tsx?raw';

vi.mock('@/lib/api/account', () => ({
  getPrivacyPolicy: vi.fn(),
  getMyAccount: vi.fn(),
  createAccount: vi.fn(),
  requestPhoneVerification: vi.fn(),
  confirmPhoneVerification: vi.fn(),
  saveTrustedContact: vi.fn(),
  setEmergencyConsent: vi.fn(),
  deleteAccount: vi.fn(),
  requestAccountDeletion: vi.fn(),
  bindDeviceToAccount: vi.fn(),
}));

function renderAtRoute(path: string, element: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={path} element={element} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Routing - Page renders at correct path', () => {
  it('WelcomePage renders', () => {
    renderAtRoute('/', <WelcomePage />);
    expect(screen.getByText('LUMINA')).toBeInTheDocument();
    expect(screen.getByText(/digital forensics/i)).toBeInTheDocument();
  });

  it('ConsentPage renders', () => {
    renderAtRoute('/consent', <ConsentPage />);
    expect(screen.getByText(/data & privacy/i)).toBeInTheDocument();
  });

  it('HomePage renders loading state initially', () => {
    renderAtRoute('/home', <HomePage />);
    const elements = screen.getAllByText(/connecting to lumina/i);
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('SessionPage renders creation view', () => {
    renderAtRoute('/session', <SessionPage />);
    expect(screen.getByText(/begin a safety session/i)).toBeInTheDocument();
  });

  it('EvidencePage renders', () => {
    renderAtRoute('/evidence', <EvidencePage />);
    expect(screen.getByText(/evidence board/i)).toBeInTheDocument();
  });

  it('HistoryPage renders', () => {
    renderAtRoute('/history', <HistoryPage />);
    expect(screen.getByText(/no history available/i)).toBeInTheDocument();
  });

  it('SettingsPage renders', () => {
    renderAtRoute('/settings', <SettingsPage />);
    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
  });

  it('RecoveryPage renders', () => {
    renderAtRoute('/recovery', <RecoveryPage />);
    expect(screen.getByText(/no active session/i)).toBeInTheDocument();
  });

  it('PrivacyCenterPage renders at /privacy', () => {
    renderAtRoute('/privacy', <PrivacyCenterPage />);
    expect(screen.getByRole('heading', { name: /privacy center/i })).toBeInTheDocument();
  });

  it('AccessibilityPage renders', () => {
    renderAtRoute('/accessibility', <AccessibilityPage />);
    expect(screen.getByRole('heading', { name: /accessibility/i })).toBeInTheDocument();
  });

  it('SecurityPage renders', () => {
    renderAtRoute('/security', <SecurityPage />);
    expect(screen.getByRole('heading', { name: /security/i })).toBeInTheDocument();
  });

  it('TrustedContactPage renders', () => {
    renderAtRoute('/trusted-contact', <TrustedContactPage />);
    expect(screen.getByRole('heading', { name: 'Trusted Contact' })).toBeInTheDocument();
    expect(screen.getByText(/not yet fully configured/i)).toBeInTheDocument();
  });
});

describe('Routing - App.tsx route structure', () => {
  it('has exactly one /privacy route', () => {
    const matches = appTsxSource.match(/path=["']\/privacy["']/g);
    expect(matches).toHaveLength(1);
  });

  it('/privacy renders PrivacyCenterPage, not the old PrivacyPage', () => {
    const privacyIdx = appTsxSource.indexOf('"/privacy"');
    const surrounding = appTsxSource.slice(privacyIdx, privacyIdx + 200);
    expect(surrounding).toContain('PrivacyCenterPage');
  });

  it('/privacy is a public route (not wrapped in AppShell)', () => {
    const lines = appTsxSource.split('\n');
    const privacyLineIdx = lines.findIndex((l) => l.includes('"/privacy"'));
    const above = lines.slice(Math.max(0, privacyLineIdx - 10), privacyLineIdx).join('\n');
    expect(above).not.toContain('AppShell');
  });
});
