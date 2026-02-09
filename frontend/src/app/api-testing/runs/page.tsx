'use client';

import { useEffect, useState, Suspense } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  PlayCircle,
  CheckCircle2,
  XCircle,
  Clock,
  Filter,
  Search,
  RefreshCw,
} from 'lucide-react';

import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/stores/authStore';
import { apiTestingRunsApi, ApiTestRunSummary } from '@/lib/api-testing';
import { cn } from '@/lib/utils';

type StatusFilter = 'all' | 'passed' | 'failed' | 'running' | 'error';
type EngineFilter = 'all' | 'python' | 'karate';

function formatDuration(durationMs?: number | null): string {
  if (durationMs == null) return '-';
  if (durationMs < 1000) return `${durationMs}ms`;
  if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`;
  return `${(durationMs / 60000).toFixed(1)}m`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function ApiRunsPageContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [runs, setRuns] = useState<ApiTestRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [engineFilter, setEngineFilter] = useState<EngineFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    void loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  const loadRuns = async () => {
    setLoading(true);
    try {
      const data = await apiTestingRunsApi.list();
      setRuns(data ?? []);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load API test runs:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredRuns = runs.filter((run) => {
    if (statusFilter !== 'all' && run.status !== statusFilter) {
      return false;
    }
    if (engineFilter !== 'all' && run.engine !== engineFilter) {
      return false;
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const name = (run.name || '').toLowerCase();
      const collection = (run.collection_name || '').toLowerCase();
      if (!name.includes(q) && !collection.includes(q)) {
        return false;
      }
    }
    return true;
  });

  if (!isAuthenticated) return null;

  const stats = {
    total: runs.length,
    passed: runs.filter((r) => r.status === 'passed').length,
    failed: runs.filter((r) => r.status === 'failed').length,
    running: runs.filter((r) => r.status === 'running').length,
    error: runs.filter((r) => r.status === 'error').length,
  };

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-card/30">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div>
              <h1 className="text-xl font-semibold">API Test Runs</h1>
              <p className="text-sm text-muted-foreground">
                History of API collections executed with Python or Karate engines.
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={loadRuns}>
            <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
        </header>

        {/* Filters */}
        <div className="px-6 py-4 border-b border-border/50 bg-card/20">
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search by run name or collection..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* Status Filter */}
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                className="h-9 w-[150px] appearance-none rounded-md border border-input bg-background pl-9 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="all">All Status</option>
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="running">Running</option>
                <option value="error">Error</option>
              </select>
            </div>

            {/* Engine Filter */}
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              <select
                value={engineFilter}
                onChange={(e) => setEngineFilter(e.target.value as EngineFilter)}
                className="h-9 w-[150px] appearance-none rounded-md border border-input bg-background pl-9 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="all">All Engines</option>
                <option value="python">Python</option>
                <option value="karate">Karate</option>
              </select>
            </div>

            {/* Quick Stats */}
            <div className="flex items-center gap-4 ml-auto text-sm">
              <span className="text-muted-foreground">
                Total: <span className="font-medium text-foreground">{stats.total}</span>
              </span>
              <span className="text-green-500">
                <CheckCircle2 className="w-4 h-4 inline mr-1" />
                {stats.passed}
              </span>
              <span className="text-red-500">
                <XCircle className="w-4 h-4 inline mr-1" />
                {stats.failed}
              </span>
              {stats.running > 0 && (
                <span className="text-yellow-500">
                  <Clock className="w-4 h-4 inline mr-1 animate-pulse" />
                  {stats.running}
                </span>
              )}
              {stats.error > 0 && (
                <span className="text-rose-400">
                  <AlertIcon />
                  {stats.error}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Runs list */}
        <main className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredRuns.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <PlayCircle className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">No API test runs found</p>
              <p className="text-sm mt-1">
                {searchQuery || statusFilter !== 'all' || engineFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Run an API collection to see results here'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/50">
              {filteredRuns.map((run) => (
                <Link
                  key={run.id}
                  href={`/api-testing/runs/${run.id}`}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-muted/50 transition-colors"
                >
                  {/* Status Icon */}
                  <div className="flex-shrink-0">
                    {run.status === 'passed' ? (
                      <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                      </div>
                    ) : run.status === 'failed' || run.status === 'error' ? (
                      <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                        <XCircle className="w-5 h-5 text-red-500" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center">
                        <Clock className="w-5 h-5 text-yellow-500 animate-pulse" />
                      </div>
                    )}
                  </div>

                  {/* Run info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">
                        {run.name || run.collection_name || 'Unnamed run'}
                      </p>
                      {run.collection_name && (
                        <Badge variant="outline" className="text-[10px]">
                          {run.collection_name}
                        </Badge>
                      )}
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {run.engine}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground text-[11px]">
                      <span className="capitalize">{run.status}</span>
                      <span>
                        {run.total_requests} req • {run.passed_requests} passed /{' '}
                        {run.failed_requests} failed
                      </span>
                    </div>
                  </div>

                  {/* Timing */}
                  <div className="flex flex-col items-end gap-1 flex-shrink-0 text-right">
                    <span className="text-sm font-medium">
                      {formatDuration(run.total_duration_ms)}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {formatDateTime(run.started_at ?? run.created_at)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

function AlertIcon() {
  return <XCircle className="w-4 h-4 inline mr-1" />;
}

export default function ApiRunsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
      <ApiRunsPageContent />
    </Suspense>
  );
}

