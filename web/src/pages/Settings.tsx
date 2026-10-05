import { useState } from 'react';
import type { FormEvent } from 'react';
import { api, API_BASE } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useApp } from '../context/AppContext';
import { Badge, Button, Card, ErrorBanner, Field, Input, PageHeader } from '../components/ui';

export default function Settings() {
  const { user, logout, refreshUser } = useAuth();
  const { theme, toggleTheme } = useApp();

  const [name, setName] = useState(user?.name ?? '');
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<unknown>(null);
  const [profileBusy, setProfileBusy] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwMsg, setPwMsg] = useState<string | null>(null);
  const [pwError, setPwError] = useState<unknown>(null);
  const [pwBusy, setPwBusy] = useState(false);

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    setProfileMsg(null);
    if (!name.trim()) {
      setProfileError(new Error('Name cannot be empty.'));
      return;
    }
    setProfileBusy(true);
    try {
      await api.updateMe({ name: name.trim() });
      await refreshUser();
      setProfileMsg('Profile updated.');
    } catch (err) {
      setProfileError(err);
    } finally {
      setProfileBusy(false);
    }
  };

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPwError(null);
    setPwMsg(null);
    if (newPw !== confirmPw) {
      setPwError(new Error('New passwords do not match.'));
      return;
    }
    if (newPw.length < 8) {
      setPwError(new Error('New password must be at least 8 characters.'));
      return;
    }
    setPwBusy(true);
    try {
      const res = await api.changePassword(currentPw, newPw);
      setPwMsg(res.message || 'Password changed.');
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err) {
      setPwError(err);
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Settings" description="Your profile, security, and app preferences." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Profile</h2>
          <form onSubmit={saveProfile} className="mt-4 space-y-4">
            {profileError ? <ErrorBanner error={profileError} /> : null}
            {profileMsg && (
              <p className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300" role="status">
                {profileMsg}
              </p>
            )}
            <Field label="Name" htmlFor="profile-name" required>
              <Input id="profile-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
            </Field>
            <Field label="Email" htmlFor="profile-email" hint="Email cannot be changed here.">
              <Input id="profile-email" value={user?.email ?? ''} disabled readOnly />
            </Field>
            <div>
              <Badge tone={user?.email_verified ? 'green' : 'yellow'}>
                {user?.email_verified ? 'Email verified' : 'Email not verified — check your inbox for the verification link'}
              </Badge>
            </div>
            <Button type="submit" loading={profileBusy}>Save profile</Button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Change password</h2>
          <form onSubmit={changePassword} className="mt-4 space-y-4">
            {pwError ? <ErrorBanner error={pwError} /> : null}
            {pwMsg && (
              <p className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300" role="status">
                {pwMsg}
              </p>
            )}
            <Field label="Current password" htmlFor="pw-current" required>
              <Input id="pw-current" type="password" autoComplete="current-password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} required />
            </Field>
            <Field label="New password" htmlFor="pw-new" required hint="At least 8 characters.">
              <Input id="pw-new" type="password" autoComplete="new-password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required />
            </Field>
            <Field label="Confirm new password" htmlFor="pw-confirm" required>
              <Input id="pw-confirm" type="password" autoComplete="new-password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} required />
            </Field>
            <Button type="submit" loading={pwBusy}>Change password</Button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Preferences</h2>
          <div className="mt-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700 dark:text-gray-300">Theme</span>
              <Button variant="secondary" onClick={toggleTheme}>
                {theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              </Button>
            </div>
            <Field label="Backend API URL" htmlFor="api-url" hint="Set at build time via the VITE_API_URL environment variable.">
              <Input id="api-url" value={API_BASE} readOnly disabled className="font-mono text-xs" />
            </Field>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Session</h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Logging out revokes your refresh token on the server.
          </p>
          <Button variant="danger" className="mt-4" onClick={() => logout()}>
            Log out
          </Button>
        </Card>
      </div>
    </div>
  );
}
