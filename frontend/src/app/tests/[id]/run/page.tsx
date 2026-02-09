'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Play,
  Square,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Gauge,
  Zap,
  Eye,
  LayoutGrid,
  Timer,
  Trash2,
  Wand2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { testsApi, healingApi, TestResponse, TestRunnerWebSocket } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { HealingPanel, HealingSuggestion, InlineApprovalDialog } from '@/components/healing/HealingDiff';

interface StepStatus {
  index: number;
  id?: string;
  type: string;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped' | 'healing' | 'healed' | 'waiting_approval';
  selector?: string;
  value?: string;
  error?: string;
  original_selector?: string;
}

interface ApprovalRequest {
  step_index: number;
  original_selector: string;
  suggested_selector: string;
  confidence: number;
  reasoning?: string;
}

interface PerformanceMetrics {
  step_index: number;
  url: string;
  ttfb: number;
  fcp: number;
  lcp: number;
  dom_content_loaded: number;
  load: number;
  cls: number;
  ratings: {
    lcp: 'good' | 'needs-improvement' | 'poor';
    fcp: 'good' | 'needs-improvement' | 'poor';
    cls: 'good' | 'needs-improvement' | 'poor';
    ttfb: 'good' | 'needs-improvement' | 'poor';
  };
}

const getRatingColor = (rating: string) => {
  switch (rating) {
    case 'good':
      return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    case 'needs-improvement':
      return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
    case 'poor':
      return 'text-red-500 bg-red-500/10 border-red-500/20';
    default:
      return 'text-muted-foreground bg-muted/10 border-border/50';
  }
};

const getRatingDot = (rating: string) => {
  switch (rating) {
    case 'good':
      return 'bg-emerald-500';
    case 'needs-improvement':
      return 'bg-amber-500';
    case 'poor':
      return 'bg-red-500';
    default:
      return 'bg-muted-foreground';
  }
};

const formatMs = (ms: number) => {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
};

export default function TestRunPage() {
  const params = useParams();
  const router = useRouter();
  const testId = params.id as string;
  const { isAuthenticated } = useAuthStore();

  const [test, setTest] = useState<TestResponse | null>(null);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>([]);
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'passed' | 'failed'>('idle');
  const [ws, setWs] = useState<TestRunnerWebSocket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<PerformanceMetrics[]>([]);
  const [showMetrics, setShowMetrics] = useState(false);
  const [healingSuggestions, setHealingSuggestions] = useState<HealingSuggestion[]>([]);
  const [showHealing, setShowHealing] = useState(false);
  const [isHealingProcessing, setIsHealingProcessing] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [wsRef, setWsRef] = useState<WebSocket | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const loadTest = async () => {
      try {
        const data = await testsApi.get(testId);
        setTest(data);
        if (data.latest_version?.steps) {
          setStepStatuses(
            data.latest_version.steps.map((s, i) => ({
              index: i,
              id: s.id,
              type: s.type,
              status: 'pending',
              selector: s.selector,
              value: s.value,
            }))
          );
        }
      } catch (e) {
        setError('Failed to load test');
      }
    };
    loadTest();
  }, [testId, isAuthenticated]);

  const startRun = useCallback(async () => {
    if (!test) return;

    setRunStatus('running');
    setError(null);
    setMetrics([]);
    setHealingSuggestions([]);
    setShowHealing(false);
    setStepStatuses((prev) => prev.map((s) => ({ ...s, status: 'pending' })));

    try {
      const socket = new TestRunnerWebSocket(testId);
      await socket.connect();
      setWs(socket);

      socket.on('screenshot', (data: unknown) => {
        const { image } = data as { image: string };
        setScreenshot(image);
      });

      socket.on('step', (data: unknown) => {
        const step = data as StepStatus;
        setStepStatuses((prev) =>
          prev.map((s) =>
            s.index === step.index ? { ...s, status: step.status, error: step.error } : s
          )
        );
      });

      socket.on('metrics', (data: unknown) => {
        const metricsData = data as PerformanceMetrics;
        setMetrics((prev) => [...prev, metricsData]);
      });

      socket.on('healing', (data: unknown) => {
        const healingData = data as HealingSuggestion;
        setHealingSuggestions((prev) => [...prev, healingData]);
        if (!healingData.auto_approved) {
          setShowHealing(true);
        }
      });

      socket.on('approval_request', (data: unknown) => {
        const approvalData = data as ApprovalRequest;
        setPendingApproval(approvalData);
      });

      socket.on('complete', (data: unknown) => {
        const { success, message } = data as { success: boolean; message: string };
        setRunStatus(success ? 'passed' : 'failed');
        if (!success) setError(message);
        socket.disconnect();
        setWs(null);
      });

      socket.on('error', (data: unknown) => {
        const { message } = data as { message: string };
        setRunStatus('failed');
        setError(message);
        socket.disconnect();
        setWs(null);
      });
    } catch (e) {
      setRunStatus('failed');
      setError('Failed to start test run');
    }
  }, [test, testId]);

  const stopRun = useCallback(() => {
    ws?.disconnect();
    setWs(null);
    setRunStatus('idle');
  }, [ws]);

  const handleApprovalResponse = useCallback((approved: boolean) => {
    if (ws && pendingApproval) {
      ws.send('approval_response', { approved });
      setPendingApproval(null);
    }
  }, [ws, pendingApproval]);

  const deleteStep = useCallback(async (stepId: string) => {
    if (!test || runStatus === 'running') return;

    try {
      await testsApi.deleteStep(testId, stepId);
      const data = await testsApi.get(testId);
      setTest(data);
      if (data.latest_version?.steps) {
        setStepStatuses(
          data.latest_version.steps.map((s, i) => ({
            index: i,
            id: s.id,
            type: s.type,
            status: 'pending',
            selector: s.selector,
            value: s.value,
          }))
        );
      }
    } catch (e) {
      setError('Failed to delete step');
    }
  }, [test, testId, runStatus]);

  const handleApproveHealing = useCallback(async (suggestion: HealingSuggestion) => {
    setIsHealingProcessing(true);
    try {
      const step = stepStatuses[suggestion.step_index];
      if (step?.id) {
        await healingApi.approveSuggestionForStep(testId, step.id, suggestion.suggested_selector);
        setHealingSuggestions((prev) =>
          prev.map((s) =>
            s.step_index === suggestion.step_index ? { ...s, auto_approved: true } : s
          )
        );
        setStepStatuses((prev) =>
          prev.map((s) =>
            s.index === suggestion.step_index
              ? { ...s, selector: suggestion.suggested_selector, original_selector: suggestion.original_selector }
              : s
          )
        );
      }
    } catch (e) {
      setError('Failed to apply healing suggestion');
    } finally {
      setIsHealingProcessing(false);
    }
  }, [testId, stepStatuses]);

  const handleRejectHealing = useCallback((suggestion: HealingSuggestion) => {
    setHealingSuggestions((prev) => prev.filter((s) => s.step_index !== suggestion.step_index));
  }, []);

  const handleApproveAllHealing = useCallback(async () => {
    const pending = healingSuggestions.filter((s) => !s.auto_approved);
    for (const suggestion of pending) {
      await handleApproveHealing(suggestion);
    }
  }, [healingSuggestions, handleApproveHealing]);

  const pendingHealingSuggestions = healingSuggestions.filter((s) => !s.auto_approved);

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-card/30">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <Link href="/tests">
              <Button variant="ghost" size="sm" className="gap-2 -ml-2">
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-sm font-semibold">{test?.name || 'Loading...'}</h1>
              <p className="text-[10px] text-muted-foreground">Test Runner</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {runStatus === 'idle' && (
              <Button onClick={startRun} className="gap-2">
                <Play className="w-4 h-4" />
                Run Test
              </Button>
            )}
            {runStatus === 'running' && (
              <Button variant="destructive" onClick={stopRun} className="gap-2">
                <Square className="w-4 h-4" />
                Stop
              </Button>
            )}
            {runStatus === 'passed' && (
              <>
                <Badge className="bg-chart-2/20 text-chart-2 border-chart-2/30 gap-1">
                  <CheckCircle2 className="w-3 h-3" />
                  Passed
                </Badge>
                <Button variant="outline" size="sm" onClick={() => { setRunStatus('idle'); startRun(); }} className="gap-2">
                  <Play className="w-3 h-3" />
                  Rerun
                </Button>
              </>
            )}
            {runStatus === 'failed' && (
              <>
                <Badge variant="destructive" className="gap-1">
                  <XCircle className="w-3 h-3" />
                  Failed
                </Badge>
                <Button variant="outline" size="sm" onClick={() => { setRunStatus('idle'); startRun(); }} className="gap-2">
                  <Play className="w-3 h-3" />
                  Rerun
                </Button>
              </>
            )}
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex overflow-hidden">
          {/* Browser view */}
          <div className="flex-1 p-4">
            <div className="h-full rounded-xl border border-border/50 bg-card/30 overflow-hidden flex flex-col">
              <div className="px-4 py-2 border-b border-border/50 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-destructive/50" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50" />
                  <div className="w-2.5 h-2.5 rounded-full bg-chart-2/50" />
                </div>
                <div className="flex-1 mx-2">
                  <div className="bg-muted/30 rounded px-3 py-1 text-xs text-muted-foreground truncate">
                    {test?.target_url || 'No URL'}
                  </div>
                </div>
              </div>
              <div className="flex-1 relative bg-black/20">
                {screenshot ? (
                  <img
                    src={`data:image/jpeg;base64,${screenshot}`}
                    alt="Browser"
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                    {runStatus === 'running' ? (
                      <Loader2 className="w-8 h-8 animate-spin" />
                    ) : (
                      <span className="text-sm">Click &quot;Run Test&quot; to start</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right panel - Steps & Metrics */}
          <div className="w-96 border-l border-border/50 bg-card/20 flex flex-col overflow-hidden">
            {/* Tabs */}
            <div className="flex border-b border-border/50">
              <button
                onClick={() => { setShowMetrics(false); setShowHealing(false); }}
                className={`flex-1 px-4 py-2.5 text-xs font-medium transition-colors ${
                  !showMetrics && !showHealing
                    ? 'text-foreground border-b-2 border-primary'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Steps ({stepStatuses.length})
              </button>
              <button
                onClick={() => { setShowMetrics(true); setShowHealing(false); }}
                className={`flex-1 px-4 py-2.5 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                  showMetrics && !showHealing
                    ? 'text-foreground border-b-2 border-primary'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Gauge className="w-3.5 h-3.5" />
                Performance ({metrics.length})
              </button>
              {healingSuggestions.length > 0 && (
                <button
                  onClick={() => { setShowHealing(true); setShowMetrics(false); }}
                  className={`flex-1 px-4 py-2.5 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                    showHealing
                      ? 'text-foreground border-b-2 border-amber-500'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Wand2 className="w-3.5 h-3.5" />
                  Healing ({pendingHealingSuggestions.length > 0 ? pendingHealingSuggestions.length : healingSuggestions.length})
                  {pendingHealingSuggestions.length > 0 && (
                    <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  )}
                </button>
              )}
            </div>

            <div className="flex-1 overflow-auto p-4">
              {error && (
                <div className="mb-3 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
                  {error}
                </div>
              )}

              {/* Approval Dialog */}
              {pendingApproval && (
                <div className="mb-4">
                  <InlineApprovalDialog
                    stepIndex={pendingApproval.step_index}
                    originalSelector={pendingApproval.original_selector}
                    suggestedSelector={pendingApproval.suggested_selector}
                    confidence={pendingApproval.confidence}
                    reasoning={pendingApproval.reasoning}
                    onApprove={() => handleApprovalResponse(true)}
                    onReject={() => handleApprovalResponse(false)}
                  />
                </div>
              )}

              {/* Healing View */}
              {showHealing && (
                <HealingPanel
                  suggestions={healingSuggestions}
                  onApprove={handleApproveHealing}
                  onReject={handleRejectHealing}
                  onApproveAll={handleApproveAllHealing}
                  isProcessing={isHealingProcessing}
                />
              )}

              {/* Steps View */}
              {!showMetrics && !showHealing && (
                <div className="space-y-2">
                  {stepStatuses.map((step, i) => {
                    const stepMetrics = metrics.find((m) => m.step_index === i);
                    return (
                      <div
                        key={i}
                        className={`p-3 rounded-lg border transition-all ${
                          step.status === 'running'
                            ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                            : step.status === 'healing'
                            ? 'border-amber-500 bg-amber-500/5 ring-1 ring-amber-500/20'
                            : step.status === 'healed'
                            ? 'border-emerald-500/30 bg-emerald-500/5'
                            : step.status === 'passed'
                            ? 'border-chart-2/30 bg-chart-2/5'
                            : step.status === 'failed'
                            ? 'border-destructive/30 bg-destructive/5'
                            : 'border-border/50 bg-card/30'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <div className="flex-shrink-0">
                            {step.status === 'running' ? (
                              <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            ) : step.status === 'healing' ? (
                              <Wand2 className="w-4 h-4 animate-pulse text-amber-500" />
                            ) : step.status === 'healed' ? (
                              <Wand2 className="w-4 h-4 text-emerald-500" />
                            ) : step.status === 'passed' ? (
                              <CheckCircle2 className="w-4 h-4 text-chart-2" />
                            ) : step.status === 'failed' ? (
                              <XCircle className="w-4 h-4 text-destructive" />
                            ) : (
                              <Clock className="w-4 h-4 text-muted-foreground" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium capitalize">{step.type}</div>
                            <div className="text-[10px] text-muted-foreground truncate">
                              {step.type === 'navigate'
                                ? step.value
                                : step.type === 'fill'
                                ? `${step.selector} = "${step.value}"`
                                : step.selector || '—'}
                            </div>
                          </div>
                          <Badge variant="outline" className="text-[10px] h-5">
                            {i + 1}
                          </Badge>
                          {runStatus !== 'running' && step.id && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 text-muted-foreground hover:text-destructive"
                              onClick={() => deleteStep(step.id!)}
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                        {step.error && (
                          <div className="mt-2 text-[10px] text-destructive">{step.error}</div>
                        )}
                        {/* Inline metrics indicator for navigate steps */}
                        {stepMetrics && step.type === 'navigate' && (
                          <div className="mt-2 pt-2 border-t border-border/30 flex items-center gap-2">
                            <div className={`w-1.5 h-1.5 rounded-full ${getRatingDot(stepMetrics.ratings.lcp)}`} />
                            <span className="text-[10px] text-muted-foreground">
                              LCP: {formatMs(stepMetrics.lcp)}
                            </span>
                            <div className={`w-1.5 h-1.5 rounded-full ${getRatingDot(stepMetrics.ratings.fcp)}`} />
                            <span className="text-[10px] text-muted-foreground">
                              FCP: {formatMs(stepMetrics.fcp)}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Metrics View */}
              {showMetrics && (
                <div className="space-y-4">
                  {metrics.length === 0 ? (
                    <div className="text-center py-12">
                      <Gauge className="w-10 h-10 mx-auto mb-3 text-muted-foreground/20" />
                      <p className="text-sm text-muted-foreground">
                        {runStatus === 'running'
                          ? 'Collecting performance data...'
                          : 'Run a test to see performance metrics'}
                      </p>
                      <p className="text-[10px] text-muted-foreground/70 mt-1">
                        Metrics are captured after each navigation
                      </p>
                    </div>
                  ) : (
                    metrics.map((m, i) => (
                      <div
                        key={i}
                        className="rounded-xl border border-border/50 bg-card/30 overflow-hidden"
                      >
                        {/* URL Header */}
                        <div className="px-4 py-2.5 border-b border-border/30 bg-muted/20">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] h-5">
                              Step {m.step_index + 1}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground truncate flex-1">
                              {m.url}
                            </span>
                          </div>
                        </div>

                        {/* Core Web Vitals */}
                        <div className="p-4">
                          <h4 className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-3">
                            Core Web Vitals
                          </h4>
                          <div className="grid grid-cols-2 gap-2">
                            {/* LCP */}
                            <div className={`p-3 rounded-lg border ${getRatingColor(m.ratings.lcp)}`}>
                              <div className="flex items-center gap-1.5 mb-1">
                                <Eye className="w-3 h-3" />
                                <span className="text-[10px] font-medium">LCP</span>
                              </div>
                              <div className="text-lg font-semibold">{formatMs(m.lcp)}</div>
                              <div className="text-[10px] opacity-70">Largest Contentful Paint</div>
                            </div>

                            {/* FCP */}
                            <div className={`p-3 rounded-lg border ${getRatingColor(m.ratings.fcp)}`}>
                              <div className="flex items-center gap-1.5 mb-1">
                                <Zap className="w-3 h-3" />
                                <span className="text-[10px] font-medium">FCP</span>
                              </div>
                              <div className="text-lg font-semibold">{formatMs(m.fcp)}</div>
                              <div className="text-[10px] opacity-70">First Contentful Paint</div>
                            </div>

                            {/* CLS */}
                            <div className={`p-3 rounded-lg border ${getRatingColor(m.ratings.cls)}`}>
                              <div className="flex items-center gap-1.5 mb-1">
                                <LayoutGrid className="w-3 h-3" />
                                <span className="text-[10px] font-medium">CLS</span>
                              </div>
                              <div className="text-lg font-semibold">{m.cls.toFixed(3)}</div>
                              <div className="text-[10px] opacity-70">Cumulative Layout Shift</div>
                            </div>

                            {/* TTFB */}
                            <div className={`p-3 rounded-lg border ${getRatingColor(m.ratings.ttfb)}`}>
                              <div className="flex items-center gap-1.5 mb-1">
                                <Timer className="w-3 h-3" />
                                <span className="text-[10px] font-medium">TTFB</span>
                              </div>
                              <div className="text-lg font-semibold">{formatMs(m.ttfb)}</div>
                              <div className="text-[10px] opacity-70">Time to First Byte</div>
                            </div>
                          </div>

                          {/* Additional Metrics */}
                          <h4 className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mt-4 mb-2">
                            Page Load Timing
                          </h4>
                          <div className="flex items-center gap-4 text-[10px]">
                            <div>
                              <span className="text-muted-foreground">DOM Ready: </span>
                              <span className="font-medium">{formatMs(m.dom_content_loaded)}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Full Load: </span>
                              <span className="font-medium">{formatMs(m.load)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}

                  {/* Legend */}
                  {metrics.length > 0 && (
                    <div className="px-3 py-2 rounded-lg bg-muted/20 border border-border/30">
                      <div className="text-[10px] text-muted-foreground mb-1.5">Rating Legend</div>
                      <div className="flex items-center gap-4 text-[10px]">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span>Good</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-amber-500" />
                          <span>Needs Improvement</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-red-500" />
                          <span>Poor</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
