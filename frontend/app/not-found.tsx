import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Search } from 'lucide-react';

export default function NotFound() {
  return (
    <>
      <Header />
      
      <main className="flex-1 flex items-center justify-center py-16">
        <div className="text-center">
          <div className="mx-auto rounded-full bg-muted p-4 w-fit">
            <Search className="h-8 w-8 text-muted-foreground" />
          </div>
          <h1 className="mt-4 text-2xl font-semibold">Page not found</h1>
          <p className="mt-2 text-muted-foreground">
            The page you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background hover:bg-foreground/90 transition-colors"
          >
            Back to jobs
          </Link>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
