'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users,
  Shield,
  Loader2,
  CheckCircle2,
  XCircle,
  Activity,
  Mail,
  Plus,
  Trash2,
  Send,
  Clock,
  UserPlus,
  Copy,
  ChevronDown,
  UserCheck,
  UserX,
  Edit2,
  X,
  Check,
  Key,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { useAuthStore, useHasHydrated, useHasPermission } from '@/stores/authStore';
import {
  adminApi,
  RoleResponse,
  UserAdminResponse,
  AdminStats,
  InvitationResponse,
} from '@/lib/api';

type TabId = 'users' | 'roles' | 'invitations';

// All available permissions
const ALL_PERMISSIONS = [
  { key: 'view_tests', label: 'View Tests' },
  { key: 'manage_tests', label: 'Manage Tests' },
  { key: 'run_tests', label: 'Run Tests' },
  { key: 'view_dashboard', label: 'View Dashboard' },
  { key: 'view_schedules', label: 'View Schedules' },
  { key: 'manage_schedules', label: 'Manage Schedules' },
  { key: 'manage_settings', label: 'Manage Settings' },
  { key: 'manage_users', label: 'Manage Users' },
  { key: 'manage_roles', label: 'Manage Roles' },
  { key: 'manage_org', label: 'Manage Organization' },
  { key: 'view_admin_dashboard', label: 'View Admin Dashboard' },
];

export default function AdminPage() {
  const router = useRouter();
  const { isAuthenticated, token, logout, user: currentUser } = useAuthStore();
  const hasHydrated = useHasHydrated();
  const canViewAdmin = useHasPermission('view_admin_dashboard');

  const [activeTab, setActiveTab] = useState<TabId>('users');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserAdminResponse[]>([]);
  const [roles, setRoles] = useState<RoleResponse[]>([]);
  const [invitations, setInvitations] = useState<InvitationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Dialog states
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [showRoleDialog, setShowRoleDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleResponse | null>(null);
  const [copiedLink, setCopiedLink] = useState<string | null>(null);

  // Form states
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRoleId, setInviteRoleId] = useState('');
  const [inviteMessage, setInviteMessage] = useState('');
  const [newRole, setNewRole] = useState({
    name: '',
    display_name: '',
    description: '',
    permissions: {} as Record<string, boolean>,
  });

  useEffect(() => {
    if (!hasHydrated) return;

    if (isAuthenticated && !token) {
      logout();
      router.push('/login');
      return;
    }

    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    if (!canViewAdmin) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, token, hasHydrated, router, logout, canViewAdmin]);

  useEffect(() => {
    if (!hasHydrated || !isAuthenticated || !token || !canViewAdmin) return;
    loadData();
  }, [isAuthenticated, hasHydrated, token, canViewAdmin]);

  const loadData = async () => {
    try {
      const [statsData, usersData, rolesData, invitationsData] = await Promise.all([
        adminApi.getStats(),
        adminApi.listUsers(),
        adminApi.listRoles(),
        adminApi.listInvitations(),
      ]);
      setStats(statsData);
      setUsers(usersData);
      setRoles(rolesData);
      setInvitations(invitationsData);
    } catch (error) {
      console.error('Failed to load admin data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, roleId: string) => {
    setActionLoading(userId);
    try {
      const updated = await adminApi.updateUserRole(userId, roleId);
      setUsers(users.map((u) => (u.id === userId ? updated : u)));
      const newStats = await adminApi.getStats();
      setStats(newStats);
    } catch (error) {
      console.error('Failed to update role:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStatusChange = async (userId: string, isActive: boolean) => {
    setActionLoading(userId);
    try {
      const updated = await adminApi.updateUserStatus(userId, isActive);
      setUsers(users.map((u) => (u.id === userId ? updated : u)));
      const newStats = await adminApi.getStats();
      setStats(newStats);
    } catch (error) {
      console.error('Failed to update status:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Are you sure you want to delete this user? This cannot be undone.')) return;
    setActionLoading(userId);
    try {
      await adminApi.deleteUser(userId);
      setUsers(users.filter((u) => u.id !== userId));
      const newStats = await adminApi.getStats();
      setStats(newStats);
    } catch (error) {
      console.error('Failed to delete user:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSendInvite = async () => {
    if (!inviteEmail || !inviteRoleId) return;
    setActionLoading('invite');
    try {
      const invitation = await adminApi.createInvitation({
        email: inviteEmail,
        role_id: inviteRoleId,
        message: inviteMessage || undefined,
      });
      setInvitations([invitation, ...invitations]);
      setShowInviteDialog(false);
      setInviteEmail('');
      setInviteRoleId('');
      setInviteMessage('');
      // Show magic link briefly
      if (invitation.magic_link) {
        setCopiedLink(invitation.id);
        navigator.clipboard.writeText(invitation.magic_link);
        setTimeout(() => setCopiedLink(null), 3000);
      }
    } catch (error: any) {
      alert(error.message || 'Failed to send invitation');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResendInvite = async (id: string) => {
    setActionLoading(id);
    try {
      await adminApi.resendInvitation(id);
    } catch (error) {
      console.error('Failed to resend invitation:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeInvite = async (id: string) => {
    setActionLoading(id);
    try {
      await adminApi.revokeInvitation(id);
      setInvitations(invitations.filter((i) => i.id !== id));
    } catch (error) {
      console.error('Failed to revoke invitation:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSaveRole = async () => {
    if (!newRole.name || !newRole.display_name) return;
    setActionLoading('role');
    try {
      if (editingRole) {
        const updated = await adminApi.updateRole(editingRole.id, {
          display_name: newRole.display_name,
          description: newRole.description,
          permissions: newRole.permissions,
        });
        setRoles(roles.map((r) => (r.id === editingRole.id ? updated : r)));
      } else {
        const created = await adminApi.createRole({
          name: newRole.name.toLowerCase().replace(/\s+/g, '_'),
          display_name: newRole.display_name,
          description: newRole.description,
          permissions: newRole.permissions,
        });
        setRoles([...roles, created]);
      }
      setShowRoleDialog(false);
      resetRoleForm();
    } catch (error: any) {
      alert(error.message || 'Failed to save role');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteRole = async (id: string) => {
    if (!confirm('Are you sure you want to delete this role?')) return;
    setActionLoading(id);
    try {
      await adminApi.deleteRole(id);
      setRoles(roles.filter((r) => r.id !== id));
    } catch (error: any) {
      alert(error.message || 'Failed to delete role');
    } finally {
      setActionLoading(null);
    }
  };

  const openEditRole = (role: RoleResponse) => {
    setEditingRole(role);
    setNewRole({
      name: role.name,
      display_name: role.display_name,
      description: role.description || '',
      permissions: { ...role.permissions },
    });
    setShowRoleDialog(true);
  };

  const resetRoleForm = () => {
    setEditingRole(null);
    setNewRole({
      name: '',
      display_name: '',
      description: '',
      permissions: {},
    });
  };

  if (!hasHydrated || !isAuthenticated || !token || !canViewAdmin) return null;

  const tabs = [
    { id: 'users' as TabId, label: 'Team Members', icon: Users, count: stats?.total_users },
    { id: 'roles' as TabId, label: 'Roles', icon: Shield, count: roles.length },
    { id: 'invitations' as TabId, label: 'Invitations', icon: Mail, count: stats?.pending_invitations },
  ];

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden bg-gradient-to-br from-background via-background to-cyan-950/5">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/40 bg-background/80 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="absolute inset-0 bg-cyan-500/20 blur-xl rounded-full" />
                <div className="relative p-2.5 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 shadow-lg shadow-cyan-500/20">
                  <Shield className="w-5 h-5 text-white" />
                </div>
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight">Team Admin</h1>
                <p className="text-xs text-muted-foreground">
                  Manage users, roles, and invitations
                </p>
              </div>
            </div>
          </div>
          <Button
            onClick={() => setShowInviteDialog(true)}
            className="bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white shadow-lg shadow-cyan-500/20"
          >
            <UserPlus className="w-4 h-4 mr-2" />
            Invite User
          </Button>
        </header>

        {/* Tab Navigation */}
        <div className="px-6 py-3 border-b border-border/40 bg-background/50">
          <nav className="flex gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 shadow-sm'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-500' : ''}`} />
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      isActive ? 'bg-cyan-500/20' : 'bg-muted'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-500/50" />
                <span className="text-sm text-muted-foreground">Loading team data...</span>
              </div>
            </div>
          ) : (
            <div className="p-6">
              {/* Users Tab */}
              {activeTab === 'users' && (
                <div className="space-y-4 animate-in fade-in duration-300">
                  {users.map((user) => (
                    <div
                      key={user.id}
                      className="flex items-center justify-between p-4 rounded-xl border border-border/50 bg-card/30 hover:bg-card/50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-teal-500/20 flex items-center justify-center">
                          <span className="text-sm font-semibold text-cyan-600 dark:text-cyan-400">
                            {user.name.charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{user.name}</p>
                            {user.id === currentUser?.id && (
                              <Badge className="text-[10px] bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20">
                                You
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {/* Role Dropdown */}
                        {user.id === currentUser?.id ? (
                          <Badge variant="outline" className="text-xs bg-cyan-500/5 border-cyan-500/20 text-cyan-600 dark:text-cyan-400">
                            {user.role_name || 'No Role'}
                          </Badge>
                        ) : (
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={(props) => (
                                <button
                                  {...props}
                                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border/50 hover:bg-muted/50 transition-colors text-sm"
                                  disabled={actionLoading === user.id}
                                >
                                  {user.role_name || 'No Role'}
                                  <ChevronDown className="w-3 h-3 opacity-50" />
                                </button>
                              )}
                            />
                            <DropdownMenuContent align="end">
                              {roles.map((role) => (
                                <DropdownMenuItem
                                  key={role.id}
                                  onClick={() => handleRoleChange(user.id, role.id)}
                                  className="gap-2"
                                >
                                  {role.display_name}
                                  {user.role_id === role.id && (
                                    <Check className="w-3 h-3 ml-auto text-cyan-500" />
                                  )}
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}

                        {/* Status Badge */}
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            user.is_active
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
                          }`}
                        >
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Badge>

                        {/* Actions */}
                        {user.id !== currentUser?.id && (
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => handleStatusChange(user.id, !user.is_active)}
                              disabled={actionLoading === user.id}
                            >
                              {user.is_active ? (
                                <UserX className="w-4 h-4 text-muted-foreground hover:text-red-500" />
                              ) : (
                                <UserCheck className="w-4 h-4 text-muted-foreground hover:text-emerald-500" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 hover:text-red-500"
                              onClick={() => handleDeleteUser(user.id)}
                              disabled={actionLoading === user.id}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Roles Tab */}
              {activeTab === 'roles' && (
                <div className="space-y-4 animate-in fade-in duration-300">
                  <div className="flex justify-end mb-4">
                    <Button
                      variant="outline"
                      onClick={() => {
                        resetRoleForm();
                        setShowRoleDialog(true);
                      }}
                      className="border-cyan-500/30 hover:bg-cyan-500/10"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Create Role
                    </Button>
                  </div>

                  {roles.map((role) => (
                    <div
                      key={role.id}
                      className="p-5 rounded-xl border border-border/50 bg-card/30"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2.5 rounded-xl ${
                            role.name === 'admin'
                              ? 'bg-gradient-to-br from-cyan-500/20 to-teal-500/20'
                              : 'bg-muted'
                          }`}>
                            <Key className={`w-4 h-4 ${
                              role.name === 'admin' ? 'text-cyan-500' : 'text-muted-foreground'
                            }`} />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="font-medium">{role.display_name}</p>
                              {role.is_system && (
                                <Badge variant="secondary" className="text-[10px]">System</Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">{role.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openEditRole(role)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          {!role.is_system && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 hover:text-red-500"
                              onClick={() => handleDeleteRole(role.id)}
                              disabled={actionLoading === role.id}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(role.permissions).map(([perm, enabled]) => (
                          <Badge
                            key={perm}
                            variant="outline"
                            className={`text-[10px] ${
                              enabled
                                ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
                                : 'opacity-40'
                            }`}
                          >
                            {enabled ? <Check className="w-2.5 h-2.5 mr-1" /> : <X className="w-2.5 h-2.5 mr-1" />}
                            {perm.replace(/_/g, ' ')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Invitations Tab */}
              {activeTab === 'invitations' && (
                <div className="space-y-4 animate-in fade-in duration-300">
                  {invitations.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <Mail className="w-12 h-12 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">No pending invitations</p>
                      <p className="text-sm mt-1">Invite team members to get started</p>
                      <Button
                        onClick={() => setShowInviteDialog(true)}
                        className="mt-4 bg-gradient-to-r from-cyan-500 to-teal-500"
                      >
                        <UserPlus className="w-4 h-4 mr-2" />
                        Send Invitation
                      </Button>
                    </div>
                  ) : (
                    invitations.map((invite) => (
                      <div
                        key={invite.id}
                        className="flex items-center justify-between p-4 rounded-xl border border-border/50 bg-card/30"
                      >
                        <div className="flex items-center gap-4">
                          <div className={`p-2.5 rounded-xl ${
                            invite.status === 'pending'
                              ? 'bg-amber-500/10'
                              : invite.status === 'accepted'
                              ? 'bg-emerald-500/10'
                              : 'bg-red-500/10'
                          }`}>
                            <Mail className={`w-4 h-4 ${
                              invite.status === 'pending'
                                ? 'text-amber-500'
                                : invite.status === 'accepted'
                                ? 'text-emerald-500'
                                : 'text-red-500'
                            }`} />
                          </div>
                          <div>
                            <p className="font-medium">{invite.email}</p>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <span>Invited as {invite.role_name}</span>
                              <span>·</span>
                              <span>by {invite.invited_by_name}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <Badge
                            variant="outline"
                            className={`text-xs ${
                              invite.status === 'pending'
                                ? 'bg-amber-500/10 text-amber-600 border-amber-500/20'
                                : invite.status === 'accepted'
                                ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
                                : 'bg-red-500/10 text-red-600 border-red-500/20'
                            }`}
                          >
                            {invite.status === 'pending' && <Clock className="w-3 h-3 mr-1" />}
                            {invite.status.charAt(0).toUpperCase() + invite.status.slice(1)}
                          </Badge>

                          {invite.status === 'pending' && (
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => handleResendInvite(invite.id)}
                                disabled={actionLoading === invite.id}
                                title="Resend invitation"
                              >
                                <Send className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 hover:text-red-500"
                                onClick={() => handleRevokeInvite(invite.id)}
                                disabled={actionLoading === invite.id}
                                title="Revoke invitation"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          )}

                          {copiedLink === invite.id && (
                            <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">
                              <Copy className="w-3 h-3 mr-1" />
                              Link copied!
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </SidebarInset>

      {/* Invite User Dialog */}
      <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-cyan-500" />
              Invite Team Member
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Email Address</label>
              <Input
                type="email"
                placeholder="colleague@company.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Role</label>
              <div className="grid grid-cols-3 gap-2">
                {roles.map((role) => (
                  <button
                    key={role.id}
                    onClick={() => setInviteRoleId(role.id)}
                    className={`p-3 rounded-lg border text-center transition-all ${
                      inviteRoleId === role.id
                        ? 'border-cyan-500/50 bg-cyan-500/10 ring-2 ring-cyan-500/20'
                        : 'border-border/50 hover:border-border'
                    }`}
                  >
                    <p className="text-sm font-medium">{role.display_name}</p>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">
                Personal Message <span className="text-muted-foreground">(optional)</span>
              </label>
              <Input
                placeholder="Welcome to the team!"
                value={inviteMessage}
                onChange={(e) => setInviteMessage(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInviteDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSendInvite}
              disabled={!inviteEmail || !inviteRoleId || actionLoading === 'invite'}
              className="bg-gradient-to-r from-cyan-500 to-teal-500"
            >
              {actionLoading === 'invite' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Send className="w-4 h-4 mr-2" />
              )}
              Send Invitation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Role Dialog */}
      <Dialog open={showRoleDialog} onOpenChange={setShowRoleDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Key className="w-5 h-5 text-cyan-500" />
              {editingRole ? 'Edit Role' : 'Create Role'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
            {!editingRole && (
              <div>
                <label className="text-sm font-medium mb-2 block">Role Name</label>
                <Input
                  placeholder="e.g., qa_lead"
                  value={newRole.name}
                  onChange={(e) => setNewRole({ ...newRole, name: e.target.value })}
                  disabled={!!editingRole}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Lowercase, no spaces (used internally)
                </p>
              </div>
            )}
            <div>
              <label className="text-sm font-medium mb-2 block">Display Name</label>
              <Input
                placeholder="e.g., QA Lead"
                value={newRole.display_name}
                onChange={(e) => setNewRole({ ...newRole, display_name: e.target.value })}
                disabled={editingRole?.is_system}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Description</label>
              <Input
                placeholder="Brief description of this role"
                value={newRole.description}
                onChange={(e) => setNewRole({ ...newRole, description: e.target.value })}
                disabled={editingRole?.is_system}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-3 block">Permissions</label>
              <div className="grid grid-cols-2 gap-2">
                {ALL_PERMISSIONS.map((perm) => (
                  <button
                    key={perm.key}
                    onClick={() => setNewRole({
                      ...newRole,
                      permissions: {
                        ...newRole.permissions,
                        [perm.key]: !newRole.permissions[perm.key],
                      },
                    })}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border text-left text-sm transition-all ${
                      newRole.permissions[perm.key]
                        ? 'border-cyan-500/50 bg-cyan-500/10'
                        : 'border-border/50 hover:border-border'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded flex items-center justify-center ${
                      newRole.permissions[perm.key]
                        ? 'bg-cyan-500 text-white'
                        : 'border border-border'
                    }`}>
                      {newRole.permissions[perm.key] && <Check className="w-3 h-3" />}
                    </div>
                    {perm.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRoleDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveRole}
              disabled={(!editingRole && !newRole.name) || !newRole.display_name || actionLoading === 'role'}
              className="bg-gradient-to-r from-cyan-500 to-teal-500"
            >
              {actionLoading === 'role' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Check className="w-4 h-4 mr-2" />
              )}
              {editingRole ? 'Save Changes' : 'Create Role'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  );
}
