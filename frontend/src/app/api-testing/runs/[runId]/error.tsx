'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { TriangleAlert } from 'lucide-react';

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  if (err && typeof err === 'object' && 'message' in err && typeof (err as { message: unknown }).message === 'string') {
    return (err as { message: string }).message;
  }
  return 'Something went wrong';
}

export default function RunDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('API test run detail error:', error);
  }, [error]);

  const message = errorMessage(error);

  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 p-6">
      <TriangleAlert className="h-10 w-10 text-destructive" />
      <h2 className="text-base font-semibold">Failed to load run</h2>
      <p className="max-w-md text-center text-sm text-muted-foreground">{message}</p>
      <div className="flex gap-2">
        <Button variant="outline" onClick={reset}>
          Try again
        </Button>
        <Button asChild variant="default">
          <Link href="/api-testing/runs">Back to runs</Link>
        </Button>
      </div>
    </div>
  );
}
