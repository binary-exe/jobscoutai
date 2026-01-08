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
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <a href="#" className="hover:text-foreground transition-colors">
              Privacy
            </a>
            <a href="#" className="hover:text-foreground transition-colors">
              Terms
            </a>
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
      </div>
    </footer>
  );
}
