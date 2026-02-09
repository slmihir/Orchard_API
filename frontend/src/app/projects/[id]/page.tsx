'use client';

import { useState, useEffect, useRef, use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  ArrowLeft,
  Loader2,
  Globe,
  LayoutGrid,
  Sparkles,
  Layers,
  Play,
  RefreshCw,
  List,
  X,
  PanelRightOpen,
  Lock,
  Unlock,
  FileText,
  MousePointer,
  Table2,
  FlaskConical,
  ChevronDown,
  ChevronRight,
  Shield,
  FormInput,
  Zap,
  Square,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { projectsApi, ProjectDetailResponse, ProjectGraphResponse, GraphNode, TestCaseResponse, TestExecutionWebSocket } from '@/lib/api';
import { useAuthStore, useHasHydrated } from '@/stores/authStore';

// Dynamically import ForceGraph2D - clearer for sitemap visualization
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-background/50">
      <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
    </div>
  ),
});

const NODE_COLORS: Record<string, string> = {
  login: '#ef4444',
  register: '#f97316',
  dashboard: '#3b82f6',
  settings: '#8b5cf6',
  form: '#22c55e',
  form_create: '#22c55e',
  form_edit: '#14b8a6',
  list: '#06b6d4',
  detail: '#6366f1',
  landing: '#ec4899',
  page: '#64748b',
};

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const hasHydrated = useHasHydrated();

  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [graphData, setGraphData] = useState<ProjectGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('graph');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [testCases, setTestCases] = useState<TestCaseResponse[]>([]);
  const [loadingTests, setLoadingTests] = useState(false);
  const [generatingTests, setGeneratingTests] = useState(false);

  // Test execution state
  const [executingTest, setExecutingTest] = useState<TestCaseResponse | null>(null);
  const [executionStatus, setExecutionStatus] = useState<string>('');
  const [executionScreenshot, setExecutionScreenshot] = useState<string | null>(null);
  const [executionSteps, setExecutionSteps] = useState<any[]>([]);
  const [executionResult, setExecutionResult] = useState<{success: boolean; message: string; duration?: number} | null>(null);
  const wsRef = useRef<TestExecutionWebSocket | null>(null);

  const toggleNodeExpanded = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const fetchTests = async () => {
    if (!projectId) return;
    setLoadingTests(true);
    try {
      const tests = await projectsApi.getTests(projectId);
      setTestCases(tests);
    } catch (error) {
      console.error('Failed to fetch tests:', error);
    } finally {
      setLoadingTests(false);
    }
  };

  const handleGenerateAllTests = async () => {
    if (!projectId) return;
    setGeneratingTests(true);
    try {
      const newTests = await projectsApi.generateAllTests(projectId);
      setTestCases((prev) => [...newTests, ...prev]);
    } catch (error) {
      console.error('Failed to generate tests:', error);
    } finally {
      setGeneratingTests(false);
    }
  };

  const handleCreateTestFromScenario = async (pageId: string, scenario: string): Promise<TestCaseResponse | null> => {
    if (!projectId) return null;
    try {
      const newTest = await projectsApi.createTestFromScenario(projectId, {
        page_id: pageId,
        scenario,
      });
      setTestCases((prev) => [newTest, ...prev]);
      return newTest;
    } catch (error) {
      console.error('Failed to create test:', error);
      return null;
    }
  };

  const handleRunScenario = async (pageId: string, scenario: string) => {
    if (!projectId) return;

    let test = testCases.find(
      (t) => t.page_id === pageId && t.description === scenario
    );

    if (!test) {
      test = await handleCreateTestFromScenario(pageId, scenario);
    }

    if (test) {
      handleRunTest(test);
    }
  };

  const handleDeleteTest = async (testId: string) => {
    if (!projectId) return;
    try {
      await projectsApi.deleteTest(projectId, testId);
      setTestCases((prev) => prev.filter((t) => t.id !== testId));
    } catch (error) {
      console.error('Failed to delete test:', error);
    }
  };

  const handleRunTest = async (test: TestCaseResponse) => {
    setExecutingTest(test);
    setExecutionStatus('connecting');
    setExecutionScreenshot(null);
    setExecutionSteps([]);
    setExecutionResult(null);

    try {
      const ws = new TestExecutionWebSocket(test.id);
      wsRef.current = ws;

      ws.on('status', (data: any) => {
        setExecutionStatus(data.status);
      });

      ws.on('screenshot', (data: any) => {
        setExecutionScreenshot(data.image);
      });

      ws.on('action', (data: any) => {
        setExecutionSteps((prev) => [...prev, data]);
      });

      ws.on('complete', (data: any) => {
        setExecutionResult({
          success: data.success,
          message: data.message,
          duration: data.duration,
        });
        setExecutionStatus('complete');
        setTestCases((prev) =>
          prev.map((t) =>
            t.id === test.id
              ? {
                  ...t,
                  status: data.status,
                  last_run_status: data.status,
                  last_run_at: new Date().toISOString(),
                  last_run_duration: data.duration,
                }
              : t
          )
        );
      });

      ws.on('error', (data: any) => {
        setExecutionResult({
          success: false,
          message: data.message,
        });
        setExecutionStatus('error');
        setTestCases((prev) =>
          prev.map((t) =>
            t.id === test.id
              ? {
                  ...t,
                  status: 'failing',
                  last_run_status: 'failed',
                  last_run_at: new Date().toISOString(),
                }
              : t
          )
        );
      });

      await ws.connect();
      ws.start();
    } catch (error) {
      console.error('Failed to run test:', error);
      setExecutionResult({
        success: false,
        message: String(error),
      });
      setExecutionStatus('error');
    }
  };

  const handleStopTest = () => {
    if (wsRef.current) {
      wsRef.current.stop();
      wsRef.current.disconnect();
      wsRef.current = null;
    }
    setExecutionStatus('stopped');
  };

  const handleCloseExecution = () => {
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
    }
    setExecutingTest(null);
    setExecutionStatus('');
    setExecutionScreenshot(null);
    setExecutionSteps([]);
    setExecutionResult(null);
  };

  useEffect(() => {
    if (project && testCases.length === 0) {
      fetchTests();
    }
  }, [project]);

  const graphRef = useRef<any>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasHydrated) return;

    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    loadProject();
  }, [hasHydrated, isAuthenticated, projectId, router]);

  // Resize graph when selected node changes
  useEffect(() => {
    if (graphRef.current) {
      setTimeout(() => {
        if (graphContainerRef.current && graphRef.current) {
          const { width, height } = graphContainerRef.current.getBoundingClientRect();
          graphRef.current.width(width);
          graphRef.current.height(height);
        }
      }, 100);
    }
  }, [selectedNode]);

  const loadProject = async () => {
    try {
      const [projectData, graph] = await Promise.all([
        projectsApi.get(projectId),
        projectsApi.getGraph(projectId),
      ]);
      setProject(projectData);
      setGraphData(graph);
    } catch (error) {
      console.error('Failed to load project:', error);
    } finally {
      setLoading(false);
    }
  };

  const getNodeColor = (node: any) => {
    if (!node) return '#64748b';
    if (node.isFeature) return '#f59e0b';
    return NODE_COLORS[node.type] || '#64748b';
  };

  const getNodeSize = (node: any) => {
    if (node.isFeature) return 8;
    if (node.depth === 0) return 10;
    return 5;
  };

  if (!hasHydrated) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen w-full overflow-hidden">
        {/* Header */}
        <header className="flex-shrink-0 flex items-center justify-between gap-2 sm:gap-4 px-2 sm:px-4 py-2 sm:py-3 border-b border-border/50 bg-card/30 z-10">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <SidebarTrigger className="-ml-1 flex-shrink-0" />
            <Link href="/projects" className="flex-shrink-0">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="w-4 h-4" />
              </Button>
            </Link>
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div className="hidden sm:flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 flex-shrink-0">
                <Globe className="w-4 h-4 text-primary" />
              </div>
              <div className="min-w-0">
                <h1 className="text-xs sm:text-sm font-semibold truncate">{project?.name || 'Project'}</h1>
                <p className="text-[10px] text-muted-foreground truncate hidden sm:block">
                  {project?.base_url}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
            {project?.status === 'pending' && (
              <Link href={`/projects/${projectId}/discover`}>
                <Button size="sm" className="gap-1 sm:gap-2 text-xs sm:text-sm">
                  <Play className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Start Discovery</span>
                  <span className="sm:hidden">Start</span>
                </Button>
              </Link>
            )}
            {project?.status === 'completed' && (
              <Link href={`/projects/${projectId}/discover`}>
                <Button variant="outline" size="sm" className="gap-1 sm:gap-2 text-xs sm:text-sm">
                  <RefreshCw className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Re-discover</span>
                  <span className="sm:hidden">Redo</span>
                </Button>
              </Link>
            )}
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex min-h-0 overflow-hidden">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Graph / List View */}
              <div
                ref={graphContainerRef}
                className="flex-1 min-w-0 relative overflow-hidden bg-gradient-to-br from-background to-muted/20"
              >
                <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
                  <div className="absolute top-2 sm:top-4 right-2 sm:right-4 z-10">
                    <TabsList className="bg-background/80 backdrop-blur text-xs sm:text-sm">
                      <TabsTrigger value="graph" className="gap-1 sm:gap-2 px-2 sm:px-3">
                        <Globe className="w-3 h-3" />
                        <span className="hidden sm:inline">Graph</span>
                      </TabsTrigger>
                      <TabsTrigger value="list" className="gap-1 sm:gap-2 px-2 sm:px-3">
                        <List className="w-3 h-3" />
                        <span className="hidden sm:inline">List</span>
                      </TabsTrigger>
                      <TabsTrigger value="tests" className="gap-1 sm:gap-2 px-2 sm:px-3">
                        <FlaskConical className="w-3 h-3" />
                        <span className="hidden sm:inline">Tests</span>
                        {testCases.length > 0 && (
                          <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">
                            {testCases.length}
                          </Badge>
                        )}
                      </TabsTrigger>
                    </TabsList>
                  </div>

                  <TabsContent value="graph" className="flex-1 m-0 relative">
                    {graphData && graphData.nodes.length > 0 ? (
                      <div className="absolute inset-0">
                        <ForceGraph2D
                          ref={graphRef}
                          graphData={graphData}
                          nodeId="id"
                          nodeLabel={(node: any) => `${node.title || 'Page'} - ${node.path || ''}`}
                          nodeColor={getNodeColor}
                          nodeRelSize={6}
                          nodeVal={getNodeSize}
                          linkDirectionalParticles={2}
                          linkDirectionalParticleSpeed={0.01}
                          linkColor={() => '#ffffff66'}
                          linkWidth={1.5}
                          backgroundColor="#0a0a0a"
                          d3AlphaDecay={0.005}
                          d3VelocityDecay={0.1}
                          warmupTicks={300}
                          cooldownTicks={1000}
                          d3Force={(forceName: string, force: any) => {
                            if (forceName === 'charge') {
                              force.strength(-5000);
                            }
                            if (forceName === 'link') {
                              force.distance(300).strength(0.3);
                            }
                          }}
                          enableNodeDrag={true}
                          onEngineStop={() => {
                            if (graphRef.current) {
                              graphRef.current.zoomToFit(400, 40);
                            }
                          }}
                          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                            // Use path for label (more unique than title)
                            const label = node.path || node.title || 'Page';
                            const displayLabel = label === '/' ? 'Home' : label.split('/').pop() || label;
                            const fontSize = Math.max(11 / globalScale, 2.5);
                            const nodeSize = getNodeSize(node) * 2;

                            // Draw node circle with border
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
                            ctx.fillStyle = getNodeColor(node);
                            ctx.fill();
                            ctx.strokeStyle = '#ffffff33';
                            ctx.lineWidth = 1;
                            ctx.stroke();

                            // Draw label with background
                            ctx.font = `bold ${fontSize}px Sans-Serif`;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';

                            const textWidth = ctx.measureText(displayLabel.slice(0, 15)).width;
                            const padding = 2;
                            ctx.fillStyle = '#000000aa';
                            ctx.fillRect(
                              node.x - textWidth / 2 - padding,
                              node.y + nodeSize + fontSize / 2 - padding,
                              textWidth + padding * 2,
                              fontSize + padding * 2
                            );

                            ctx.fillStyle = '#ffffff';
                            ctx.fillText(displayLabel.slice(0, 15), node.x, node.y + nodeSize + fontSize + padding);
                          }}
                          nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                            const nodeSize = getNodeSize(node) * 2;
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, nodeSize + 5, 0, 2 * Math.PI);
                            ctx.fillStyle = color;
                            ctx.fill();
                          }}
                          onNodeClick={(node: any) => setSelectedNode(node)}
                        />
                      </div>
                    ) : (
                      <div className="absolute inset-0 flex flex-col items-center justify-center p-4">
                        <Globe className="w-12 h-12 sm:w-16 sm:h-16 text-muted-foreground/20 mb-4" />
                        <h3 className="text-base sm:text-lg font-medium mb-2">No Data Yet</h3>
                        <p className="text-xs sm:text-sm text-muted-foreground mb-6 text-center max-w-xs">
                          Run discovery to explore this project
                        </p>
                        <Link href={`/projects/${projectId}/discover`}>
                          <Button className="gap-2">
                            <Play className="w-4 h-4" />
                            Start Discovery
                          </Button>
                        </Link>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="list" className="flex-1 m-0 overflow-auto p-4 sm:p-6">
                    <div className="max-w-4xl mx-auto">
                      {/* Simple list */}
                      <div className="divide-y divide-border/50">
                        {graphData?.nodes.map((node) => {
                          const isExpanded = expandedNodes.has(node.id);
                          const analysis = node.llmAnalysis;
                          const hasRichData = analysis || node.testScenarios?.length;
                          const nodeColor = NODE_COLORS[node.type] || '#64748b';

                          return (
                            <div key={node.id} className="py-4 first:pt-0">
                              {/* Row */}
                              <div
                                className={`flex items-start gap-4 ${hasRichData ? 'cursor-pointer' : ''}`}
                                onClick={() => hasRichData && toggleNodeExpanded(node.id)}
                              >
                                {/* Color dot */}
                                <div
                                  className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                                  style={{ backgroundColor: nodeColor }}
                                />

                                {/* Main content */}
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-medium text-sm truncate">{node.title}</span>
                                    {node.requiresAuth && (
                                      <Lock className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                    )}
                                  </div>
                                  <div className="font-mono-custom text-xs text-muted-foreground truncate">
                                    {node.path}
                                  </div>

                                  {/* Tags row */}
                                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                                    <span
                                      className="text-[11px] px-2 py-0.5 rounded-md font-medium"
                                      style={{ backgroundColor: `${nodeColor}18`, color: nodeColor }}
                                    >
                                      {node.type?.replace('_', ' ')}
                                    </span>

                                    {analysis?.forms && analysis.forms.length > 0 && (
                                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                                        {analysis.forms.length} form{analysis.forms.length > 1 ? 's' : ''}
                                      </span>
                                    )}

                                    {analysis?.tables && analysis.tables.length > 0 && (
                                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                                        {analysis.tables.length} table{analysis.tables.length > 1 ? 's' : ''}
                                      </span>
                                    )}

                                    {analysis?.actions && analysis.actions.length > 0 && (
                                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                                        {analysis.actions.length} action{analysis.actions.length > 1 ? 's' : ''}
                                      </span>
                                    )}

                                    {node.testScenarios && node.testScenarios.length > 0 && (
                                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                                        {node.testScenarios.length} test{node.testScenarios.length > 1 ? 's' : ''}
                                      </span>
                                    )}
                                  </div>

                                  {/* Description */}
                                  {analysis?.page_description && !isExpanded && (
                                    <p className="text-xs text-muted-foreground mt-2 line-clamp-1">
                                      {analysis.page_description}
                                    </p>
                                  )}
                                </div>

                                {/* Right side */}
                                <div className="flex items-center gap-3 flex-shrink-0">
                                  <span className="text-xs text-muted-foreground hidden sm:block">
                                    depth {node.depth}
                                  </span>
                                  {hasRichData && (
                                    <ChevronDown
                                      className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                    />
                                  )}
                                </div>
                              </div>

                              {/* Expanded details */}
                              {isExpanded && hasRichData && (
                                <div className="mt-4 ml-6 border-l-2 border-border/50 pl-4">
                                  {/* Description */}
                                  {analysis?.page_description && (
                                    <p className="text-sm text-muted-foreground mb-4">
                                      {analysis.page_description}
                                    </p>
                                  )}

                                  {/* Grid layout for data sections */}
                                  <div className="grid sm:grid-cols-2 gap-4">
                                    {/* Forms */}
                                    {analysis?.forms && analysis.forms.length > 0 && (
                                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                                        <div className="flex items-center gap-2 mb-3">
                                          <FormInput className="w-4 h-4 text-green-500" />
                                          <span className="text-xs font-semibold uppercase tracking-wide">Forms</span>
                                        </div>
                                        <div className="space-y-3">
                                          {analysis.forms.map((form, i) => (
                                            <div key={i}>
                                              <div className="text-sm font-medium mb-1.5">
                                                {form.form_purpose || form.form_name || 'Form'}
                                              </div>
                                              {form.fields && form.fields.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                  {form.fields.map((field, j) => (
                                                    <span
                                                      key={j}
                                                      className="text-[11px] px-1.5 py-0.5 rounded bg-background border border-border/50 font-mono-custom"
                                                    >
                                                      {field.label || field.name}
                                                      {field.required && <span className="text-red-500 ml-0.5">*</span>}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Tables */}
                                    {analysis?.tables && analysis.tables.length > 0 && (
                                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                                        <div className="flex items-center gap-2 mb-3">
                                          <Table2 className="w-4 h-4 text-cyan-500" />
                                          <span className="text-xs font-semibold uppercase tracking-wide">Tables</span>
                                        </div>
                                        <div className="space-y-3">
                                          {analysis.tables.map((table, i) => (
                                            <div key={i}>
                                              <div className="text-sm font-medium mb-1.5">
                                                {table.table_name || 'Data Table'}
                                              </div>
                                              {table.columns && table.columns.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mb-1.5">
                                                  {table.columns.map((col, j) => (
                                                    <span
                                                      key={j}
                                                      className="text-[11px] px-1.5 py-0.5 rounded bg-background border border-border/50 font-mono-custom"
                                                    >
                                                      {col}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                              <div className="text-[11px] text-muted-foreground">
                                                {[
                                                  table.has_pagination && 'Pagination',
                                                  table.has_sorting && 'Sorting',
                                                  table.has_filtering && 'Filtering',
                                                ].filter(Boolean).join(' · ') || 'No features'}
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Actions */}
                                    {analysis?.actions && analysis.actions.length > 0 && (
                                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                                        <div className="flex items-center gap-2 mb-3">
                                          <MousePointer className="w-4 h-4 text-purple-500" />
                                          <span className="text-xs font-semibold uppercase tracking-wide">Actions</span>
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                          {analysis.actions.map((action, i) => (
                                            <span
                                              key={i}
                                              className={`text-[11px] px-2 py-1 rounded-md border ${
                                                action.is_destructive
                                                  ? 'bg-red-500/10 text-red-500 border-red-500/20'
                                                  : 'bg-background border-border/50'
                                              }`}
                                            >
                                              {action.action_text}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Permissions */}
                                    {node.requiredPermissions && node.requiredPermissions.length > 0 && (
                                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                                        <div className="flex items-center gap-2 mb-3">
                                          <Shield className="w-4 h-4 text-amber-500" />
                                          <span className="text-xs font-semibold uppercase tracking-wide">Permissions</span>
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                          {node.requiredPermissions.map((perm, i) => (
                                            <span
                                              key={i}
                                              className="text-[11px] px-2 py-1 rounded-md bg-amber-500/10 text-amber-600 border border-amber-500/20"
                                            >
                                              {perm}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>

                                  {/* Test Scenarios - Full width */}
                                  {node.testScenarios && node.testScenarios.length > 0 && (
                                    <div className="mt-4 p-3 rounded-lg bg-muted/30 border border-border/50">
                                      <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                          <FlaskConical className="w-4 h-4 text-blue-500" />
                                          <span className="text-xs font-semibold uppercase tracking-wide">Test Scenarios</span>
                                        </div>
                                      </div>
                                      <div className="space-y-2">
                                        {node.testScenarios.map((scenario, i) => (
                                          <div
                                            key={i}
                                            className="flex items-start justify-between gap-3 text-sm text-muted-foreground p-2 rounded-md bg-background/50 border border-border/30"
                                          >
                                            <div className="flex items-start gap-3 flex-1 min-w-0">
                                              <span className="text-blue-500 font-mono text-xs mt-0.5">{i + 1}</span>
                                              <span className="flex-1">{scenario}</span>
                                            </div>
                                            <Button
                                              variant="outline"
                                              size="sm"
                                              className="text-[10px] h-6 px-2 flex-shrink-0"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleRunScenario(node.id, scenario);
                                              }}
                                            >
                                              <Play className="w-3 h-3 mr-1" />
                                              Run
                                            </Button>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      {/* Empty state */}
                      {(!graphData?.nodes || graphData.nodes.length === 0) && (
                        <div className="text-center py-16">
                          <Globe className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                          <p className="text-sm text-muted-foreground">No pages discovered yet</p>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  {/* Tests Tab */}
                  <TabsContent value="tests" className="flex-1 m-0 overflow-auto p-4 sm:p-6">
                    <div className="max-w-4xl mx-auto">
                      {/* Header */}
                      <div className="flex items-center justify-between mb-6">
                        <div>
                          <h2 className="text-lg font-semibold">Test Cases</h2>
                          <p className="text-sm text-muted-foreground">
                            {testCases.length} test{testCases.length !== 1 ? 's' : ''} created
                          </p>
                        </div>
                        <Button
                          onClick={handleGenerateAllTests}
                          disabled={generatingTests || !graphData?.nodes.length}
                          size="sm"
                        >
                          {generatingTests ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Generating...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4 mr-2" />
                              Generate All Tests
                            </>
                          )}
                        </Button>
                      </div>

                      {/* Loading state */}
                      {loadingTests && (
                        <div className="flex items-center justify-center py-12">
                          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </div>
                      )}

                      {/* Test cases list */}
                      {!loadingTests && testCases.length > 0 && (
                        <div className="space-y-3">
                          {testCases.map((test) => {
                            const page = graphData?.nodes.find((n) => n.id === test.page_id);
                            return (
                              <div
                                key={test.id}
                                className="p-4 rounded-lg border border-border/50 bg-card/30 hover:bg-card/50 transition-colors"
                              >
                                <div className="flex items-start justify-between gap-4">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="font-medium text-sm truncate">{test.name}</span>
                                      <Badge
                                        variant="outline"
                                        className={`text-[10px] ${
                                          test.status === 'passing'
                                            ? 'bg-green-500/10 text-green-500 border-green-500/30'
                                            : test.status === 'failing'
                                            ? 'bg-red-500/10 text-red-500 border-red-500/30'
                                            : 'bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        {test.status}
                                      </Badge>
                                      <Badge variant="outline" className="text-[10px]">
                                        {test.source}
                                      </Badge>
                                    </div>
                                    {page && (
                                      <p className="text-xs text-muted-foreground font-mono-custom truncate">
                                        {page.path}
                                      </p>
                                    )}
                                    {test.description && (
                                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                        {test.description}
                                      </p>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2 flex-shrink-0">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="text-xs"
                                      onClick={() => handleRunTest(test)}
                                    >
                                      <Play className="w-3 h-3 mr-1" />
                                      Run
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="text-xs text-muted-foreground hover:text-red-500"
                                      onClick={() => handleDeleteTest(test.id)}
                                    >
                                      <X className="w-3 h-3" />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Empty state - no tests */}
                      {!loadingTests && testCases.length === 0 && graphData?.nodes.length > 0 && (
                        <div className="text-center py-12 border border-dashed border-border/50 rounded-lg">
                          <FlaskConical className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                          <h3 className="text-sm font-medium mb-1">No tests yet</h3>
                          <p className="text-xs text-muted-foreground mb-4">
                            Generate tests from discovered page scenarios
                          </p>
                          <Button onClick={handleGenerateAllTests} disabled={generatingTests} size="sm">
                            <Sparkles className="w-4 h-4 mr-2" />
                            Generate All Tests
                          </Button>
                        </div>
                      )}

                      {/* Empty state - no pages */}
                      {!loadingTests && (!graphData?.nodes || graphData.nodes.length === 0) && (
                        <div className="text-center py-12">
                          <Globe className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                          <p className="text-sm text-muted-foreground">
                            Run discovery first to find pages and generate tests
                          </p>
                        </div>
                      )}
                    </div>
                  </TabsContent>
                </Tabs>

                {/* Stats overlay - hide in list view */}
                {activeTab === 'graph' && (
                <div className="absolute top-2 sm:top-4 left-2 sm:left-4 flex flex-col gap-2 z-10">
                  <div className="flex items-center gap-2 sm:gap-4 px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg bg-background/80 backdrop-blur border border-border/50">
                    <div className="flex items-center gap-1 sm:gap-2">
                      <LayoutGrid className="w-3 h-3 sm:w-4 sm:h-4 text-blue-500" />
                      <span className="text-xs sm:text-sm font-medium">{graphData?.stats.pages || 0}</span>
                      <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">pages</span>
                    </div>
                    <div className="flex items-center gap-1 sm:gap-2">
                      <Sparkles className="w-3 h-3 sm:w-4 sm:h-4 text-amber-500" />
                      <span className="text-xs sm:text-sm font-medium">{graphData?.stats.features || 0}</span>
                      <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">features</span>
                    </div>
                    <div className="flex items-center gap-1 sm:gap-2">
                      <Layers className="w-3 h-3 sm:w-4 sm:h-4 text-purple-500" />
                      <span className="text-xs sm:text-sm font-medium">{graphData?.stats.patterns || 0}</span>
                      <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">patterns</span>
                    </div>
                  </div>
                </div>
                )}

                {/* Legend - hidden on small screens */}
                {activeTab === 'graph' && (
                  <div className="absolute bottom-2 sm:bottom-4 left-2 sm:left-4 px-2 sm:px-4 py-2 sm:py-3 rounded-lg bg-background/80 backdrop-blur border border-border/50 z-10 hidden sm:block">
                    <p className="text-[10px] text-muted-foreground mb-2 font-medium">Legend</p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-amber-500" />
                        <span>Feature</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-red-500" />
                        <span>Login</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <span>Dashboard</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        <span>Form</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Hint to click nodes - only show when no node selected */}
                {activeTab === 'graph' && !selectedNode && graphData && graphData.nodes.length > 0 && (
                  <div className="absolute bottom-2 sm:bottom-4 right-2 sm:right-4 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg bg-background/80 backdrop-blur border border-border/50 z-10 flex items-center gap-2">
                    <PanelRightOpen className="w-3 h-3 sm:w-4 sm:h-4 text-muted-foreground" />
                    <span className="text-[10px] sm:text-xs text-muted-foreground">Click a node for details</span>
                  </div>
                )}
              </div>

              {/* Right panel - Selected node details */}
              {selectedNode && (
                <div className="w-64 sm:w-72 lg:w-80 flex-shrink-0 border-l border-border/50 flex flex-col bg-card/30 overflow-hidden">
                  <div className="p-2 sm:p-4 border-b border-border/50 flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-xs sm:text-sm font-semibold mb-1 truncate">{selectedNode.title}</h3>
                      <p className="text-[10px] sm:text-xs text-muted-foreground truncate">{selectedNode.path}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 flex-shrink-0"
                      onClick={() => setSelectedNode(null)}
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                  <div className="p-2 sm:p-4 space-y-3 sm:space-y-4 overflow-y-auto flex-1">
                    <div>
                      <p className="text-[10px] text-muted-foreground mb-1">Type</p>
                      <Badge variant="outline" className="text-[10px] sm:text-xs">{selectedNode.type}</Badge>
                    </div>
                    {selectedNode.section && (
                      <div>
                        <p className="text-[10px] text-muted-foreground mb-1">Section</p>
                        <p className="text-xs sm:text-sm">{selectedNode.section}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-[10px] text-muted-foreground mb-1">Depth</p>
                      <p className="text-xs sm:text-sm">{selectedNode.depth} clicks from start</p>
                    </div>
                    {selectedNode.isFeature && (
                      <div>
                        <p className="text-[10px] text-muted-foreground mb-1">Feature</p>
                        <p className="text-xs sm:text-sm">{selectedNode.featureName}</p>
                      </div>
                    )}
                    {selectedNode.screenshot && (
                      <div>
                        <p className="text-[10px] text-muted-foreground mb-1">Screenshot</p>
                        <img
                          src={selectedNode.screenshot}
                          alt="Page screenshot"
                          className="rounded-lg border border-border/50 w-full"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </SidebarInset>

      {/* Test Execution Modal */}
      {executingTest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <FlaskConical className="w-5 h-5 text-blue-500" />
                </div>
                <div>
                  <h2 className="font-semibold">{executingTest.name}</h2>
                  <p className="text-xs text-muted-foreground">
                    {executionStatus === 'connecting' && 'Connecting...'}
                    {executionStatus === 'starting_browser' && 'Starting browser...'}
                    {executionStatus === 'running' && 'Running test...'}
                    {executionStatus === 'complete' && 'Test completed'}
                    {executionStatus === 'error' && 'Test failed'}
                    {executionStatus === 'stopped' && 'Test stopped'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {executionStatus === 'running' && (
                  <Button variant="outline" size="sm" onClick={handleStopTest}>
                    <Square className="w-3 h-3 mr-1" />
                    Stop
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={handleCloseExecution}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="flex-1 flex min-h-0 overflow-hidden">
              {/* Screenshot Panel */}
              <div className="flex-1 bg-black flex items-center justify-center p-4">
                {executionScreenshot ? (
                  <img
                    src={`data:image/png;base64,${executionScreenshot}`}
                    alt="Test execution"
                    className="max-w-full max-h-full object-contain rounded-lg"
                  />
                ) : (
                  <div className="text-muted-foreground flex flex-col items-center gap-3">
                    {['connecting', 'starting_browser'].includes(executionStatus) ? (
                      <>
                        <Loader2 className="w-8 h-8 animate-spin" />
                        <span className="text-sm">
                          {executionStatus === 'connecting' ? 'Connecting...' : 'Starting browser...'}
                        </span>
                      </>
                    ) : executionResult ? (
                      <>
                        {executionResult.success ? (
                          <CheckCircle2 className="w-12 h-12 text-green-500" />
                        ) : (
                          <XCircle className="w-12 h-12 text-red-500" />
                        )}
                        <span className="text-sm text-center max-w-xs">{executionResult.message}</span>
                        {executionResult.duration && (
                          <span className="text-xs text-muted-foreground">
                            Duration: {(executionResult.duration / 1000).toFixed(1)}s
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-sm">Waiting for screenshot...</span>
                    )}
                  </div>
                )}
              </div>

              {/* Steps Panel */}
              <div className="w-80 border-l border-border flex flex-col">
                <div className="px-4 py-3 border-b border-border">
                  <h3 className="text-sm font-medium">Steps ({executionSteps.length})</h3>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-2">
                  {executionSteps.length === 0 && (
                    <p className="text-xs text-muted-foreground text-center py-4">
                      No steps recorded yet
                    </p>
                  )}
                  {executionSteps.map((step, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-muted/30 border border-border/50 text-xs"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-muted-foreground">{i + 1}</span>
                        <Badge variant="outline" className="text-[10px]">
                          {step.type}
                        </Badge>
                      </div>
                      {step.selector && (
                        <p className="font-mono text-[10px] text-muted-foreground truncate">
                          {step.selector}
                        </p>
                      )}
                      {step.value && (
                        <p className="text-muted-foreground mt-1 truncate">
                          {step.value}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            {executionResult && (
              <div className={`px-6 py-4 border-t ${executionResult.success ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {executionResult.success ? (
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className={`font-medium ${executionResult.success ? 'text-green-500' : 'text-red-500'}`}>
                      {executionResult.success ? 'Test Passed' : 'Test Failed'}
                    </span>
                  </div>
                  <Button onClick={handleCloseExecution}>
                    Close
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </SidebarProvider>
  );
}
