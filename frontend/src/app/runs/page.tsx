'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  PlayCircle,
  CheckCircle2,
  XCircle,
  Clock,
  Filter,
  Search,
  RefreshCw,
  ExternalLink,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { useAuthStore } from '@/stores/authStore';
import { dashboardApi, RunListItem } from '@/lib/api';
import { cn } from '@/lib/utils';

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function formatDuration(durationMs?: number): string {
  if (!durationMs) return '-';
  if (durationMs < 1000) return `${durationMs}ms`;
  if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`;
  return `${(durationMs / 60000).toFixed(1)}m`;
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function RunsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuthStore();

  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadRuns();
  }, [isAuthenticated, statusFilter]);

  const loadRuns = async () => {
    setLoading(true);
    try {
      const params: { status?: string; limit: number } = { limit: 100 };
      if (statusFilter && statusFilter !== 'all') {
        params.status = statusFilter;
      }
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'runs/page.tsx:82',message:'Before calling dashboardApi.listRuns',data:{params},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
      // #endregion
      const data = await dashboardApi.listRuns(params);
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'runs/page.tsx:86',message:'After calling dashboardApi.listRuns',data:{data_length:data?.length||0,data_preview:data?.slice(0,2)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
      // #endregion
      setRuns(data);
    } catch (error) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'runs/page.tsx:89',message:'Error loading runs',data:{error:String(error)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
      // #endregion
      console.error('Failed to load runs:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredRuns = runs.filter((run) => {
    if (!searchQuery) return true;
    return run.test_name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const stats = {
    total: runs.length,
    passed: runs.filter((r) => r.status === 'passed').length,
    failed: runs.filter((r) => r.status === 'failed').length,
    running: runs.filter((r) => r.status === 'running').length,
  };

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-card/30">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div>
              <h1 className="text-xl font-semibold">Test Runs</h1>
              <p className="text-sm text-muted-foreground">History of all test executions</p>
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
                placeholder="Search by test name..."
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
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 w-[150px] appearance-none rounded-md border border-input bg-background pl-9 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="all">All Status</option>
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="running">Running</option>
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
            </div>
          </div>
        </div>

        {/* Runs List */}
        <main className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredRuns.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <PlayCircle className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">No test runs found</p>
              <p className="text-sm mt-1">
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Run a test to see results here'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/50">
              {filteredRuns.map((run) => (
                <Link
                  key={run.id}
                  href={`/tests/${run.test_id}/run`}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-muted/50 transition-colors"
                >
                  {/* Status Icon */}
                  <div className="flex-shrink-0">
                    {run.status === 'passed' ? (
                      <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                      </div>
                    ) : run.status === 'failed' ? (
                      <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                        <XCircle className="w-5 h-5 text-red-500" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center">
                        <Clock className="w-5 h-5 text-yellow-500 animate-pulse" />
                      </div>
                    )}
                  </div>

                  {/* Test Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{run.test_name}</p>
                      <Badge variant="outline" className="text-[10px]">
                        v{run.version_number}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                      {run.collection_name && (
                        <span className="flex items-center gap-1">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: run.collection_color }}
                          />
                          {run.collection_name}
                        </span>
                      )}
                      <span>{formatDateTime(run.started_at)}</span>
                    </div>
                    {run.status === 'failed' && run.error_message && (
                      <p className="text-xs text-red-400 mt-1 line-clamp-1 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        {run.error_message}
                      </p>
                    )}
                  </div>

                  {/* Duration & Status */}
                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="text-right">
                      <p className="text-sm font-medium">{formatDuration(run.duration_ms)}</p>
                      <p className="text-xs text-muted-foreground">{formatTimeAgo(run.started_at)}</p>
                    </div>
                    <Badge
                      variant={
                        run.status === 'passed'
                          ? 'default'
                          : run.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                      }
                    >
                      {run.status}
                    </Badge>
                    <ExternalLink className="w-4 h-4 text-muted-foreground" />
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

export default function RunsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
      <RunsPageContent />
    </Suspense>
  );
}
