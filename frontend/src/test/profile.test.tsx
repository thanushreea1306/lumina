import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProfilePage } from '@/app/ProfilePage';

// ---- Mock API ----

const mockProfile = {
  account_id: 'user123',
  display_name: 'Test User',
  phone_masked: '+91****3210',
  phone_verified: true,
  account_status: 'ACTIVE',
  emergency_consent: 'NOT_GIVEN',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const mockGetProfile = vi.fn();
const mockUpdateProfile = vi.fn();
const mockDeleteAccount = vi.fn();

vi.mock('@/lib/api/account', () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
  deleteAccount: (...args: unknown[]) => mockDeleteAccount(...args),
  requestAccountDeletion: vi.fn(),
}));

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={['/profile']}>
      <ProfilePage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ---- Tests ----

describe('ProfilePage', () => {
  it('shows loading state initially', () => {
    mockGetProfile.mockReturnValue(new Promise(() => {})); // never resolves
    renderProfile();
    expect(screen.getByText(/loading profile/i)).toBeInTheDocument();
  });

  it('loads and displays profile data', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    expect(screen.getByText('+91****3210')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument(); // emergency consent NOT_GIVEN
  });

  it('displays error state when profile load fails', async () => {
    mockGetProfile.mockRejectedValue(new Error('Network error'));
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('allows editing display name', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    mockUpdateProfile.mockResolvedValue({ ...mockProfile, display_name: 'New Name' });
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    // Click edit
    fireEvent.click(screen.getByText('Edit'));

    // Edit name
    const input = screen.getByLabelText('Display name');
    fireEvent.change(input, { target: { value: 'New Name' } });

    // Save
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith('New Name');
    });
  });

  it('cancel edit reverts changes', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Edit'));
    const input = screen.getByLabelText('Display name');
    fireEvent.change(input, { target: { value: 'Changed' } });
    fireEvent.click(screen.getByText('Cancel'));

    // Original name should still be shown
    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(mockUpdateProfile).not.toHaveBeenCalled();
  });

  it('shows masked phone number', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('+91****3210')).toBeInTheDocument();
    });
  });

  it('shows verification status', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Verified')).toBeInTheDocument();
    });
  });

  it('shows unverified status when phone is not verified', async () => {
    mockGetProfile.mockResolvedValue({ ...mockProfile, phone_verified: false });
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Unverified')).toBeInTheDocument();
    });
  });

  it('shows account deletion button', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument();
    });
  });

  it('opens delete confirmation dialog', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument();
    });

    // Click the delete button (the one in the danger zone card)
    const deleteButtons = screen.getAllByText('Delete Account');
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    // Dialog should appear
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText(/permanently remove/i)).toBeInTheDocument();
  });

  it('delete confirmation dialog can be cancelled', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('Delete Account');
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Cancel'));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('retry button reloads profile on error', async () => {
    mockGetProfile
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Retry'));

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
  });

  it('shows security link', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText(/device identity/i)).toBeInTheDocument();
    });
  });

  it('handles revoked account status', async () => {
    mockGetProfile.mockResolvedValue({ ...mockProfile, account_status: 'REVOKED' });
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText('REVOKED')).toBeInTheDocument();
    });
  });

  it('displays account creation date', async () => {
    mockGetProfile.mockResolvedValue(mockProfile);
    renderProfile();

    await waitFor(() => {
      expect(screen.getByText(/created/i)).toBeInTheDocument();
    });
  });
});
