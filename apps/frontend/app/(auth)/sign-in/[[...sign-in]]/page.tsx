import { SignIn } from '@clerk/nextjs';
import Link from 'next/link';
import { ShieldCheck } from 'lucide-react';

export default function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="mb-6 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <span className="text-xl font-bold tracking-tight">Zentrix.ai</span>
      </div>

      <SignIn
        appearance={{
          elements: {
            rootBox: 'mx-auto',
            card: 'bg-card border border-border shadow-xl rounded-xl',
          },
        }}
      />

      <p className="mt-6 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground underline underline-offset-4">
          ← Back to home
        </Link>
      </p>
    </div>
  );
}
