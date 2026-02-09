'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Wand2,
  Loader2,
  Check,
  Sparkles,
  Zap,
  Bot,
  Sun,
  Moon,
  Monitor,
  User,
  Palette,
  Shield,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { useAuthStore, useHasHydrated } from '@/stores/authStore';
import { settingsApi } from '@/lib/api';

interface HealingSettings {
  enabled: boolean;
  auto_approve: boolean;
  auto_approve_threshold: number;
  mode: string;
  provider: string;
}

interface LLMProvider {
  id: string;
  name: string;
  available: boolean;
  description: string;
}

type TabId = 'healing' | 'appearance' | 'profile';

export default function SettingsPage() {
  const router = useRouter();
  const { isAuthenticated, token, logout, user } = useAuthStore();
  const hasHydrated = useHasHydrated();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  const [activeTab, setActiveTab] = useState<TabId>('healing');
  const [settings, setSettings] = useState<HealingSettings | null>(null);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!hasHydrated) return;

    if (isAuthenticated && !token) {
      logout();
      router.push('/login');
      return;
    }

    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, token, hasHydrated, router, logout]);

  useEffect(() => {
    if (!hasHydrated || !isAuthenticated || !token) return;
    loadSettings();
  }, [isAuthenticated, hasHydrated, token]);

  const loadSettings = async () => {
    try {
      const [healingSettings, llmProviders] = await Promise.all([
        settingsApi.getHealingSettings(),
        settingsApi.getLLMProviders(),
      ]);
      setSettings(healingSettings);
      setProviders(llmProviders);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateSetting = async (key: string, value: unknown) => {
    if (!settings) return;

    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);

    setSaving(true);
    setSaved(false);
    try {
      await settingsApi.updateHealingSettings({ [key]: value });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save setting:', error);
      setSettings(settings);
    } finally {
      setSaving(false);
    }
  };

  if (!hasHydrated || !isAuthenticated || !token) return null;

  const tabs = [
    { id: 'healing' as TabId, label: 'Self-Healing', icon: Wand2 },
    { id: 'appearance' as TabId, label: 'Appearance', icon: Palette },
    { id: 'profile' as TabId, label: 'Profile', icon: User },
  ];

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/40 bg-background/80 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="-ml-1" />
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full" />
                <div className="relative p-2.5 rounded-xl bg-gradient-to-br from-primary to-cyan-600 shadow-lg shadow-primary/20">
                  <Zap className="w-5 h-5 text-white" />
                </div>
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
                <p className="text-xs text-muted-foreground">
                  Personalize your experience
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {saving && (
              <Badge variant="outline" className="text-xs bg-background/50 animate-pulse">
                <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                Saving
              </Badge>
            )}
            {saved && (
              <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs">
                <Check className="w-3 h-3 mr-1.5" />
                Saved
              </Badge>
            )}
          </div>
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
                      ? 'bg-primary/10 text-primary dark:text-primary shadow-sm'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-primary' : ''}`} />
                  {tab.label}
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
                <Loader2 className="w-8 h-8 animate-spin text-primary/50" />
                <span className="text-sm text-muted-foreground">Loading settings...</span>
              </div>
            </div>
          ) : (
            <div className="p-6 max-w-3xl">
              {/* Self-Healing Tab */}
              {activeTab === 'healing' && settings && (
                <div className="space-y-6 animate-in fade-in duration-300">
                  {/* Main Toggle Card */}
                  <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-card/50 backdrop-blur-sm">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-primary/10 to-transparent pointer-events-none" />
                    <div className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20">
                            <Wand2 className="w-6 h-6 text-primary" />
                          </div>
                          <div>
                            <h2 className="text-lg font-semibold">Self-Healing</h2>
                            <p className="text-sm text-muted-foreground mt-1 max-w-md">
                              When selectors break, AI automatically finds and suggests the correct element. Enable to keep your tests running smoothly.
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => updateSetting('enabled', !settings.enabled)}
                          className={`relative w-14 h-7 rounded-full transition-all duration-300 ${
                            settings.enabled
                              ? 'bg-gradient-to-r from-primary to-cyan-400 shadow-lg shadow-primary/30'
                              : 'bg-muted'
                          }`}
                        >
                          <span
                            className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-md transition-all duration-300 ${
                              settings.enabled ? 'left-8' : 'left-1'
                            }`}
                          />
                        </button>
                      </div>
                    </div>
                  </div>

                  {settings.enabled && (
                    <>
                      {/* Auto-Approve Section */}
                      <div className="rounded-2xl border border-border/50 bg-card/30 p-6 space-y-6">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-medium flex items-center gap-2">
                              <Sparkles className="w-4 h-4 text-primary" />
                              Auto-Approve Fixes
                            </h3>
                            <p className="text-sm text-muted-foreground mt-1">
                              Automatically apply high-confidence fixes without manual review
                            </p>
                          </div>
                          <button
                            onClick={() => updateSetting('auto_approve', !settings.auto_approve)}
                            className={`relative w-12 h-6 rounded-full transition-all ${
                              settings.auto_approve
                                ? 'bg-gradient-to-r from-primary to-cyan-400'
                                : 'bg-muted'
                            }`}
                          >
                            <span
                              className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all ${
                                settings.auto_approve ? 'left-7' : 'left-1'
                              }`}
                            />
                          </button>
                        </div>

                        {settings.auto_approve && (
                          <div className="pt-4 border-t border-border/30">
                            <div className="flex items-center justify-between mb-4">
                              <div>
                                <p className="text-sm font-medium">Confidence Threshold</p>
                                <p className="text-xs text-muted-foreground">
                                  Only auto-approve when AI confidence exceeds this level
                                </p>
                              </div>
                              <div className="px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20">
                                <span className="text-sm font-mono font-bold text-primary dark:text-primary">
                                  {(settings.auto_approve_threshold * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                            <div className="relative">
                              <div className="absolute inset-0 h-2 top-1/2 -translate-y-1/2 rounded-full bg-gradient-to-r from-cyan-600 via-primary to-emerald-500 opacity-20" />
                              <input
                                type="range"
                                min="50"
                                max="99"
                                value={settings.auto_approve_threshold * 100}
                                onChange={(e) =>
                                  updateSetting('auto_approve_threshold', parseInt(e.target.value) / 100)
                                }
                                className="relative w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
                                style={{
                                  background: `linear-gradient(to right, rgb(8 145 178) 0%, rgb(6 182 212) ${(settings.auto_approve_threshold - 0.5) * 200}%, rgb(229 231 235) ${(settings.auto_approve_threshold - 0.5) * 200}%)`
                                }}
                              />
                            </div>
                            <div className="flex justify-between text-[10px] text-muted-foreground mt-2 px-1">
                              <span>50% - More Fixes</span>
                              <span>99% - More Careful</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Healing Mode */}
                      <div className="rounded-2xl border border-border/50 bg-card/30 p-6">
                        <h3 className="font-medium mb-4">Healing Mode</h3>
                        <div className="grid grid-cols-3 gap-3">
                          {[
                            { id: 'inline', label: 'Inline', desc: 'Fix during test run', icon: '⚡' },
                            { id: 'batch', label: 'Batch', desc: 'Review after run', icon: '📋' },
                            { id: 'both', label: 'Both', desc: 'Inline + batch', icon: '🔄' },
                          ].map((mode) => (
                            <button
                              key={mode.id}
                              onClick={() => updateSetting('mode', mode.id)}
                              className={`relative p-4 rounded-xl border text-left transition-all ${
                                settings.mode === mode.id
                                  ? 'border-primary/50 bg-primary/5 ring-2 ring-primary/20'
                                  : 'border-border/50 bg-background/50 hover:border-border hover:bg-muted/30'
                              }`}
                            >
                              <span className="text-xl mb-2 block">{mode.icon}</span>
                              <p className="text-sm font-medium">{mode.label}</p>
                              <p className="text-[11px] text-muted-foreground mt-0.5">{mode.desc}</p>
                              {settings.mode === mode.id && (
                                <div className="absolute top-3 right-3 w-2 h-2 rounded-full bg-primary" />
                              )}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* AI Provider */}
                      <div className="rounded-2xl border border-border/50 bg-card/30 p-6">
                        <div className="flex items-center gap-2 mb-4">
                          <Bot className="w-4 h-4 text-primary" />
                          <h3 className="font-medium">AI Provider</h3>
                        </div>
                        <div className="grid gap-3">
                          {providers.map((provider) => (
                            <button
                              key={provider.id}
                              onClick={() => provider.available && updateSetting('provider', provider.id)}
                              disabled={!provider.available}
                              className={`p-4 rounded-xl border text-left transition-all ${
                                settings.provider === provider.id
                                  ? 'border-primary/50 bg-primary/5 ring-2 ring-primary/20'
                                  : provider.available
                                  ? 'border-border/50 bg-background/50 hover:border-border'
                                  : 'border-border/30 bg-muted/10 opacity-50 cursor-not-allowed'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <div
                                    className={`p-2 rounded-lg ${
                                      provider.id === 'gemini'
                                        ? 'bg-blue-500/10 text-blue-500'
                                        : provider.id === 'openai'
                                        ? 'bg-emerald-500/10 text-emerald-500'
                                        : 'bg-orange-500/10 text-orange-500'
                                    }`}
                                  >
                                    {provider.id === 'gemini' ? (
                                      <Zap className="w-4 h-4" />
                                    ) : provider.id === 'openai' ? (
                                      <Bot className="w-4 h-4" />
                                    ) : (
                                      <Sparkles className="w-4 h-4" />
                                    )}
                                  </div>
                                  <div>
                                    <p className="text-sm font-medium">{provider.name}</p>
                                    <p className="text-xs text-muted-foreground">{provider.description}</p>
                                  </div>
                                </div>
                                {!provider.available && (
                                  <Badge variant="outline" className="text-[10px]">
                                    No API key
                                  </Badge>
                                )}
                                {settings.provider === provider.id && provider.available && (
                                  <Check className="w-5 h-5 text-primary" />
                                )}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Appearance Tab */}
              {activeTab === 'appearance' && mounted && (
                <div className="space-y-6 animate-in fade-in duration-300">
                  <div className="rounded-2xl border border-border/50 bg-card/30 p-6">
                    <h3 className="font-medium mb-4 flex items-center gap-2">
                      <Palette className="w-4 h-4 text-primary" />
                      Theme
                    </h3>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { id: 'light', label: 'Light', icon: Sun },
                        { id: 'dark', label: 'Dark', icon: Moon },
                        { id: 'system', label: 'System', icon: Monitor },
                      ].map((t) => {
                        const Icon = t.icon;
                        return (
                          <button
                            key={t.id}
                            onClick={() => setTheme(t.id)}
                            className={`p-4 rounded-xl border text-center transition-all ${
                              theme === t.id
                                ? 'border-primary/50 bg-primary/5 ring-2 ring-primary/20'
                                : 'border-border/50 bg-background/50 hover:border-border hover:bg-muted/30'
                            }`}
                          >
                            <Icon className={`w-6 h-6 mx-auto mb-2 ${theme === t.id ? 'text-primary' : 'text-muted-foreground'}`} />
                            <p className="text-sm font-medium">{t.label}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* Profile Tab */}
              {activeTab === 'profile' && (
                <div className="space-y-6 animate-in fade-in duration-300">
                  <div className="rounded-2xl border border-border/50 bg-card/30 p-6">
                    <div className="flex items-center gap-4 mb-6">
                      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-cyan-600 flex items-center justify-center text-2xl font-bold text-white shadow-lg shadow-primary/20">
                        {user?.name?.charAt(0) || 'U'}
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold">{user?.name}</h2>
                        <p className="text-sm text-muted-foreground">{user?.email}</p>
                        {user?.role && (
                          <Badge className="mt-2 bg-primary/10 text-primary dark:text-primary border-primary/20">
                            <Shield className="w-3 h-3 mr-1" />
                            {user.role.display_name}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="pt-4 border-t border-border/30">
                      <p className="text-xs text-muted-foreground">
                        Profile editing coming soon. Contact an administrator to update your details.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
