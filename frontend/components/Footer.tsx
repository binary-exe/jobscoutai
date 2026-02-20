import Link from 'next/link';
import { Heart } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-border/40 py-8 mt-auto">
      <div className="container mx-auto max-w-5xl px-4">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="text-sm text-muted-foreground">
            Built with{' '}
            <Heart className="inline h-3 w-3 text-red-500" />{' '}
            for remote workers everywhere
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <Link href="/pricing" className="hover:text-foreground transition-colors">
              Pricing
            </Link>
            <Link href="/terms" className="hover:text-foreground transition-colors">
              Terms
            </Link>
            <Link href="/privacy" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
            <Link href="/refunds" className="hover:text-foreground transition-colors">
              Refunds
            </Link>
            <Link href="/contact" className="hover:text-foreground transition-colors">
              Contact
            </Link>
            <a 
              href="https://producthunt.com/products/jobscout"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Product Hunt
            </a>
          </div>
        </div>
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Payments powered by Paddle.
        </p>
      </div>
    </footer>
  );
}
