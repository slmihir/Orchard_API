'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Globe,
  ArrowLeft,
  Eye,
  EyeOff,
  Loader2,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { projectsApi } from '@/lib/api';
import { useAuthStore, useHasHydrated } from '@/stores/authStore';

export default function NewProjectPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const hasHydrated = useHasHydrated();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [description, setDescription] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [maxDepth, setMaxDepth] = useState(5);
  const [maxPages, setMaxPages] = useState(100);

  useEffect(() => {
    if (hasHydrated && !isAuthenticated) {
      router.push('/login');
    }
  }, [hasHydrated, isAuthenticated, router]);

  // Auto-generate name from URL
  useEffect(() => {
    if (baseUrl && !name) {
      try {
        const url = new URL(baseUrl);
        setName(url.hostname.replace('www.', ''));
      } catch {
        // Invalid URL, ignore
      }
    }
  }, [baseUrl, name]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !baseUrl) return;

    setLoading(true);
    try {
      const project = await projectsApi.create({
        name,
        base_url: baseUrl,
        description: description || undefined,
        credentials: (username || password) ? {
          username: username || undefined,
          email: username || undefined,
          password: password || undefined,
        } : undefined,
        max_depth: maxDepth,
        max_pages: maxPages,
      });

      // Redirect to discovery page
      router.push(`/projects/${project.id}/discover`);
    } catch (error) {
      console.error('Failed to create project:', error);
      setLoading(false);
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
        <header className="flex items-center gap-4 px-4 py-3 border-b border-border/50 bg-card/30">
          <SidebarTrigger className="-ml-1" />
          <Link href="/projects">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Globe className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">New Project</h1>
              <p className="text-[10px] text-muted-foreground">
                Configure and start discovering
              </p>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <div className="max-w-xl mx-auto">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* URL Input - Primary */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Website URL</label>
                <Input
                  type="url"
                  placeholder="https://app.example.com"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="h-12 text-base"
                  required
                  autoFocus
                />
                <p className="text-[11px] text-muted-foreground">
                  The starting URL for discovery. Usually the login page or homepage.
                </p>
              </div>

              {/* Project Name */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Project Name</label>
                <Input
                  placeholder="My App"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              {/* Description (Optional) */}
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Description <span className="text-muted-foreground font-normal">(optional)</span>
                </label>
                <Input
                  placeholder="E-commerce platform for..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {/* Credentials Section */}
              <div className="rounded-xl border border-border/50 bg-card/20 p-4 space-y-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-medium">Login Credentials</h3>
                  <span className="text-[10px] text-muted-foreground">(optional)</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  If your app requires authentication, provide credentials for the scout agent to login.
                </p>
                <div className="grid gap-3">
                  <Input
                    placeholder="Email or username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                  <div className="relative">
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Advanced Settings */}
              <div className="rounded-xl border border-border/50 bg-card/20 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center justify-between w-full p-4 text-left hover:bg-card/30 transition-colors"
                >
                  <span className="text-sm font-medium">Advanced Settings</span>
                  {showAdvanced ? (
                    <ChevronUp className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>

                {showAdvanced && (
                  <div className="p-4 pt-0 space-y-4 border-t border-border/50">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="text-xs font-medium">Max Depth</label>
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          value={maxDepth}
                          onChange={(e) => setMaxDepth(parseInt(e.target.value) || 5)}
                        />
                        <p className="text-[10px] text-muted-foreground">
                          Maximum clicks from start page
                        </p>
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-medium">Max Pages</label>
                        <Input
                          type="number"
                          min={10}
                          max={500}
                          value={maxPages}
                          onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)}
                        />
                        <p className="text-[10px] text-muted-foreground">
                          Maximum pages to discover
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Submit */}
              <div className="flex items-center justify-between pt-4">
                <Link href="/projects">
                  <Button type="button" variant="ghost">
                    Cancel
                  </Button>
                </Link>
                <Button
                  type="submit"
                  disabled={!name || !baseUrl || loading}
                  className="gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Create & Start Discovery
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
