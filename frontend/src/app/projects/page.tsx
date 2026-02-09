'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Globe,
  Plus,
  Play,
  Trash2,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Pause,
  LayoutGrid,
  Layers,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { projectsApi, ProjectResponse } from '@/lib/api';
import { useAuthStore, useHasHydrated } from '@/stores/authStore';

const STATUS_CONFIG: Record<string, { icon: any; color: string; bg: string; label: string; animate?: boolean }> = {
  pending: { icon: Clock, color: 'text-muted-foreground', bg: 'bg-muted', label: 'Pending' },
  discovering: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'Discovering', animate: true },
  paused: { icon: Pause, color: 'text-yellow-500', bg: 'bg-yellow-500/10', label: 'Paused' },
  completed: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-500/10', label: 'Completed' },
  failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-500/10', label: 'Failed' },
};

export default function ProjectsPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const hasHydrated = useHasHydrated();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (hasHydrated && !isAuthenticated) {
      router.push('/login');
    }
  }, [hasHydrated, isAuthenticated, router]);

  useEffect(() => {
    if (hasHydrated && isAuthenticated) {
      loadProjects();
    }
  }, [hasHydrated, isAuthenticated]);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const data = await projectsApi.list();
      setProjects(data);
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm('Delete this project and all discovered data?')) return;
    try {
      await projectsApi.delete(id);
      setProjects(projects.filter((p) => p.id !== id));
    } catch (error) {
      console.error('Failed to delete:', error);
    }
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
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border/50 bg-card/30">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                <Globe className="w-4 h-4 text-primary" />
              </div>
              <div>
                <h1 className="text-sm font-semibold">Projects</h1>
                <p className="text-[10px] text-muted-foreground">
                  {projects.length} project{projects.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          </div>
          <Link href="/projects/new">
            <Button size="sm" className="gap-2">
              <Plus className="w-4 h-4" />
              New Project
            </Button>
          </Link>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <div className="max-w-5xl mx-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : projects.length === 0 ? (
              <div className="text-center py-16 rounded-2xl border border-dashed border-border/50 bg-card/20">
                <Globe className="w-12 h-12 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="text-lg font-medium mb-2">No projects yet</h3>
                <p className="text-sm text-muted-foreground mb-6">
                  Create your first project to start discovering features
                </p>
                <Link href="/projects/new">
                  <Button className="gap-2">
                    <Plus className="w-4 h-4" />
                    Create Project
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="grid gap-4">
                {projects.map((project) => {
                  const status = STATUS_CONFIG[project.status] || STATUS_CONFIG.pending;
                  const StatusIcon = status.icon;

                  return (
                    <Link
                      key={project.id}
                      href={`/projects/${project.id}`}
                      className="block"
                    >
                      <div className="p-5 rounded-xl border border-border/50 bg-card/30 hover:bg-card/50 hover:border-border transition-all cursor-pointer group">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-2">
                              <h3 className="font-semibold truncate">{project.name}</h3>
                              <Badge
                                variant="outline"
                                className={`text-[10px] ${status.bg} ${status.color} border-0`}
                              >
                                <StatusIcon className={`w-3 h-3 mr-1 ${status.animate ? 'animate-spin' : ''}`} />
                                {status.label}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground truncate mb-3">
                              {project.base_url}
                            </p>

                            {/* Stats */}
                            <div className="flex items-center gap-6 text-xs">
                              <div className="flex items-center gap-1.5">
                                <LayoutGrid className="w-3.5 h-3.5 text-muted-foreground" />
                                <span className="font-medium">{project.pages_discovered}</span>
                                <span className="text-muted-foreground">pages</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Sparkles className="w-3.5 h-3.5 text-muted-foreground" />
                                <span className="font-medium">{project.features_found}</span>
                                <span className="text-muted-foreground">features</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Layers className="w-3.5 h-3.5 text-muted-foreground" />
                                <span className="font-medium">{project.patterns_detected}</span>
                                <span className="text-muted-foreground">patterns</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {project.status === 'pending' && (
                              <Link
                                href={`/projects/${project.id}/discover`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Button
                                  variant="default"
                                  size="sm"
                                  className="gap-1.5"
                                >
                                  <Play className="w-3.5 h-3.5" />
                                  Discover
                                </Button>
                              </Link>
                            )}
                            {project.status === 'completed' && (
                              <Link
                                href={`/projects/${project.id}`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="gap-1.5"
                                >
                                  View Graph
                                </Button>
                              </Link>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => handleDelete(project.id, e)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>

                        {/* Progress bar for discovering */}
                        {project.status === 'discovering' && (
                          <div className="mt-4 pt-4 border-t border-border/50">
                            <div className="flex items-center justify-between text-xs mb-2">
                              <span className="text-muted-foreground">Discovery in progress...</span>
                              <span className="font-medium">{project.pages_discovered} / {project.max_pages}</span>
                            </div>
                            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary rounded-full transition-all"
                                style={{ width: `${(project.pages_discovered / project.max_pages) * 100}%` }}
                              />
                            </div>
                          </div>
                        )}

                        {/* Timestamps */}
                        <div className="flex items-center gap-4 mt-4 text-[10px] text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Created {new Date(project.created_at).toLocaleDateString()}
                          </div>
                          {project.discovery_completed_at && (
                            <div>
                              Completed {new Date(project.discovery_completed_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
