'use client';

import { Briefcase, Clock, TrendingUp, Database } from 'lucide-react';
import { Stats as StatsType } from '@/lib/api';
import { cn } from '@/lib/utils';

interface StatsProps {
  stats: StatsType;
  className?: string;
}

export function Stats({ stats, className }: StatsProps) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-4", className)}>
      <StatCard
        icon={<Briefcase className="h-4 w-4" />}
        label="Total Jobs"
        value={stats.total_jobs.toLocaleString()}
      />
      <StatCard
        icon={<TrendingUp className="h-4 w-4" />}
        label="New Today"
        value={`+${stats.jobs_last_24h}`}
        highlight
      />
      <StatCard
        icon={<Clock className="h-4 w-4" />}
        label="This Week"
        value={`+${stats.jobs_last_7d}`}
      />
      <StatCard
        icon={<Database className="h-4 w-4" />}
        label="Sources"
        value={Object.keys(stats.sources).length.toString()}
      />
    </div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}

function StatCard({ icon, label, value, highlight }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className={cn(
        "mt-1 text-xl font-semibold",
        highlight && "text-remote"
      )}>
        {value}
      </div>
    </div>
  );
}
