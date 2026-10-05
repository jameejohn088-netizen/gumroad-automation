import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import AuthLayout from '../components/AuthLayout';
import { Button, ErrorBanner, Field, Input } from '../components/ui';

export default function Signup() {
  const { signup } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
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
      const msg = await signup(name.trim(), email.trim(), password);
      setDone(msg);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Create account" subtitle="Start automating your Gumroad sales.">
      {error ? <ErrorBanner error={error} /> : null}
      {done ? (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300" role="status">
          <p className="font-medium">Account created</p>
          <p className="mt-1">{done}</p>
          <Link to="/login" className="mt-3 inline-block font-medium text-blue-600 hover:underline dark:text-blue-400">
            Go to login →
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Name" htmlFor="name" required>
            <Input id="name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
          </Field>
          <Field label="Email" htmlFor="email" required>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </Field>
          <Field label="Password" htmlFor="password" required hint="At least 8 characters.">
            <Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          <Field label="Confirm password" htmlFor="confirm" required>
            <Input id="confirm" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••" />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>
            Sign up
          </Button>
        </form>
      )}
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Already have an account?{' '}
        <Link to="/login" className="text-blue-600 hover:underline dark:text-blue-400">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
