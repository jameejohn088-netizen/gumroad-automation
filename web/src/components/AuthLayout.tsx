import type { ReactNode } from 'react';
import { Card } from './ui';

export default function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-center text-xl font-bold text-gray-900 dark:text-white">
          Gumroad<span className="text-blue-600"> Automation</span>
        </h1>
        <h2 className="mt-4 text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>}
        <div className="mt-6 space-y-4">{children}</div>
      </Card>
    </div>
  );
}
