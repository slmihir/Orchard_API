'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  Zap,
  MessageSquare,
  FolderOpen,
  LogOut,
  ChevronRight,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Folder,
  LayoutDashboard,
  PlayCircle,
  ListChecks,
  Clock,
  Settings,
  Moon,
  Sun,
  Shield,
  Globe,
  Code,
} from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuthStore, useHasPermission } from '@/stores/authStore';
import { collectionsApi, CollectionResponse } from '@/lib/api';
import { useTheme } from 'next-themes';

const COLLECTION_COLORS = [
  '#6366f1', // indigo
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#f43f5e', // rose
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#14b8a6', // teal
  '#06b6d4', // cyan
  '#3b82f6', // blue
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, logout } = useAuthStore();
  const { state } = useSidebar();
  const isCollapsed = state === 'collapsed';
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const canViewAdmin = useHasPermission('view_admin_dashboard');

  useEffect(() => {
    setMounted(true);
  }, []);

  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [isTestsOpen, setIsTestsOpen] = useState(true);
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingCollection, setEditingCollection] = useState<CollectionResponse | null>(null);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [newCollectionColor, setNewCollectionColor] = useState(COLLECTION_COLORS[0]);

  const selectedCollectionId = searchParams.get('collection');

  useEffect(() => {
    loadCollections();

    // Listen for collection updates from other components
    const handleCollectionUpdate = () => loadCollections();
    window.addEventListener('collections-updated', handleCollectionUpdate);
    return () => window.removeEventListener('collections-updated', handleCollectionUpdate);
  }, []);

  const loadCollections = async () => {
    try {
      const data = await collectionsApi.list();
      setCollections(data);
    } catch (error) {
      console.error('Failed to load collections:', error);
    }
  };

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) return;
    try {
      await collectionsApi.create({
        name: newCollectionName,
        color: newCollectionColor,
      });
      setNewCollectionName('');
      setNewCollectionColor(COLLECTION_COLORS[0]);
      setShowNewDialog(false);
      loadCollections();
    } catch (error) {
      console.error('Failed to create collection:', error);
    }
  };

  const handleUpdateCollection = async () => {
    if (!editingCollection || !newCollectionName.trim()) return;
    try {
      await collectionsApi.update(editingCollection.id, {
        name: newCollectionName,
        color: newCollectionColor,
      });
      setShowEditDialog(false);
      setEditingCollection(null);
      loadCollections();
    } catch (error) {
      console.error('Failed to update collection:', error);
    }
  };

  const handleDeleteCollection = async (id: string) => {
    if (!confirm('Delete this collection? Tests will be moved to "Uncategorized".')) return;
    try {
      await collectionsApi.delete(id);
      loadCollections();
      if (selectedCollectionId === id) {
        router.push('/tests');
      }
    } catch (error) {
      console.error('Failed to delete collection:', error);
    }
  };

  const openEditDialog = (collection: CollectionResponse) => {
    setEditingCollection(collection);
    setNewCollectionName(collection.name);
    setNewCollectionColor(collection.color);
    setShowEditDialog(true);
  };

  return (
    <>
      <Sidebar collapsible="icon" className="border-r border-border/50">
        <SidebarHeader className={isCollapsed ? "p-2" : "p-4"}>
          <Link href="/" className="flex items-center gap-3">
            <div className="relative flex-shrink-0">
              <div className="absolute inset-0 bg-primary/20 blur-lg rounded-full" />
              <div className={`relative flex items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/80 shadow-lg shadow-primary/20 transition-all ${isCollapsed ? 'w-8 h-8' : 'w-10 h-10'}`}>
                <Zap className={isCollapsed ? "w-4 h-4 text-primary-foreground" : "w-5 h-5 text-primary-foreground"} />
              </div>
            </div>
            {!isCollapsed && (
              <div className="overflow-hidden">
                <h1 className="text-lg font-bold tracking-tight">Autoflow</h1>
                <p className="text-[10px] text-muted-foreground tracking-widest uppercase">
                  AI Automation
                </p>
              </div>
            )}
          </Link>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel className={isCollapsed ? 'sr-only' : ''}>
              Navigation
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {/* Dashboard */}
                <SidebarMenuItem>
                  <Link href="/dashboard" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/dashboard'}
                      tooltip="Dashboard"
                      className={`h-10 w-full ${
                        pathname === '/dashboard'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <LayoutDashboard className="w-4 h-4" />
                      <span>Dashboard</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Projects */}
                <SidebarMenuItem>
                  <Link href="/projects" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/projects' || pathname.startsWith('/projects/')}
                      tooltip="Projects"
                      className={`h-10 w-full ${
                        pathname === '/projects' || pathname.startsWith('/projects/')
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <Globe className="w-4 h-4" />
                      <span>Projects</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* API Testing */}
                <SidebarMenuItem>
                  <Link href="/api-testing" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/api-testing'}
                      tooltip="API Testing"
                      className={`h-10 w-full ${
                        pathname === '/api-testing'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <Code className="w-4 h-4" />
                      <span>API Testing</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* API Test Runs - direct access to run list and details */}
                <SidebarMenuItem>
                  <Link href="/api-testing/runs" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/api-testing/runs' || pathname.startsWith('/api-testing/runs/')}
                      tooltip="API Test Runs"
                      className={`h-10 w-full ${
                        pathname === '/api-testing/runs' || pathname.startsWith('/api-testing/runs/')
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <ListChecks className="w-4 h-4" />
                      <span>API Test Runs</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Create Test */}
                <SidebarMenuItem>
                  <Link href="/" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/'}
                      tooltip="Create Test"
                      className={`h-10 w-full ${
                        pathname === '/'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <MessageSquare className="w-4 h-4" />
                      <span>Create Test</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Saved Tests with Collections */}
                <Collapsible open={isTestsOpen} onOpenChange={setIsTestsOpen}>
                  <SidebarMenuItem>
                    <CollapsibleTrigger
                      render={(props) => (
                        <SidebarMenuButton
                          {...props}
                          tooltip="Saved Tests"
                          className={`h-10 w-full ${
                            pathname === '/tests'
                              ? 'bg-primary/10 text-primary border-l-2 border-primary'
                              : 'hover:bg-card/50'
                          }`}
                        >
                          <FolderOpen className="w-4 h-4" />
                          <span className="flex-1">Saved Tests</span>
                          <ChevronRight className={`w-4 h-4 transition-transform ${isTestsOpen ? 'rotate-90' : ''}`} />
                        </SidebarMenuButton>
                      )}
                    />
                    <CollapsibleContent>
                      <SidebarMenuSub>
                        {/* All Tests */}
                        <SidebarMenuSubItem>
                          <Link href="/tests" className="w-full">
                            <SidebarMenuSubButton
                              isActive={pathname === '/tests' && !selectedCollectionId}
                              className="w-full"
                            >
                              <span>All Tests</span>
                            </SidebarMenuSubButton>
                          </Link>
                        </SidebarMenuSubItem>

                        {/* Collections */}
                        {collections.map((collection) => (
                          <SidebarMenuSubItem key={collection.id} className="group/collection">
                            <div className="flex items-center w-full">
                              <Link href={`/tests?collection=${collection.id}`} className="flex-1">
                                <SidebarMenuSubButton
                                  isActive={selectedCollectionId === collection.id}
                                  className="w-full"
                                >
                                  <div
                                    className="w-2 h-2 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: collection.color }}
                                  />
                                  <span className="truncate flex-1">{collection.name}</span>
                                  <span className="text-[10px] text-muted-foreground">
                                    {collection.test_count}
                                  </span>
                                </SidebarMenuSubButton>
                              </Link>
                              <DropdownMenu>
                                <DropdownMenuTrigger
                                  render={(props) => (
                                    <button
                                      {...props}
                                      className="p-1 opacity-0 group-hover/collection:opacity-100 hover:bg-muted rounded transition-opacity"
                                    >
                                      <MoreHorizontal className="w-3 h-3" />
                                    </button>
                                  )}
                                />
                                <DropdownMenuContent align="end" className="w-32">
                                  <DropdownMenuItem onClick={() => openEditDialog(collection)}>
                                    <Pencil className="w-3 h-3 mr-2" />
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() => handleDeleteCollection(collection.id)}
                                    className="text-destructive"
                                  >
                                    <Trash2 className="w-3 h-3 mr-2" />
                                    Delete
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </SidebarMenuSubItem>
                        ))}

                        {/* Add Collection */}
                        <SidebarMenuSubItem>
                          <button
                            onClick={() => setShowNewDialog(true)}
                            className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
                          >
                            <Plus className="w-3 h-3" />
                            <span>New Collection</span>
                          </button>
                        </SidebarMenuSubItem>
                      </SidebarMenuSub>
                    </CollapsibleContent>
                  </SidebarMenuItem>
                </Collapsible>

                {/* Test Runs */}
                <SidebarMenuItem>
                  <Link href="/runs" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/runs'}
                      tooltip="Test Runs"
                      className={`h-10 w-full ${
                        pathname === '/runs'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <PlayCircle className="w-4 h-4" />
                      <span>Test Runs</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Schedules */}
                <SidebarMenuItem>
                  <Link href="/schedules" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/schedules'}
                      tooltip="Schedules"
                      className={`h-10 w-full ${
                        pathname === '/schedules'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <Clock className="w-4 h-4" />
                      <span>Schedules</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Settings */}
                <SidebarMenuItem>
                  <Link href="/settings" className="w-full">
                    <SidebarMenuButton
                      isActive={pathname === '/settings'}
                      tooltip="Settings"
                      className={`h-10 w-full ${
                        pathname === '/settings'
                          ? 'bg-primary/10 text-primary border-l-2 border-primary'
                          : 'hover:bg-card/50'
                      }`}
                    >
                      <Settings className="w-4 h-4" />
                      <span>Settings</span>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>

                {/* Admin - only shown to users with admin permissions */}
                {canViewAdmin && (
                  <SidebarMenuItem>
                    <Link href="/admin" className="w-full">
                      <SidebarMenuButton
                        isActive={pathname === '/admin' || pathname.startsWith('/admin/')}
                        tooltip="Admin"
                        className={`h-10 w-full ${
                          pathname === '/admin' || pathname.startsWith('/admin/')
                            ? 'bg-primary/10 text-primary border-l-2 border-primary'
                            : 'hover:bg-card/50'
                        }`}
                      >
                        <Shield className="w-4 h-4" />
                        <span>Admin</span>
                      </SidebarMenuButton>
                    </Link>
                  </SidebarMenuItem>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter className="p-4 border-t border-border/50">
          <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
            {!isCollapsed && (
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-medium text-primary">
                    {user?.name?.charAt(0) || 'U'}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">{user?.name || 'User'}</p>
                    {user?.role && (
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                        user.role.name === 'admin'
                          ? 'bg-primary/20 text-primary'
                          : 'bg-muted text-muted-foreground'
                      }`}>
                        {user.role.display_name}
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground truncate">{user?.email}</p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="flex-shrink-0 h-8 w-8 text-muted-foreground hover:text-foreground"
                title="Toggle theme"
              >
                {mounted && (theme === 'dark' ? (
                  <Sun className="w-4 h-4" />
                ) : (
                  <Moon className="w-4 h-4" />
                ))}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="flex-shrink-0 h-8 w-8 text-muted-foreground hover:text-foreground"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      {/* New Collection Dialog */}
      <Dialog open={showNewDialog} onOpenChange={setShowNewDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>New Collection</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="e.g., Login Tests"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Color</label>
              <div className="flex gap-2 flex-wrap">
                {COLLECTION_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNewCollectionColor(color)}
                    className={`w-8 h-8 rounded-lg transition-all ${
                      newCollectionColor === color
                        ? 'ring-2 ring-offset-2 ring-offset-background ring-foreground scale-110'
                        : 'hover:scale-105'
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateCollection}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Collection Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Collection</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="Collection name"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Color</label>
              <div className="flex gap-2 flex-wrap">
                {COLLECTION_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNewCollectionColor(color)}
                    className={`w-8 h-8 rounded-lg transition-all ${
                      newCollectionColor === color
                        ? 'ring-2 ring-offset-2 ring-offset-background ring-foreground scale-110'
                        : 'hover:scale-105'
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateCollection}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
