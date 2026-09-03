import { describe, it, expect } from 'vitest';
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
import { PrivacyPage } from '@/app/PrivacyPage';
import { AccessibilityPage } from '@/app/AccessibilityPage';
import { SecurityPage } from '@/app/SecurityPage';
import { TrustedContactPage } from '@/app/TrustedContactPage';

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

  it('PrivacyPage renders', () => {
    renderAtRoute('/privacy', <PrivacyPage />);
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
