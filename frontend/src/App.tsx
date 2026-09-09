import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { WelcomePage } from '@/app/WelcomePage';
import { ConsentPage } from '@/app/ConsentPage';
import { OnboardingPage } from '@/app/OnboardingPage';
import { PrivacyCenterPage } from '@/app/PrivacyCenterPage';
import { HomePage } from '@/app/HomePage';
import { SessionPage } from '@/app/SessionPage';
import { EvidencePage } from '@/app/EvidencePage';
import { HistoryPage } from '@/app/HistoryPage';
import { SettingsPage } from '@/app/SettingsPage';
import { VerifyPage } from '@/app/VerifyPage';
import { PausePage } from '@/app/PausePage';
import { ProtectPage } from '@/app/ProtectPage';
import { RecoveryPage } from '@/app/RecoveryPage';
import { AccessibilityPage } from '@/app/AccessibilityPage';
import { SecurityPage } from '@/app/SecurityPage';
import { ProfilePage } from '@/app/ProfilePage';
import { IncidentEntryPage } from '@/app/IncidentEntryPage';
import { IncidentViewPage } from '@/app/IncidentViewPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes (no shell) */}
        <Route path="/" element={<WelcomePage />} />
        <Route path="/welcome" element={<Navigate to="/" replace />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/privacy" element={<PrivacyCenterPage />} />

        {/* Protected routes (with shell) */}
        <Route
          path="/home"
          element={
            <AppShell>
              <HomePage />
            </AppShell>
          }
        />
        <Route
          path="/session"
          element={
            <AppShell>
              <SessionPage />
            </AppShell>
          }
        />
        <Route
          path="/evidence"
          element={
            <AppShell>
              <EvidencePage />
            </AppShell>
          }
        />
        <Route
          path="/history"
          element={
            <AppShell>
              <HistoryPage />
            </AppShell>
          }
        />
        <Route
          path="/verify"
          element={
            <AppShell>
              <VerifyPage />
            </AppShell>
          }
        />
        <Route
          path="/pause"
          element={
            <AppShell>
              <PausePage />
            </AppShell>
          }
        />
        <Route
          path="/protect"
          element={
            <AppShell>
              <ProtectPage />
            </AppShell>
          }
        />
        <Route
          path="/recovery"
          element={
            <AppShell>
              <RecoveryPage />
            </AppShell>
          }
        />
        <Route
          path="/accessibility"
          element={
            <AppShell>
              <AccessibilityPage />
            </AppShell>
          }
        />
        <Route
          path="/security"
          element={
            <AppShell>
              <SecurityPage />
            </AppShell>
          }
        />
        <Route
          path="/profile"
          element={
            <AppShell>
              <ProfilePage />
            </AppShell>
          }
        />
        <Route
          path="/settings"
          element={
            <AppShell>
              <SettingsPage />
            </AppShell>
          }
        />
        <Route
          path="/incident/new"
          element={
            <AppShell>
              <IncidentEntryPage />
            </AppShell>
          }
        />
        <Route
          path="/incident"
          element={
            <AppShell>
              <IncidentViewPage />
            </AppShell>
          }
        />

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
