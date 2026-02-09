'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Play, RefreshCcw, TriangleAlert, Plus, FileInput, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import {
  apiTestingCollectionsApi,
  apiTestingRunsApi,
  apiTestingRequestsApi,
  ApiCollectionSummary,
  ApiCollectionDetail,
  ApiRequest,
  ApiTestRunSummary,
} from '@/lib/api-testing';
import { Input } from '@/components/ui/input';

const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_DEFAULT_API_TESTING_BASE_URL || 'http://backend:8000';

function toErrorMessage(e: unknown, fallback: string): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') {
    return (e as { message: string }).message;
  }
  return fallback;
}

export default function ApiTestingPage() {
  const [collections, setCollections] = useState<ApiCollectionSummary[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);
  const [selectedCollectionDetail, setSelectedCollectionDetail] =
    useState<ApiCollectionDetail | null>(null);

  const [runs, setRuns] = useState<ApiTestRunSummary[]>([]);

  const [loadingCollections, setLoadingCollections] = useState(false);
  const [loadingCollectionDetail, setLoadingCollectionDetail] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runningCollectionId, setRunningCollectionId] = useState<string | null>(null);

  const [engine, setEngine] = useState<'python' | 'karate'>('python');
  const [error, setError] = useState<string | null>(null);

  // Quick start form state
  const [qsName, setQsName] = useState('Health Check Collection');
  const [qsBaseUrl, setQsBaseUrl] = useState(DEFAULT_BASE_URL);
  const [qsMethod, setQsMethod] = useState<'GET' | 'POST' | 'PUT' | 'DELETE'>('GET');
  const [qsPath, setQsPath] = useState('/health');
  const [creatingQuickStart, setCreatingQuickStart] = useState(false);

  // Add request form
  const [newReqMethod, setNewReqMethod] = useState<'GET' | 'POST' | 'PUT' | 'DELETE'>('GET');
  const [newReqPath, setNewReqPath] = useState('');
  const [newReqName, setNewReqName] = useState('');
  const [creatingRequest, setCreatingRequest] = useState(false);

  // Import state
  const [postmanFile, setPostmanFile] = useState<File | null>(null);
  const [openApiFile, setOpenApiFile] = useState<File | null>(null);
  const [importingPostman, setImportingPostman] = useState(false);
  const [importingOpenApi, setImportingOpenApi] = useState(false);

  const requests: ApiRequest[] = useMemo(
    () => selectedCollectionDetail?.requests || [],
    [selectedCollectionDetail],
  );

  const loadCollections = async () => {
    setLoadingCollections(true);
    setError(null);
    try {
      const data = await apiTestingCollectionsApi.list();
      setCollections(data);
      if (!selectedCollectionId && data.length > 0) {
        setSelectedCollectionId(data[0].id);
      }
    } catch (e: unknown) {
      console.error('Failed to load API collections', e);
      setError(toErrorMessage(e, 'Failed to load API collections'));
    } finally {
      setLoadingCollections(false);
    }
  };

  const loadCollectionDetail = async (id: string | null) => {
    if (!id) {
      setSelectedCollectionDetail(null);
      return;
    }
    setLoadingCollectionDetail(true);
    try {
      const detail = await apiTestingCollectionsApi.get(id);
      setSelectedCollectionDetail(detail);
    } catch (e: unknown) {
      console.error('Failed to load collection detail', e);
      setError(toErrorMessage(e, 'Failed to load collection detail'));
      setSelectedCollectionDetail(null);
    } finally {
      setLoadingCollectionDetail(false);
    }
  };

  const loadRuns = async () => {
    setLoadingRuns(true);
    try {
      const data = await apiTestingRunsApi.list();
      setRuns(data);
    } catch (e) {
      console.error('Failed to load API test runs', e);
    } finally {
      setLoadingRuns(false);
    }
  };

  useEffect(() => {
    void (async () => {
      await loadCollections();
      await loadRuns();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedCollectionId) {
      void loadCollectionDetail(selectedCollectionId);
    }
  }, [selectedCollectionId]);

  const runCollection = async (collectionId: string) => {
    setRunningCollectionId(collectionId);
    setError(null);
    try {
      await apiTestingRunsApi.executeCollection(collectionId, { engine });
      await loadRuns();
    } catch (e: unknown) {
      console.error('Failed to execute collection', e);
      setError(toErrorMessage(e, 'Failed to execute collection'));
    } finally {
      setRunningCollectionId(null);
    }
  };

  const handleQuickStartCreate = async () => {
    if (!qsPath.trim()) {
      setError('URL path is required for Quick Start.');
      return;
    }
    setCreatingQuickStart(true);
    setError(null);
    try {
      const collection = await apiTestingCollectionsApi.create({
        name: qsName || 'Quick Collection',
        base_url: qsBaseUrl || undefined,
        default_engine: 'python',
      });

      await apiTestingRequestsApi.create({
        collection_id: collection.id,
        name: `${qsMethod} ${qsPath}`,
        method: qsMethod,
        url_path: qsPath,
        assertions: [
          {
            type: 'status',
            name: 'Status is 200',
            config: { expected: 200, operator: 'equals' },
          },
        ],
      });

      await loadCollections();
      setSelectedCollectionId(collection.id);
      await loadCollectionDetail(collection.id);
    } catch (e: unknown) {
      console.error('Failed to create quick start collection', e);
      setError(toErrorMessage(e, 'Failed to create collection'));
    } finally {
      setCreatingQuickStart(false);
    }
  };

  const handleAddRequest = async () => {
    if (!selectedCollectionId) return;
    if (!newReqPath.trim()) {
      setError('URL path is required for new request.');
      return;
    }
    setCreatingRequest(true);
    setError(null);
    try {
      const orderIndex = requests.length;
      await apiTestingRequestsApi.create({
        collection_id: selectedCollectionId,
        name: newReqName || `${newReqMethod} ${newReqPath}`,
        method: newReqMethod,
        url_path: newReqPath,
        order_index: orderIndex,
      });
      setNewReqName('');
      setNewReqPath('');
      await loadCollectionDetail(selectedCollectionId);
      await loadCollections();
    } catch (e: unknown) {
      console.error('Failed to create request', e);
      setError(toErrorMessage(e, 'Failed to create request'));
    } finally {
      setCreatingRequest(false);
    }
  };

  const handleImportPostman = async () => {
    if (!postmanFile) return;
    setImportingPostman(true);
    setError(null);
    try {
      const col = await apiTestingCollectionsApi.importPostman(postmanFile);
      setPostmanFile(null);
      await loadCollections();
      setSelectedCollectionId(col.id);
      await loadCollectionDetail(col.id);
    } catch (e: unknown) {
      console.error('Failed to import Postman collection', e);
      setError(toErrorMessage(e, 'Failed to import Postman collection'));
    } finally {
      setImportingPostman(false);
    }
  };

  const handleImportOpenApi = async () => {
    if (!openApiFile) return;
    setImportingOpenApi(true);
    setError(null);
    try {
      const col = await apiTestingCollectionsApi.importOpenApi(openApiFile, true);
      setOpenApiFile(null);
      await loadCollections();
      setSelectedCollectionId(col.id);
      await loadCollectionDetail(col.id);
    } catch (e: unknown) {
      console.error('Failed to import OpenAPI spec', e);
      setError(toErrorMessage(e, 'Failed to import OpenAPI spec'));
    } finally {
      setImportingOpenApi(false);
    }
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
              <h1 className="text-xl font-semibold">API Testing</h1>
              <p className="text-sm text-muted-foreground">
                Create API collections and run them with the Python engine or Karate engine backed by
                your existing backend services.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as 'python' | 'karate')}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="python">Python engine</option>
              <option value="karate">Karate engine</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void loadCollections();
                void loadRuns();
              }}
            >
              <RefreshCcw className="w-4 h-4 mr-1" />
              Refresh
            </Button>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <div className="flex flex-col gap-6 p-4 md:p-6">

      {error && (
        <Card className="border-destructive/40 bg-destructive/5 p-3 flex items-start gap-2 text-sm text-destructive">
          <TriangleAlert className="w-4 h-4 mt-0.5" />
          <div>{error}</div>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-[minmax(0,2.5fr)_minmax(0,3fr)]">
        <div className="flex flex-col gap-4">
          {/* Quick Start */}
          <Card className="p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-medium">Quick Start</h2>
                <p className="text-xs text-muted-foreground">
                  Create a simple collection and first request in one step.
                </p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">
                  Collection name
                </label>
                <Input
                  value={qsName}
                  onChange={(e) => setQsName(e.target.value)}
                  placeholder="Collection name"
                  className="h-8 text-xs"
                />
                <label className="text-xs font-medium text-muted-foreground">
                  Base URL
                  <span className="ml-1 text-[10px] text-muted-foreground">
                    (inside Docker, defaults to backend service)
                  </span>
                </label>
                <Input
                  value={qsBaseUrl}
                  onChange={(e) => setQsBaseUrl(e.target.value)}
                  placeholder="http://backend:8000"
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">First request</label>
                <div className="flex gap-2">
                  <select
                    value={qsMethod}
                    onChange={(e) =>
                      setQsMethod(e.target.value as 'GET' | 'POST' | 'PUT' | 'DELETE')
                    }
                    className="h-8 w-20 rounded-md border border-input bg-background px-2 text-xs"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                  <Input
                    value={qsPath}
                    onChange={(e) => setQsPath(e.target.value)}
                    placeholder="/health"
                    className="h-8 text-xs flex-1"
                  />
                </div>
                <div className="flex justify-end pt-2">
                  <Button
                    size="sm"
                    className="gap-1.5 h-8 text-xs"
                    onClick={handleQuickStartCreate}
                    disabled={creatingQuickStart}
                  >
                    {creatingQuickStart ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <Plus className="w-3 h-3" />
                        Create Collection + Request
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* Collections and Requests */}
          <Card className="p-4 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">API Collections</h2>
              <span className="text-xs text-muted-foreground">
                {loadingCollections ? 'Loading…' : `${collections.length} collections`}
              </span>
            </div>

            <div className="flex flex-col gap-3 md:flex-row md:gap-4">
              <div className="md:w-1/2 space-y-2 max-h-[320px] overflow-y-auto pr-1">
                {collections.length === 0 && !loadingCollections && (
                  <p className="text-xs text-muted-foreground">
                    No API collections yet. Use Quick Start above or import from Postman/OpenAPI.
                  </p>
                )}
                {collections.map((c) => {
                  const isSelected = c.id === selectedCollectionId;
                  return (
                    <div
                      key={c.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedCollectionId(c.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedCollectionId(c.id);
                        }
                      }}
                      className={`w-full text-left rounded-md border px-3 py-2 text-xs transition-all cursor-pointer ${
                        isSelected
                          ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                          : 'border-border/60 bg-card/40 hover:bg-card/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium truncate text-sm">{c.name}</span>
                            <Badge variant="outline" className="text-[10px] capitalize">
                              {c.default_engine}
                            </Badge>
                          </div>
                          {c.description && (
                            <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                              {c.description}
                            </p>
                          )}
                          <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground mt-1">
                            {typeof c.request_count === 'number' && (
                              <span>{c.request_count} req</span>
                            )}
                            {typeof c.environment_count === 'number' && (
                              <span>• {c.environment_count} env</span>
                            )}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="default"
                          className="h-7 text-[11px] px-2 flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            void runCollection(c.id);
                          }}
                          disabled={runningCollectionId === c.id}
                        >
                          <Play className="w-3 h-3 mr-1" />
                          {runningCollectionId === c.id ? 'Running…' : 'Run'}
                        </Button>
                      </div>
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        Engine: <span className="font-medium capitalize">{engine}</span>
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Requests for selected collection */}
              <div className="md:w-1/2 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-medium text-muted-foreground">
                    Requests {selectedCollectionDetail ? `in ${selectedCollectionDetail.name}` : ''}
                  </h3>
                  <span className="text-[10px] text-muted-foreground">
                    {loadingCollectionDetail
                      ? 'Loading…'
                      : `${requests.length} request${requests.length === 1 ? '' : 's'}`}
                  </span>
                </div>

                <div className="space-y-1 max-h-[260px] overflow-y-auto pr-1">
                  {requests.length === 0 && !loadingCollectionDetail && (
                    <p className="text-[11px] text-muted-foreground">
                      No requests yet. Add one below.
                    </p>
                  )}
                  {requests.map((r) => (
                    <div
                      key={r.id}
                      className="flex items-start justify-between gap-2 rounded-md border border-border/60 bg-card/40 px-2 py-2 text-[11px]"
                    >
                      <div className="min-w-0 space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">
                            {r.method}
                          </span>
                          <span className="font-medium truncate">{r.name}</span>
                        </div>
                        <p className="font-mono text-[11px] text-muted-foreground truncate">
                          {r.url_path}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Add request form */}
                <div className="pt-2 border-t border-border/40 mt-1 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      Add request to collection
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <select
                      value={newReqMethod}
                      onChange={(e) =>
                        setNewReqMethod(e.target.value as 'GET' | 'POST' | 'PUT' | 'DELETE')
                      }
                      className="h-8 w-20 rounded-md border border-input bg-background px-2 text-xs"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                    <Input
                      value={newReqPath}
                      onChange={(e) => setNewReqPath(e.target.value)}
                      placeholder="/path"
                      className="h-8 text-xs flex-1"
                    />
                  </div>
                  <Input
                    value={newReqName}
                    onChange={(e) => setNewReqName(e.target.value)}
                    placeholder="Optional request name"
                    className="h-8 text-xs"
                  />
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      className="h-8 text-xs gap-1.5"
                      onClick={handleAddRequest}
                      disabled={creatingRequest || !selectedCollectionId}
                    >
                      {creatingRequest ? (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Adding...
                        </>
                      ) : (
                        <>
                          <Plus className="w-3 h-3" />
                          Add Request
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Imports */}
          <Card className="p-4 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">Import Collections</h2>
              <span className="text-xs text-muted-foreground">
                Use existing Postman or OpenAPI definitions.
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <FileInput className="w-3 h-3" />
                  Postman collection (JSON)
                </div>
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    setPostmanFile(file);
                  }}
                  className="block w-full text-xs text-muted-foreground file:mr-2 file:px-2 file:py-1 file:text-xs file:border-0 file:rounded-md file:bg-muted file:text-foreground"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs gap-1.5"
                  onClick={handleImportPostman}
                  disabled={!postmanFile || importingPostman}
                >
                  {importingPostman ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Plus className="w-3 h-3" />
                      Import Postman
                    </>
                  )}
                </Button>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <FileInput className="w-3 h-3" />
                  OpenAPI / Swagger (JSON or YAML)
                </div>
                <input
                  type="file"
                  accept=".json,.yaml,.yml,application/json,application/x-yaml,text/yaml"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    setOpenApiFile(file);
                  }}
                  className="block w-full text-xs text-muted-foreground file:mr-2 file:px-2 file:py-1 file:text-xs file:border-0 file:rounded-md file:bg-muted file:text-foreground"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs gap-1.5"
                  onClick={handleImportOpenApi}
                  disabled={!openApiFile || importingOpenApi}
                >
                  {importingOpenApi ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Plus className="w-3 h-3" />
                      Import OpenAPI
                    </>
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Runs panel */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Recent API Test Runs</h2>
            <span className="text-xs text-muted-foreground">
              {loadingRuns ? 'Loading…' : `${runs.length} runs`}
            </span>
          </div>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {runs.length === 0 && !loadingRuns && (
              <p className="text-xs text-muted-foreground">
                No runs yet. Execute a collection on the left to see results here.
              </p>
            )}
            {runs.map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-card/40 p-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">
                      {run.name || run.collection_name || 'Unnamed run'}
                    </p>
                    <Badge variant="outline" className="text-[10px] capitalize">
                      {run.engine}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                    {run.collection_name && <span>{run.collection_name}</span>}
                    <span>• {run.status}</span>
                    {typeof run.total_requests === 'number' && (
                      <span>• {run.total_requests} req</span>
                    )}
                    {typeof run.passed_requests === 'number' &&
                      typeof run.failed_requests === 'number' && (
                        <span>
                          • {run.passed_requests} passed / {run.failed_requests} failed
                        </span>
                      )}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-[10px] text-muted-foreground">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : ''}
                  </span>
                  <Link
                    href={`/api-testing/runs/${run.id}`}
                    className="text-[10px] text-primary hover:underline"
                  >
                    View details
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
            <div className="flex justify-end">
              <Link href="/api-testing/runs" className="text-xs text-primary hover:underline">
                View all API runs
              </Link>
            </div>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}


