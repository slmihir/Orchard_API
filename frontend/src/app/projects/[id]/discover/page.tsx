'use client';

import { useState, useEffect, useRef, useCallback, use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  ArrowLeft,
  Play,
  Pause,
  Square,
  Loader2,
  Globe,
  LayoutGrid,
  Sparkles,
  Layers,
  Activity,
  Monitor,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ChevronRight,
  PanelRightOpen,
  PanelRightClose,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { projectsApi, ProjectDiscoveryWebSocket, ProjectResponse } from '@/lib/api';
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

interface GraphNode {
  id: string;
  url: string;
  path: string;
  title: string;
  type: string;
  section?: string;
  depth: number;
  isFeature: boolean;
  featureName?: string;
  isPattern: boolean;
  patternId?: string;
  x?: number;
  y?: number;
  z?: number;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
  label?: string;
}

interface ActivityItem {
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
}

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
  page: '#64748b',
};

export default function DiscoverPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const hasHydrated = useHasHydrated();

  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<'idle' | 'running' | 'paused' | 'completed' | 'error'>('idle');
  const [showRightPanel, setShowRightPanel] = useState(true);

  // Graph state
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);

  // Stats
  const [stats, setStats] = useState({
    pages: 0,
    features: 0,
    patterns: 0,
    depth: 0,
  });

  // Live view
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);

  // WebSocket
  const wsRef = useRef<ProjectDiscoveryWebSocket | null>(null);
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
  }, [showRightPanel]);

  const loadProject = async () => {
    try {
      const data = await projectsApi.get(projectId);
      setProject(data);

      if (data.pages && data.pages.length > 0) {
        const graphData = await projectsApi.getGraph(projectId);
        setNodes(graphData.nodes);
        setLinks(graphData.links);
        setStats({
          ...graphData.stats,
          depth: 0,
        });
      }

      setStatus('idle');
    } catch (error) {
      console.error('Failed to load project:', error);
    } finally {
      setLoading(false);
    }
  };

  const startDiscovery = useCallback(async () => {
    if (!project) return;

    setNodes([]);
    setLinks([]);
    setStats({ pages: 0, features: 0, patterns: 0, depth: 0 });
    setActivities([]);
    setScreenshot(null);

    setStatus('running');
    addActivity('Starting discovery...', 'info');

    const ws = new ProjectDiscoveryWebSocket(projectId);
    wsRef.current = ws;

    ws.on('status', (data: any) => {
      if (data.status === 'paused') setStatus('paused');
      else if (data.status === 'running') setStatus('running');
    });

    ws.on('page_discovered', (data: any) => {
      const newNode: GraphNode = {
        id: data.id,
        url: data.url,
        path: data.path,
        title: data.title || data.path,
        type: data.page_type || 'page',
        section: data.section,
        depth: data.depth,
        isFeature: data.is_feature,
        featureName: data.feature_name,
        isPattern: data.is_pattern_instance,
        patternId: data.pattern_id,
      };
      setNodes((prev) => [...prev, newNode]);
    });

    ws.on('connection_found', (data: any) => {
      const newLink: GraphLink = {
        source: data.source_id,
        target: data.target_id,
        type: data.action?.type || 'click',
        label: data.action?.text,
      };
      setLinks((prev) => [...prev, newLink]);
    });

    ws.on('screenshot', (data: any) => {
      setScreenshot(data.image);
    });

    ws.on('activity', (data: any) => {
      addActivity(data.message, data.type || 'info');
    });

    ws.on('stats', (data: any) => {
      setStats({
        pages: data.pages_discovered || 0,
        features: data.features_found || 0,
        patterns: data.patterns_detected || 0,
        depth: data.current_depth || 0,
      });
    });

    ws.on('section_found', (data: any) => {
      addActivity(`Found section: ${data.name}`, 'success');
    });

    ws.on('feature_found', (data: any) => {
      addActivity(`Found feature: ${data.name}`, 'success');
    });

    ws.on('pattern_detected', (data: any) => {
      addActivity(`Detected pattern: ${data.pattern_id}`, 'info');
    });

    ws.on('complete', (data: any) => {
      setStatus('completed');
      addActivity(data.success ? 'Discovery completed!' : 'Discovery failed', data.success ? 'success' : 'error');
      ws.disconnect();
    });

    ws.on('error', (data: any) => {
      setStatus('error');
      addActivity(`Error: ${data.message}`, 'error');
    });

    try {
      await ws.connect();
    } catch (error) {
      setStatus('error');
      addActivity('Failed to connect', 'error');
    }
  }, [project, projectId]);

  const pauseDiscovery = () => {
    wsRef.current?.pause();
    setStatus('paused');
    addActivity('Discovery paused', 'info');
  };

  const resumeDiscovery = () => {
    wsRef.current?.resume();
    setStatus('running');
    addActivity('Discovery resumed', 'info');
  };

  const stopDiscovery = () => {
    wsRef.current?.stop();
    wsRef.current?.disconnect();
    setStatus('completed');
    addActivity('Discovery stopped', 'info');
  };

  const addActivity = (message: string, type: ActivityItem['type']) => {
    setActivities((prev) => [
      { message, type, timestamp: new Date().toISOString() },
      ...prev.slice(0, 99),
    ]);
  };

  const getNodeColor = (node: GraphNode) => {
    if (!node) return '#64748b';
    if (node.isFeature) return '#f59e0b';
    return NODE_COLORS[node.type] || '#64748b';
  };

  const getNodeSize = (node: GraphNode) => {
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
                <h1 className="text-xs sm:text-sm font-semibold truncate">{project?.name || 'Discovery'}</h1>
                <p className="text-[10px] text-muted-foreground truncate hidden sm:block">
                  {project?.base_url}
                </p>
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
            {status === 'idle' && (
              <Button onClick={startDiscovery} size="sm" className="gap-1 sm:gap-2 text-xs sm:text-sm">
                <Play className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="hidden sm:inline">{nodes.length > 0 ? 'Re-discover' : 'Start Discovery'}</span>
                <span className="sm:hidden">Start</span>
              </Button>
            )}
            {status === 'running' && (
              <>
                <Button variant="outline" size="sm" onClick={pauseDiscovery} className="gap-1 sm:gap-2">
                  <Pause className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Pause</span>
                </Button>
                <Button variant="destructive" size="sm" onClick={stopDiscovery} className="gap-1 sm:gap-2">
                  <Square className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Stop</span>
                </Button>
              </>
            )}
            {status === 'paused' && (
              <>
                <Button size="sm" onClick={resumeDiscovery} className="gap-1 sm:gap-2">
                  <Play className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Resume</span>
                </Button>
                <Button variant="destructive" size="sm" onClick={stopDiscovery} className="gap-1 sm:gap-2">
                  <Square className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">Stop</span>
                </Button>
              </>
            )}
            {(status === 'completed' || status === 'error') && nodes.length > 0 && (
              <Badge
                variant="outline"
                className={`text-[10px] sm:text-xs ${status === 'completed' ? 'bg-green-500/10 text-green-500 border-0' : 'bg-red-500/10 text-red-500 border-0'}`}
              >
                {status === 'completed' ? (
                  <><CheckCircle2 className="w-3 h-3 mr-1" /> <span className="hidden sm:inline">Completed</span></>
                ) : (
                  <><XCircle className="w-3 h-3 mr-1" /> <span className="hidden sm:inline">Error</span></>
                )}
              </Badge>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 flex-shrink-0"
              onClick={() => setShowRightPanel(!showRightPanel)}
            >
              {showRightPanel ? (
                <PanelRightClose className="w-4 h-4" />
              ) : (
                <PanelRightOpen className="w-4 h-4" />
              )}
            </Button>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex min-h-0 overflow-hidden">
          {/* 3D Graph - Main area */}
          <div
            ref={graphContainerRef}
            className="flex-1 min-w-0 relative overflow-hidden bg-gradient-to-br from-background to-muted/20"
          >
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : nodes.length === 0 && status === 'idle' ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-4">
                <Globe className="w-12 h-12 sm:w-16 sm:h-16 text-muted-foreground/20 mb-4" />
                <h3 className="text-base sm:text-lg font-medium mb-2 text-center">Ready to Discover</h3>
                <p className="text-xs sm:text-sm text-muted-foreground mb-6 text-center max-w-xs">
                  Click &quot;Start Discovery&quot; to explore {project?.base_url}
                </p>
                <Button onClick={startDiscovery} className="gap-2">
                  <Play className="w-4 h-4" />
                  Start Discovery
                </Button>
              </div>
            ) : (
              <div className="absolute inset-0">
                <ForceGraph2D
                  ref={graphRef}
                  graphData={{ nodes, links }}
                  nodeId="id"
                  nodeLabel={(node: any) => `${node.title || 'Page'} - ${node.path || ''}`}
                  nodeColor={(node: any) => getNodeColor(node as GraphNode)}
                  nodeRelSize={6}
                  nodeVal={(node: any) => getNodeSize(node as GraphNode)}
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
                    const nodeSize = getNodeSize(node as GraphNode) * 2;

                    // Draw node circle with border
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
                    ctx.fillStyle = getNodeColor(node as GraphNode);
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
                    const nodeSize = getNodeSize(node as GraphNode) * 2;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, nodeSize + 5, 0, 2 * Math.PI);
                    ctx.fillStyle = color;
                    ctx.fill();
                  }}
                  onNodeClick={(node: any) => {
                    console.log('Clicked node:', node);
                  }}
                />
              </div>
            )}

            {/* Stats overlay */}
            <div className="absolute top-2 sm:top-4 left-2 sm:left-4 flex flex-col gap-2 z-10">
              <div className="flex items-center gap-2 sm:gap-4 px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg bg-background/80 backdrop-blur border border-border/50">
                <div className="flex items-center gap-1 sm:gap-2">
                  <LayoutGrid className="w-3 h-3 sm:w-4 sm:h-4 text-blue-500" />
                  <span className="text-xs sm:text-sm font-medium">{stats.pages}</span>
                  <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">pages</span>
                </div>
                <div className="flex items-center gap-1 sm:gap-2">
                  <Sparkles className="w-3 h-3 sm:w-4 sm:h-4 text-amber-500" />
                  <span className="text-xs sm:text-sm font-medium">{stats.features}</span>
                  <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">features</span>
                </div>
                <div className="flex items-center gap-1 sm:gap-2">
                  <Layers className="w-3 h-3 sm:w-4 sm:h-4 text-purple-500" />
                  <span className="text-xs sm:text-sm font-medium">{stats.patterns}</span>
                  <span className="text-[10px] sm:text-xs text-muted-foreground hidden sm:inline">patterns</span>
                </div>
              </div>

              {status === 'running' && (
                <div className="flex items-center gap-2 px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <Loader2 className="w-3 h-3 sm:w-4 sm:h-4 animate-spin text-blue-500" />
                  <span className="text-[10px] sm:text-xs text-blue-500">Discovering...</span>
                </div>
              )}
            </div>

            {/* Legend - hidden on very small screens */}
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
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-cyan-500" />
                  <span>List</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-slate-500" />
                  <span>Page</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right panel - Live View & Activity */}
          {showRightPanel && (
            <div className="w-64 sm:w-72 lg:w-80 flex-shrink-0 border-l border-border/50 flex flex-col bg-card/30 overflow-hidden">
              {/* Live Screenshot */}
              <div className="p-2 sm:p-4 border-b border-border/50 flex-shrink-0">
                <div className="flex items-center gap-2 mb-2 sm:mb-3">
                  <Monitor className="w-3 h-3 sm:w-4 sm:h-4 text-muted-foreground" />
                  <span className="text-[10px] sm:text-xs font-medium">Live View</span>
                  {status === 'running' && (
                    <span className="flex items-center gap-1 text-[10px] text-green-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                      Live
                    </span>
                  )}
                </div>
                <div className="aspect-video rounded-lg bg-muted/50 overflow-hidden border border-border/50">
                  {screenshot ? (
                    <img
                      src={`data:image/jpeg;base64,${screenshot}`}
                      alt="Live browser view"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      <Monitor className="w-6 h-6 sm:w-8 sm:h-8 opacity-20" />
                    </div>
                  )}
                </div>
              </div>

              {/* Activity Stream */}
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <div className="flex items-center gap-2 px-2 sm:px-4 py-2 sm:py-3 border-b border-border/50 flex-shrink-0">
                  <Activity className="w-3 h-3 sm:w-4 sm:h-4 text-muted-foreground" />
                  <span className="text-[10px] sm:text-xs font-medium">Activity</span>
                </div>
                <div className="flex-1 overflow-y-auto p-1 sm:p-2">
                  {activities.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-8">
                      <Clock className="w-5 h-5 sm:w-6 sm:h-6 opacity-20 mb-2" />
                      <span className="text-[10px] sm:text-xs">No activity yet</span>
                    </div>
                  ) : (
                    <div className="space-y-0.5 sm:space-y-1">
                      {activities.map((activity, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-1.5 sm:gap-2 px-1.5 sm:px-2 py-1 sm:py-1.5 rounded hover:bg-muted/50 transition-colors"
                        >
                          {activity.type === 'success' && (
                            <CheckCircle2 className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                          )}
                          {activity.type === 'error' && (
                            <XCircle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                          )}
                          {activity.type === 'warning' && (
                            <AlertCircle className="w-3 h-3 text-yellow-500 mt-0.5 flex-shrink-0" />
                          )}
                          {activity.type === 'info' && (
                            <ChevronRight className="w-3 h-3 text-muted-foreground mt-0.5 flex-shrink-0" />
                          )}
                          <span className="text-[10px] sm:text-[11px] text-foreground/80 leading-tight break-words">
                            {activity.message}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
