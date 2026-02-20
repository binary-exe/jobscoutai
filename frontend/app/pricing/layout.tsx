import type { Metadata } from 'next';
import { PRODUCT_NAME } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Pricing | ${PRODUCT_NAME}`,
  description: `Simple, transparent pricing for ${PRODUCT_NAME}. Free tier, Pro, and Power plans. Resume tailoring, cover letters, application tracking, and trust reports.`,
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
