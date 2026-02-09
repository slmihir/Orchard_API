'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Clock,
  Plus,
  RefreshCw,
  Trash2,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  Calendar,
  MoreHorizontal,
  Folder,
  FileText,
  History,
  ChevronRight,
  ArrowLeft,
  Timer,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { useAuthStore } from '@/stores/authStore';
import { schedulesApi, testsApi, collectionsApi, ScheduleResponse, ScheduleRunResponse, TestResponse, CollectionResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

function formatNextRun(dateString?: string): string {
  if (!dateString) return 'Not scheduled';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 0) return 'Overdue';
  if (diffMins < 60) return `In ${diffMins}m`;
  if (diffHours < 24) return `In ${diffHours}h`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatFrequency(schedule: ScheduleResponse): string {
  const hour = schedule.run_at_hour ?? 9;
  const minute = schedule.run_at_minute ?? 0;
  const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;

  switch (schedule.frequency) {
    case 'hourly':
      return `Every hour at :${minute.toString().padStart(2, '0')}`;
    case 'daily':
      return `Daily at ${timeStr}`;
    case 'weekly':
      const days = schedule.run_on_days?.split(',').map(d => {
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        return dayNames[parseInt(d) % 7];
      }).join(', ');
      return `Weekly (${days}) at ${timeStr}`;
    default:
      return schedule.frequency;
  }
}

export default function SchedulesPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [tests, setTests] = useState<TestResponse[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  // Form state
  const [formName, setFormName] = useState('');
  const [formTargetType, setFormTargetType] = useState<'test' | 'collection'>('test');
  const [formTestId, setFormTestId] = useState('');
  const [formCollectionId, setFormCollectionId] = useState('');
  const [formFrequency, setFormFrequency] = useState('daily');
  const [formHour, setFormHour] = useState(9);
  const [formMinute, setFormMinute] = useState(0);
  const [formDays, setFormDays] = useState('1,2,3,4,5');

  // Run history state
  const [showHistorySheet, setShowHistorySheet] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState<ScheduleResponse | null>(null);
  const [scheduleRuns, setScheduleRuns] = useState<ScheduleRunResponse[]>([]);
  const [selectedRun, setSelectedRun] = useState<ScheduleRunResponse | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

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
      const [schedulesData, testsData, collectionsData] = await Promise.all([
        schedulesApi.list(),
        testsApi.list(),
        collectionsApi.list(),
      ]);
      setSchedules(schedulesData);
      setTests(testsData);
      setCollections(collectionsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSchedule = async () => {
    if (!formName) return;
    if (formTargetType === 'test' && !formTestId) return;
    if (formTargetType === 'collection' && !formCollectionId) return;

    try {
      await schedulesApi.create({
        name: formName,
        test_id: formTargetType === 'test' ? formTestId : undefined,
        collection_id: formTargetType === 'collection' ? formCollectionId : undefined,
        frequency: formFrequency,
        run_at_hour: formHour,
        run_at_minute: formMinute,
        run_on_days: formFrequency === 'weekly' ? formDays : undefined,
      });

      setShowCreateDialog(false);
      resetForm();
      loadData();
    } catch (error) {
      console.error('Failed to create schedule:', error);
    }
  };

  const handleToggle = async (id: string) => {
    try {
      await schedulesApi.toggle(id);
      loadData();
    } catch (error) {
      console.error('Failed to toggle schedule:', error);
    }
  };

  const handleRunNow = async (id: string) => {
    try {
      await schedulesApi.runNow(id);
      // Refresh after a short delay to show updated status
      setTimeout(() => loadData(), 2000);
    } catch (error) {
      console.error('Failed to run schedule:', error);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this schedule?')) return;

    try {
      await schedulesApi.delete(id);
      loadData();
    } catch (error) {
      console.error('Failed to delete schedule:', error);
    }
  };

  const resetForm = () => {
    setFormName('');
    setFormTargetType('test');
    setFormTestId('');
    setFormCollectionId('');
    setFormFrequency('daily');
    setFormHour(9);
    setFormMinute(0);
    setFormDays('1,2,3,4,5');
  };

  const openRunHistory = async (schedule: ScheduleResponse) => {
    setSelectedSchedule(schedule);
    setSelectedRun(null);
    setShowHistorySheet(true);
    setLoadingHistory(true);

    try {
      const runs = await schedulesApi.getRuns(schedule.id);
      setScheduleRuns(runs);
    } catch (error) {
      console.error('Failed to load run history:', error);
      setScheduleRuns([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const viewRunDetail = async (run: ScheduleRunResponse) => {
    if (!selectedSchedule) return;

    setLoadingHistory(true);
    try {
      const detail = await schedulesApi.getRunDetail(selectedSchedule.id, run.id);
      setSelectedRun(detail);
    } catch (error) {
      console.error('Failed to load run detail:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const formatDuration = (ms?: number): string => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatRunTime = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const isFormValid = formName && (
    (formTargetType === 'test' && formTestId) ||
    (formTargetType === 'collection' && formCollectionId)
  );

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
              <h1 className="text-xl font-semibold">Schedules</h1>
              <p className="text-sm text-muted-foreground">Automated recurring test runs</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={loadData}>
              <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setShowCreateDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              New Schedule
            </Button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : schedules.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <Clock className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">No schedules yet</p>
              <p className="text-sm mt-1">Create a schedule to run tests automatically</p>
              <Button className="mt-4" onClick={() => setShowCreateDialog(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Schedule
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {schedules.map((schedule) => (
                <Card key={schedule.id} className={cn(!schedule.enabled && 'opacity-60')}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-base truncate">{schedule.name}</CardTitle>
                        <CardDescription className="truncate flex items-center gap-1.5">
                          {schedule.target_type === 'collection' ? (
                            <>
                              <Folder className="w-3 h-3" />
                              {schedule.collection_name}
                            </>
                          ) : (
                            <>
                              <FileText className="w-3 h-3" />
                              {schedule.test_name}
                            </>
                          )}
                        </CardDescription>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={(props) => (
                            <button {...props} className="p-1 hover:bg-muted rounded">
                              <MoreHorizontal className="w-4 h-4" />
                            </button>
                          )}
                        />
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openRunHistory(schedule)}>
                            <History className="w-4 h-4 mr-2" />
                            Run History
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleRunNow(schedule.id)}>
                            <Play className="w-4 h-4 mr-2" />
                            Run Now
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleToggle(schedule.id)}>
                            {schedule.enabled ? (
                              <>
                                <Pause className="w-4 h-4 mr-2" />
                                Disable
                              </>
                            ) : (
                              <>
                                <Play className="w-4 h-4 mr-2" />
                                Enable
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDelete(schedule.id)}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2 text-sm">
                      <Calendar className="w-4 h-4 text-muted-foreground" />
                      <span>{formatFrequency(schedule)}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="text-sm">
                        <span className="text-muted-foreground">Next run: </span>
                        <span className={schedule.enabled ? 'text-foreground' : 'text-muted-foreground'}>
                          {schedule.enabled ? formatNextRun(schedule.next_run_at) : 'Disabled'}
                        </span>
                      </div>
                      <Badge variant={schedule.enabled ? 'default' : 'secondary'}>
                        {schedule.enabled ? 'Active' : 'Paused'}
                      </Badge>
                    </div>

                    {schedule.last_run_at && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        {schedule.last_run_status === 'passed' ? (
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        ) : schedule.last_run_status === 'failed' ? (
                          <XCircle className="w-4 h-4 text-red-500" />
                        ) : (
                          <Clock className="w-4 h-4" />
                        )}
                        <span>
                          Last run: {new Date(schedule.last_run_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </main>
      </SidebarInset>

      {/* Create Schedule Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create Schedule</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Schedule Name</label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g., Daily Login Tests"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Run</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setFormTargetType('test')}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors',
                    formTargetType === 'test'
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-input hover:bg-muted'
                  )}
                >
                  <FileText className="w-4 h-4" />
                  Single Test
                </button>
                <button
                  onClick={() => setFormTargetType('collection')}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors',
                    formTargetType === 'collection'
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-input hover:bg-muted'
                  )}
                >
                  <Folder className="w-4 h-4" />
                  Collection
                </button>
              </div>
            </div>

            {formTargetType === 'test' ? (
              <div className="space-y-2">
                <label className="text-sm font-medium">Test to Run</label>
                <select
                  value={formTestId}
                  onChange={(e) => setFormTestId(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Select a test...</option>
                  {tests.map((test) => (
                    <option key={test.id} value={test.id}>
                      {test.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm font-medium">Collection to Run</label>
                <select
                  value={formCollectionId}
                  onChange={(e) => setFormCollectionId(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Select a collection...</option>
                  {collections.map((collection) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name} ({collection.test_count} tests)
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">Frequency</label>
              <select
                value={formFrequency}
                onChange={(e) => setFormFrequency(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>

            {formFrequency !== 'hourly' && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Run at Time</label>
                <div className="flex gap-2">
                  <select
                    value={formHour}
                    onChange={(e) => setFormHour(parseInt(e.target.value))}
                    className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>
                        {i.toString().padStart(2, '0')}
                      </option>
                    ))}
                  </select>
                  <span className="flex items-center">:</span>
                  <select
                    value={formMinute}
                    onChange={(e) => setFormMinute(parseInt(e.target.value))}
                    className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
                  >
                    {[0, 15, 30, 45].map((m) => (
                      <option key={m} value={m}>
                        {m.toString().padStart(2, '0')}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {formFrequency === 'weekly' && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Run on Days</label>
                <div className="flex gap-1 flex-wrap">
                  {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day, index) => {
                    const isSelected = formDays.split(',').includes(index.toString());
                    return (
                      <button
                        key={day}
                        onClick={() => {
                          const days = formDays.split(',').filter(d => d);
                          if (isSelected) {
                            setFormDays(days.filter(d => d !== index.toString()).join(','));
                          } else {
                            setFormDays([...days, index.toString()].sort().join(','));
                          }
                        }}
                        className={cn(
                          'px-3 py-1 text-xs rounded-md border transition-colors',
                          isSelected
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'border-input hover:bg-muted'
                        )}
                      >
                        {day}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateSchedule} disabled={!isFormValid}>
              Create Schedule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run History Sheet */}
      <Sheet open={showHistorySheet} onOpenChange={setShowHistorySheet}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader className="space-y-1">
            {selectedRun ? (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setSelectedRun(null)}
                >
                  <ArrowLeft className="w-4 h-4" />
                </Button>
                <div>
                  <SheetTitle className="text-left">Run Details</SheetTitle>
                  <p className="text-sm text-muted-foreground">
                    {formatRunTime(selectedRun.started_at)}
                  </p>
                </div>
              </div>
            ) : (
              <>
                <SheetTitle className="text-left">Run History</SheetTitle>
                <p className="text-sm text-muted-foreground">
                  {selectedSchedule?.name}
                </p>
              </>
            )}
          </SheetHeader>

          <div className="mt-6">
            {loadingHistory ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : selectedRun ? (
              // Run Detail View
              <div className="space-y-6">
                {/* Summary */}
                <div className="p-4 rounded-lg bg-muted/50 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Status</span>
                    <Badge
                      variant={selectedRun.status === 'passed' ? 'default' : 'destructive'}
                      className={cn(
                        selectedRun.status === 'passed' && 'bg-green-500/10 text-green-500 hover:bg-green-500/20'
                      )}
                    >
                      {selectedRun.status}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Duration</span>
                    <span className="text-sm font-medium">{formatDuration(selectedRun.duration_ms)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Tests</span>
                    <span className="text-sm font-medium">
                      <span className="text-green-500">{selectedRun.passed_tests}</span>
                      {' / '}
                      <span className={selectedRun.failed_tests > 0 ? 'text-red-500' : ''}>{selectedRun.total_tests}</span>
                    </span>
                  </div>
                </div>

                {selectedRun.error_message && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <p className="text-sm text-red-400">{selectedRun.error_message}</p>
                  </div>
                )}

                {/* Test Results */}
                {selectedRun.test_runs && selectedRun.test_runs.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-medium">Test Results</h3>
                    <div className="space-y-2">
                      {selectedRun.test_runs.map((testRun) => (
                        <div
                          key={testRun.id}
                          className="flex items-center justify-between p-3 rounded-lg border bg-card"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            {testRun.status === 'passed' ? (
                              <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                            )}
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">{testRun.test_name}</p>
                              {testRun.error_message && (
                                <p className="text-xs text-red-400 truncate">{testRun.error_message}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
                            <Timer className="w-3 h-3" />
                            {formatDuration(testRun.duration_ms)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : scheduleRuns.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <History className="w-10 h-10 mb-3 opacity-50" />
                <p className="text-sm">No runs yet</p>
                <p className="text-xs mt-1">Run this schedule to see history</p>
              </div>
            ) : (
              // Run History List
              <div className="space-y-2">
                {scheduleRuns.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => viewRunDetail(run)}
                    className="w-full flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {run.status === 'passed' ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
                      ) : run.status === 'running' ? (
                        <RefreshCw className="w-5 h-5 text-blue-500 animate-spin shrink-0" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500 shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{formatRunTime(run.started_at)}</p>
                        <p className="text-xs text-muted-foreground">
                          {run.passed_tests}/{run.total_tests} tests passed
                          {run.duration_ms && ` • ${formatDuration(run.duration_ms)}`}
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </SidebarProvider>
  );
}
