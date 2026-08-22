'use client';

import * as React from 'react';
import { AlertCircle, Inbox, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export function LoadingState({
  message = 'Loading live data...',
  className,
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center p-12 text-center', className)}>
      <Loader2 className="h-8 w-8 animate-spin text-primary opacity-80" />
      <p className="mt-3 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function ErrorState({
  title = 'Failed to load data',
  message = 'An unexpected error occurred while communicating with the backend API.',
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <Card className={cn('border-destructive/40 bg-destructive/5', className)}>
      <CardContent className="flex flex-col items-center justify-center p-8 text-center">
        <div className="rounded-full bg-destructive/10 p-3 text-destructive">
          <AlertCircle className="h-6 w-6" />
        </div>
        <h3 className="mt-3 text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-1 max-w-md text-xs text-muted-foreground">{message}</p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="mt-4 gap-2">
            <RefreshCw className="h-3.5 w-3.5" />
            Retry Request
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export function EmptyState({
  title = 'No records found',
  description = 'There is currently no data available for this view.',
  action,
  className,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-lg border border-dashed border-border p-12 text-center', className)}>
      <div className="rounded-full bg-muted p-3 text-muted-foreground">
        <Inbox className="h-6 w-6" />
      </div>
      <h3 className="mt-3 text-base font-medium text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
