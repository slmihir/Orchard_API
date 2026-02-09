'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, XCircle, Clock, ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react';

import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/stores/authStore';
import { apiTestingRunsApi, ApiTestRunDetailResponse, APIRequestResultResponse } from '@/lib/api-testing';

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

function statusIcon(status: string) {
  if (status === 'passed') {
    return <CheckCircle2 className="w-4 h-4 text-green-500" />;
  }
  if (status === 'failed' || status === 'error') {
    return <XCircle className="w-4 h-4 text-red-500" />;
  }
  return <Clock className="w-4 h-4 text-yellow-500" />;
}

function formatJson(value: string | Record<string, unknown> | null | undefined): string {
  if (!value) return '';
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
}

function formatHeaders(headers: Record<string, unknown> | null | undefined): string {
  if (!headers || typeof headers !== 'object') return '';
  return Object.entries(headers)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    .join('\n');
}

function toErrorMessage(e: unknown, fallback: string): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') {
    return (e as { message: string }).message;
  }
  return fallback;
}

function ApiRunDetailContent() {
  const params = useParams<{ runId: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [run, setRun] = useState<ApiTestRunDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiTestingRunsApi.get(params.runId);
        setRun(data);
      } catch (e: unknown) {
        // eslint-disable-next-line no-console
        console.error('Failed to load API test run detail', e);
        setError(toErrorMessage(e, 'Failed to load API test run detail'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [isAuthenticated, params.runId]);

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-card/30">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => router.push('/api-testing/runs')}
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div>
                <h1 className="text-xl font-semibold">
                  API Test Run
                  {run?.name ? `: ${run.name}` : ''}
                </h1>
                <p className="text-sm text-muted-foreground">
                  Detailed execution results for this API collection run.
                </p>
              </div>
            </div>
          </div>
          {run && (
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  run.status === 'passed'
                    ? 'default'
                    : run.status === 'failed' || run.status === 'error'
                    ? 'destructive'
                    : 'secondary'
                }
                className="capitalize flex items-center gap-1"
              >
                {statusIcon(run.status)}
                <span>{run.status}</span>
              </Badge>
              <Badge variant="outline" className="capitalize">
                {run.engine}
              </Badge>
            </div>
          )}
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              Loading run details...
            </div>
          ) : error ? (
            <div className="border border-destructive/40 bg-destructive/5 rounded-md p-4 text-sm text-destructive">
              {error}
            </div>
          ) : !run ? (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              Run not found.
            </div>
          ) : (
            <>
              {/* Summary */}
              <section className="grid gap-4 md:grid-cols-3">
                <div className="border border-border/60 rounded-md bg-card/40 p-4 space-y-2">
                  <h2 className="text-sm font-medium">Run Info</h2>
                  <div className="text-xs text-muted-foreground space-y-1">
                    {run.collection_id && (
                      <div>
                        Collection ID:{' '}
                        <span className="font-mono text-foreground">{run.collection_id}</span>
                      </div>
                    )}
                    <div>
                      Trigger:{' '}
                      <span className="capitalize">
                        {run.trigger_type}
                        {run.trigger_source ? ` (${run.trigger_source})` : ''}
                      </span>
                    </div>
                    <div>
                      Started: <span>{formatDateTime(run.started_at)}</span>
                    </div>
                    <div>
                      Finished: <span>{formatDateTime(run.finished_at)}</span>
                    </div>
                    <div>
                      Duration:{' '}
                      <span className="font-medium">{formatDuration(run.total_duration_ms)}</span>
                    </div>
                  </div>
                </div>

                <div className="border border-border/60 rounded-md bg-card/40 p-4 space-y-2">
                  <h2 className="text-sm font-medium">Requests</h2>
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div>Total: {run.total_requests}</div>
                    <div className="text-green-500">Passed: {run.passed_requests}</div>
                    <div className="text-red-500">Failed: {run.failed_requests}</div>
                    <div>Skipped: {run.skipped_requests}</div>
                  </div>
                </div>

                <div className="border border-border/60 rounded-md bg-card/40 p-4 space-y-2">
                  <h2 className="text-sm font-medium">Assertions</h2>
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div>Total: {run.total_assertions}</div>
                    <div className="text-green-500">Passed: {run.passed_assertions}</div>
                    <div className="text-red-500">Failed: {run.failed_assertions}</div>
                    {run.error_message && (
                      <div className="text-destructive mt-1">
                        Error: <span>{run.error_message}</span>
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* Results table */}
              <section className="border border-border/60 rounded-md bg-card/40 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-medium">Request Results</h2>
                  <span className="text-xs text-muted-foreground">
                    {run.results?.length ?? 0} result
                    {run.results && run.results.length === 1 ? '' : 's'}
                  </span>
                </div>
                {(!run.results || run.results.length === 0) ? (
                  <p className="text-xs text-muted-foreground">
                    No detailed request results were recorded for this run.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="text-left border-b border-border/60 text-muted-foreground">
                        <tr>
                          <th className="py-2 pr-3">#</th>
                          <th className="py-2 pr-3">Status</th>
                          <th className="py-2 pr-3">Request</th>
                          <th className="py-2 pr-3">HTTP</th>
                          <th className="py-2 pr-3">Duration</th>
                          <th className="py-2 pr-3">Assertions</th>
                          <th className="py-2 pr-3">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.results.map((res: APIRequestResultResponse) => {
                          const isExpanded = expandedRows.has(res.id);
                          const hasAssertions =
                            Array.isArray(res.assertion_results) && res.assertion_results.length > 0;
                          const hasDetails =
                            res.resolved_url ||
                            res.resolved_method ||
                            res.resolved_headers ||
                            res.resolved_body ||
                            res.response_status != null ||
                            res.response_headers ||
                            res.response_body ||
                            hasAssertions;
                          return (
                            <React.Fragment key={res.id}>
                              <tr
                                className="border-b border-border/40 last:border-0 hover:bg-muted/30 cursor-pointer"
                                onClick={() => {
                                  if (!hasDetails) return;
                                  const newExpanded = new Set(expandedRows);
                                  if (isExpanded) {
                                    newExpanded.delete(res.id);
                                  } else {
                                    newExpanded.add(res.id);
                                  }
                                  setExpandedRows(newExpanded);
                                }}
                              >
                                <td className="py-2 pr-3 align-top">
                                  <div className="flex items-center gap-1">
                                    {hasDetails && (
                                      <button
                                        type="button"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const newExpanded = new Set(expandedRows);
                                          if (isExpanded) {
                                            newExpanded.delete(res.id);
                                          } else {
                                            newExpanded.add(res.id);
                                          }
                                          setExpandedRows(newExpanded);
                                        }}
                                      >
                                        {isExpanded ? (
                                          <ChevronDown className="w-3 h-3" />
                                        ) : (
                                          <ChevronRight className="w-3 h-3" />
                                        )}
                                      </button>
                                    )}
                                    <span>{res.execution_order}</span>
                                  </div>
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  <div className="flex items-center gap-1">
                                    {statusIcon(res.status)}
                                    <span className="capitalize">{res.status}</span>
                                  </div>
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  <div className="flex flex-col">
                                    <span className="font-mono text-[11px]">
                                      {res.resolved_method || ''}
                                    </span>
                                    <span className="font-mono text-[11px] text-muted-foreground break-all">
                                      {res.resolved_url || ''}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  {res.response_status != null ? (
                                    <span>{res.response_status}</span>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  {formatDuration(res.duration_ms)}
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  {Array.isArray(res.assertion_results) &&
                                  res.assertion_results.length > 0 ? (
                                    <span>
                                      {res.assertion_results.filter((a: any) => a?.passed).length} /
                                      {res.assertion_results.length} passed
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                                <td className="py-2 pr-3 align-top max-w-xs">
                                  {res.error_message ? (
                                    <span className="text-destructive line-clamp-2">
                                      {res.error_message}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                              </tr>
                              {isExpanded && hasDetails && (
                                <tr>
                                  <td colSpan={7} className="p-4 bg-muted/20">
                                    {/* Assertion Details - Show first if available */}
                                    {hasAssertions && (
                                      <div className="mb-4 pb-4 border-b border-border/60">
                                        <h3 className="text-xs font-semibold text-foreground mb-3">
                                          Assertion Results ({res.assertion_results!.length})
                                        </h3>
                                        <div className="space-y-2">
                                          {res.assertion_results!.map((assertion: any, idx: number) => (
                                            <div
                                              key={idx}
                                              className={`text-[11px] p-3 rounded border ${
                                                assertion.passed
                                                  ? 'bg-green-500/10 border-green-500/20 text-green-600'
                                                  : 'bg-red-500/10 border-red-500/20 text-red-600'
                                              }`}
                                            >
                                              <div className="flex items-center gap-2 mb-1">
                                                {assertion.passed ? (
                                                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                                                ) : (
                                                  <XCircle className="w-4 h-4 flex-shrink-0" />
                                                )}
                                                <span className="font-semibold">
                                                  {assertion.name || assertion.type || `Assertion ${idx + 1}`}
                                                </span>
                                                <Badge
                                                  variant={assertion.passed ? 'default' : 'destructive'}
                                                  className="text-[10px] ml-auto"
                                                >
                                                  {assertion.passed ? 'Passed' : 'Failed'}
                                                </Badge>
                                              </div>
                                              {assertion.message && (
                                                <div className="mt-2 ml-6 text-muted-foreground text-[10px]">
                                                  {assertion.message}
                                                </div>
                                              )}
                                              {(assertion.expected != null || assertion.actual != null) && (
                                                <div className="mt-2 ml-6 space-y-1 text-[10px]">
                                                  {assertion.expected != null && (
                                                    <div className="text-muted-foreground">
                                                      <span className="font-medium">Expected:</span>{' '}
                                                      <span className="font-mono">
                                                        {typeof assertion.expected === 'object'
                                                          ? JSON.stringify(assertion.expected)
                                                          : String(assertion.expected)}
                                                      </span>
                                                    </div>
                                                  )}
                                                  {assertion.actual != null && (
                                                    <div className="text-muted-foreground">
                                                      <span className="font-medium">Actual:</span>{' '}
                                                      <span className="font-mono">
                                                        {typeof assertion.actual === 'object'
                                                          ? JSON.stringify(assertion.actual)
                                                          : String(assertion.actual)}
                                                      </span>
                                                    </div>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    <div className="grid gap-4 md:grid-cols-2">
                                      {/* Request Details */}
                                      <div className="space-y-3">
                                        <h3 className="text-xs font-semibold text-foreground">
                                          Request Details
                                        </h3>
                                        {(res.resolved_method || res.resolved_url) && (
                                          <div className="space-y-1">
                                            {res.resolved_method && (
                                              <div>
                                                <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                                  Method
                                                </h4>
                                                <div className="text-[11px] font-mono bg-background border border-border/60 rounded p-2">
                                                  {res.resolved_method}
                                                </div>
                                              </div>
                                            )}
                                            {res.resolved_url && (
                                              <div>
                                                <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                                  URL
                                                </h4>
                                                <pre className="text-[10px] bg-background border border-border/60 rounded p-2 overflow-x-auto break-all font-mono">
                                                  {res.resolved_url}
                                                </pre>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                        {res.resolved_headers && Object.keys(res.resolved_headers).length > 0 && (
                                          <div>
                                            <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                              Headers
                                            </h4>
                                            <pre className="text-[10px] bg-background border border-border/60 rounded p-2 overflow-x-auto font-mono">
                                              {formatHeaders(res.resolved_headers)}
                                            </pre>
                                          </div>
                                        )}
                                        {res.resolved_body && (
                                          <div>
                                            <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                              Body
                                            </h4>
                                            <pre className="text-[10px] bg-background border border-border/60 rounded p-2 overflow-x-auto max-h-64 overflow-y-auto font-mono">
                                              {formatJson(res.resolved_body)}
                                            </pre>
                                          </div>
                                        )}
                                        {!res.resolved_method && !res.resolved_url && !res.resolved_headers && !res.resolved_body && (
                                          <p className="text-[11px] text-muted-foreground">
                                            No request details available
                                          </p>
                                        )}
                                      </div>

                                      {/* Response Details */}
                                      <div className="space-y-3">
                                        <h3 className="text-xs font-semibold text-foreground">
                                          Response Details
                                        </h3>
                                        {res.response_status != null && (
                                          <div>
                                            <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                              Status Code
                                            </h4>
                                            <div className="text-[11px] font-mono bg-background border border-border/60 rounded p-2">
                                              {res.response_status}
                                            </div>
                                          </div>
                                        )}
                                        {res.response_headers && (
                                          <div>
                                            <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                              Headers
                                            </h4>
                                            <pre className="text-[10px] bg-background border border-border/60 rounded p-2 overflow-x-auto font-mono">
                                              {formatHeaders(res.response_headers)}
                                            </pre>
                                          </div>
                                        )}
                                        {res.response_body && (
                                          <div>
                                            <h4 className="text-[11px] font-medium text-muted-foreground mb-1">
                                              Body
                                              {res.response_size_bytes != null && (
                                                <span className="ml-2 text-muted-foreground">
                                                  ({res.response_size_bytes} bytes)
                                                </span>
                                              )}
                                            </h4>
                                            <pre className="text-[10px] bg-background border border-border/60 rounded p-2 overflow-x-auto max-h-64 overflow-y-auto font-mono">
                                              {formatJson(res.response_body)}
                                            </pre>
                                          </div>
                                        )}
                                        {res.response_status == null &&
                                          !res.response_headers &&
                                          !res.response_body && (
                                            <p className="text-[11px] text-muted-foreground">
                                              No response details available (re-run the collection to capture response from Karate)
                                            </p>
                                          )}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Back to API Testing */}
              <div className="flex justify-between items-center pt-2">
                <Link href="/api-testing" className="text-xs text-primary hover:underline">
                  ← Back to API Testing
                </Link>
                <Link href="/api-testing/runs" className="text-xs text-primary hover:underline">
                  View all API runs
                </Link>
              </div>
            </>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default function ApiRunDetailPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
      <ApiRunDetailContent />
    </Suspense>
  );
}

