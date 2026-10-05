import { useCallback, useEffect, useState } from 'react';
import type { ListParams } from '../api/client';
import type { Paginated } from '../api/types';

/**
 * Paginated, searchable list state wired to a backend list fetcher.
 * Pass a stable fetcher (e.g. api.products) and the selected account id.
 */
export function usePaginated<T>(
  fetcher: (p: ListParams) => Promise<Paginated<T>>,
  accountId?: string,
) {
  const perPage = 20;
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [data, setData] = useState<Paginated<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q);
      setPage(1);
    }, 400);
    return () => window.clearTimeout(t);
  }, [q]);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher({ account_id: accountId, q: debouncedQ || undefined, page, per_page: perPage })
      .then((d) => setData(d))
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  }, [fetcher, accountId, debouncedQ, page]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Reset to first page when the account filter changes.
  useEffect(() => {
    setPage(1);
  }, [accountId]);

  return { page, setPage, q, setQ, data, loading, error, reload, perPage };
}
