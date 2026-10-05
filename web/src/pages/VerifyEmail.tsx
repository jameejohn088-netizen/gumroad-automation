import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import AuthLayout from '../components/AuthLayout';
import { ErrorBanner, LoadingBlock } from '../components/ui';

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setState('error');
      setMessage('This verification link is missing its token.');
      return;
    }
    let cancelled = false;
    api
      .verifyEmail(token)
      .then((res) => {
        if (!cancelled) {
          setState('ok');
          setMessage(res.message || 'Your email has been verified.');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState('error');
          setMessage(err instanceof Error ? err.message : 'Verification failed.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AuthLayout title="Verify email">
      {state === 'loading' && <LoadingBlock label="Verifying your email…" />}
      {state === 'ok' && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300" role="status">
          <p className="font-medium">Email verified</p>
          <p className="mt-1">{message}</p>
          <Link to="/login" className="mt-3 inline-block font-medium text-blue-600 hover:underline dark:text-blue-400">
            Go to login →
          </Link>
        </div>
      )}
      {state === 'error' && <ErrorBanner error={new Error(message)} />}
    </AuthLayout>
  );
}
