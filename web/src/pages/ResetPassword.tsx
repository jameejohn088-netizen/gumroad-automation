import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import AuthLayout from '../components/AuthLayout';
import { Button, ErrorBanner, Field, Input } from '../components/ui';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError(new Error('Passwords do not match.'));
      return;
    }
    if (password.length < 8) {
      setError(new Error('Password must be at least 8 characters.'));
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      navigate('/login?reset=1', { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <AuthLayout title="Reset password">
        <ErrorBanner error={new Error('This reset link is missing its token. Please request a new one.')} />
        <p className="text-sm">
          <Link to="/forgot-password" className="text-blue-600 hover:underline dark:text-blue-400">
            Request a new reset link
          </Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Set a new password" subtitle="Choose a new password for your account.">
      {error ? <ErrorBanner error={error} /> : null}
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="New password" htmlFor="password" required hint="At least 8 characters.">
          <Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </Field>
        <Field label="Confirm new password" htmlFor="confirm" required>
          <Input id="confirm" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••" />
        </Field>
        <Button type="submit" className="w-full" loading={loading}>
          Reset password
        </Button>
      </form>
    </AuthLayout>
  );
}
