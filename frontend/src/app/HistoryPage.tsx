import { SectionHeader } from '@/components/SectionHeader';
import { EmptyState } from '@/components/EmptyState';

export function HistoryPage() {
  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={5}
        title="Session History"
        subtitle="Past safety sessions and outcomes"
      />

      <EmptyState
        title="No History"
        description="Completed sessions will appear here with their safety decisions and outcomes."
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        }
      />
    </div>
  );
}
