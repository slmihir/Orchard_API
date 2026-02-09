'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  BarChart3,
  PlayCircle,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  Plus,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { useAuthStore } from '@/stores/authStore';
import { dashboardApi, DashboardStats, RecentRun } from '@/lib/api';
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

function formatDuration(startedAt: string, finishedAt?: string): string {
  if (!finishedAt) return 'Running...';
  const start = new Date(startedAt);
  const end = new Date(finishedAt);
  const diffMs = end.getTime() - start.getTime();
  if (diffMs < 1000) return `${diffMs}ms`;
  if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
  return `${(diffMs / 60000).toFixed(1)}m`;
}

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([]);
  const [recentFailures, setRecentFailures] = useState<RecentRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadData();
  }, [isAuthenticated]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, runsData, failuresData] = await Promise.all([
        dashboardApi.getStats(),
        dashboardApi.getRecentRuns(8),
        dashboardApi.getRecentFailures(5),
      ]);
      setStats(statsData);
      setRecentRuns(runsData);
      setRecentFailures(failuresData);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
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
              <h1 className="text-xl font-semibold">Dashboard</h1>
              <p className="text-sm text-muted-foreground">Overview of your test automation</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={loadData}>
              <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
              Refresh
            </Button>
            <Link href="/">
              <Button size="sm">
                <Plus className="w-4 h-4 mr-2" />
                Create Test
              </Button>
            </Link>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Tests
                </CardTitle>
                <BarChart3 className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_tests ?? '-'}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Saved test cases
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Runs
                </CardTitle>
                <PlayCircle className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_runs ?? '-'}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {stats?.runs_today ?? 0} runs today
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Pass Rate
                </CardTitle>
                <TrendingUp className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats?.pass_rate !== undefined ? `${stats.pass_rate}%` : '-'}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-green-500">{stats?.passed_runs ?? 0} passed</span>
                  <span className="text-xs text-muted-foreground">/</span>
                  <span className="text-xs text-red-500">{stats?.failed_runs ?? 0} failed</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Runs Today
                </CardTitle>
                <Clock className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.runs_today ?? '-'}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Last 24 hours
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Main content grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recent Runs */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Recent Runs</CardTitle>
                    <CardDescription>Latest test executions</CardDescription>
                  </div>
                  <Link href="/runs">
                    <Button variant="ghost" size="sm">
                      View All
                      <ArrowRight className="w-4 h-4 ml-1" />
                    </Button>
                  </Link>
                </CardHeader>
                <CardContent>
                  {recentRuns.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <PlayCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No test runs yet</p>
                      <p className="text-xs mt-1">Run a test to see results here</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentRuns.map((run) => (
                        <Link
                          key={run.id}
                          href={`/tests/${run.test_id}/run`}
                          className="flex items-center justify-between p-3 rounded-lg border border-border/50 hover:bg-muted/50 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            {run.status === 'passed' ? (
                              <CheckCircle2 className="w-5 h-5 text-green-500" />
                            ) : run.status === 'failed' ? (
                              <XCircle className="w-5 h-5 text-red-500" />
                            ) : (
                              <Clock className="w-5 h-5 text-yellow-500 animate-pulse" />
                            )}
                            <div>
                              <p className="font-medium text-sm">{run.test_name}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {run.collection_name && (
                                  <Badge
                                    variant="outline"
                                    className="text-[10px] px-1.5 py-0"
                                    style={{ borderColor: run.collection_color }}
                                  >
                                    {run.collection_name}
                                  </Badge>
                                )}
                                <span className="text-xs text-muted-foreground">
                                  {formatTimeAgo(run.started_at)}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge
                              variant={
                                run.status === 'passed'
                                  ? 'default'
                                  : run.status === 'failed'
                                  ? 'destructive'
                                  : 'secondary'
                              }
                              className="text-xs"
                            >
                              {run.status}
                            </Badge>
                            <p className="text-xs text-muted-foreground mt-1">
                              {formatDuration(run.started_at, run.finished_at)}
                            </p>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Recent Failures */}
            <div>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    <CardTitle>Recent Failures</CardTitle>
                  </div>
                  <CardDescription>Tests that need attention</CardDescription>
                </CardHeader>
                <CardContent>
                  {recentFailures.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500 opacity-50" />
                      <p className="text-green-600">All tests passing!</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentFailures.map((run) => (
                        <Link
                          key={run.id}
                          href={`/tests/${run.test_id}/run`}
                          className="block p-3 rounded-lg border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <p className="font-medium text-sm">{run.test_name}</p>
                            <span className="text-xs text-muted-foreground">
                              {formatTimeAgo(run.started_at)}
                            </span>
                          </div>
                          {run.error_message && (
                            <p className="text-xs text-red-400 mt-1 line-clamp-2">
                              {run.error_message}
                            </p>
                          )}
                        </Link>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card className="mt-4">
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Link href="/" className="block">
                    <Button variant="outline" className="w-full justify-start">
                      <Plus className="w-4 h-4 mr-2" />
                      Create New Test
                    </Button>
                  </Link>
                  <Link href="/tests" className="block">
                    <Button variant="outline" className="w-full justify-start">
                      <BarChart3 className="w-4 h-4 mr-2" />
                      View All Tests
                    </Button>
                  </Link>
                  <Link href="/runs" className="block">
                    <Button variant="outline" className="w-full justify-start">
                      <PlayCircle className="w-4 h-4 mr-2" />
                      View Run History
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
