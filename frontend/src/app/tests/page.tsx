'use client';

import { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Play,
  Trash2,
  Code,
  Clock,
  FileCode2,
  Copy,
  Check,
  Zap,
  FolderInput,
  MoreHorizontal,
  Pencil,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { AppSidebar } from '@/components/app-sidebar';
import { testsApi, collectionsApi, TestResponse, CollectionResponse, GenerateVariantsResponse, VariantResponse } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';

function TestsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const [tests, setTests] = useState<TestResponse[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTest, setSelectedTest] = useState<TestResponse | null>(null);
  const [playwrightCode, setPlaywrightCode] = useState<string>('');
  const [codeLanguage, setCodeLanguage] = useState<'typescript' | 'python'>('typescript');
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editingSteps, setEditingSteps] = useState<Array<{id: string; type: string; selector: string; value: string}>>([]);
  const [saving, setSaving] = useState(false);
  const [variants, setVariants] = useState<VariantResponse[]>([]);
  const [variantInfo, setVariantInfo] = useState<{setup_boundary: number; setup_type: string; duplicate_skipped: boolean} | null>(null);
  const [generatingVariants, setGeneratingVariants] = useState(false);
  const [showVariants, setShowVariants] = useState(false);
  const [expandedVariant, setExpandedVariant] = useState<number | null>(null);
  const [savingVariants, setSavingVariants] = useState(false);
  const [savedVariantIds, setSavedVariantIds] = useState<string[]>([]);

  const collectionId = searchParams.get('collection');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated, collectionId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [testsData, collectionsData] = await Promise.all([
        testsApi.list(collectionId || undefined),
        collectionsApi.list(),
      ]);
      setTests(testsData);
      setCollections(collectionsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewCode = async (test: TestResponse) => {
    setSelectedTest(test);
    setShowCode(true);
    setShowVariants(false);
    setVariants([]);
    setVariantInfo(null);
    setExpandedVariant(null);
    try {
      const code = await testsApi.getPlaywrightCode(test.id, codeLanguage);
      setPlaywrightCode(code);
    } catch (error) {
      setPlaywrightCode('// Failed to load code');
    }
  };

  const handleLanguageChange = async (lang: 'typescript' | 'python') => {
    setCodeLanguage(lang);
    if (selectedTest) {
      const code = await testsApi.getPlaywrightCode(selectedTest.id, lang);
      setPlaywrightCode(code);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this test?')) return;
    try {
      await testsApi.delete(id);
      setTests(tests.filter((t) => t.id !== id));
      if (selectedTest?.id === id) {
        setSelectedTest(null);
        setShowCode(false);
      }
    } catch (error) {
      console.error('Failed to delete:', error);
    }
  };

  const handleMoveToCollection = async (testId: string, newCollectionId: string | null) => {
    try {
      await testsApi.update(testId, { collection_id: newCollectionId } as any);
      await loadData();
      // Notify sidebar to refresh collection counts
      window.dispatchEvent(new Event('collections-updated'));
    } catch (error) {
      console.error('Failed to move test:', error);
    }
  };

  const handleEnterEditMode = async () => {
    if (!selectedTest) return;
    const fullTest = await testsApi.get(selectedTest.id);
    setSelectedTest(fullTest);
    if (fullTest.latest_version?.steps) {
      setEditingSteps(fullTest.latest_version.steps.map(s => ({
        id: s.id,
        type: s.type,
        selector: s.selector || '',
        value: s.value || '',
      })));
    }
    setEditMode(true);
  };

  const handleCancelEdit = () => {
    setEditMode(false);
    setEditingSteps([]);
  };

  const handleStepChange = (id: string, field: 'selector' | 'value', newValue: string) => {
    setEditingSteps(prev => prev.map(s => s.id === id ? { ...s, [field]: newValue } : s));
  };

  const handleSaveSteps = async () => {
    if (!selectedTest) return;
    setSaving(true);
    try {
      for (const step of editingSteps) {
        const original = selectedTest.latest_version?.steps?.find(s => s.id === step.id);
        if (original && (original.selector !== step.selector || original.value !== step.value)) {
          await testsApi.updateStep(selectedTest.id, step.id, {
            selector: step.selector || undefined,
            value: step.value || undefined,
          });
        }
      }
      // Also update target_url if navigate step changed
      const navStep = editingSteps.find(s => s.type === 'navigate');
      if (navStep && navStep.value) {
        await testsApi.update(selectedTest.id, { target_url: navStep.value } as any);
      }

      // Refresh
      const updated = await testsApi.get(selectedTest.id);
      setSelectedTest(updated);
      setTests(tests.map(t => t.id === updated.id ? updated : t));
      const code = await testsApi.getPlaywrightCode(selectedTest.id, codeLanguage);
      setPlaywrightCode(code);
      setEditMode(false);
      setEditingSteps([]);
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setSaving(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(playwrightCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateVariants = async () => {
    if (!selectedTest) return;
    setGeneratingVariants(true);
    setVariants([]);
    setVariantInfo(null);
    setSavedVariantIds([]);
    try {
      const result = await testsApi.generateVariants(selectedTest.id);
      setVariants(result.variants);
      setVariantInfo({
        setup_boundary: result.setup_boundary,
        setup_type: result.setup_type,
        duplicate_skipped: result.duplicate_skipped,
      });
      setShowVariants(true);
    } catch (error) {
      console.error('Failed to generate variants:', error);
    } finally {
      setGeneratingVariants(false);
    }
  };

  const handleSaveVariants = async () => {
    if (!selectedTest || variants.length === 0) return;
    setSavingVariants(true);
    try {
      const result = await testsApi.saveVariants(selectedTest.id, variants);
      setSavedVariantIds(result.variants.map((v) => v.id));
      // Refresh test list to show new variants
      await loadData();
    } catch (error) {
      console.error('Failed to save variants:', error);
    } finally {
      setSavingVariants(false);
    }
  };

  const getPageTitle = () => {
    if (collectionId) {
      const collection = collections.find((c) => c.id === collectionId);
      return collection?.name || 'Collection';
    }
    return 'All Tests';
  };

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center gap-4 px-4 py-3 border-b border-border/50 bg-card/30">
          <SidebarTrigger className="-ml-1" />
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <FileCode2 className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">{getPageTitle()}</h1>
              <p className="text-[10px] text-muted-foreground">
                {tests.length} test{tests.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-6xl mx-auto">
            {/* Tests List */}
            <div className="space-y-3">
              {loading ? (
                <div className="text-center py-12 text-muted-foreground">
                  Loading tests...
                </div>
              ) : tests.length === 0 ? (
                <div className="text-center py-16 rounded-2xl border border-dashed border-border/50 bg-card/20">
                  <FileCode2 className="w-12 h-12 mx-auto mb-4 text-muted-foreground/30" />
                  <h3 className="text-lg font-medium mb-2">No tests yet</h3>
                  <p className="text-sm text-muted-foreground mb-6">
                    Create your first test by recording browser actions
                  </p>
                  <Link href="/">
                    <Button className="gap-2">
                      <Zap className="w-4 h-4" />
                      Create Test
                    </Button>
                  </Link>
                </div>
              ) : (
                tests.map((test) => (
                  <div
                    key={test.id}
                    className={`p-4 rounded-xl border bg-card/30 hover:bg-card/50 transition-all cursor-pointer ${
                      selectedTest?.id === test.id
                        ? 'border-primary ring-1 ring-primary/20'
                        : 'border-border/50 hover:border-border'
                    }`}
                    onClick={() => handleViewCode(test)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium truncate">{test.name}</h3>
                          {test.collection && (
                            <div
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: test.collection.color }}
                              title={test.collection.name}
                            />
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {test.target_url}
                        </p>
                        <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(test.created_at).toLocaleDateString()}
                          </div>
                          {test.latest_version && (
                            <>
                              <Badge variant="outline" className="text-[10px] h-5">
                                v{test.latest_version.version_number}
                              </Badge>
                              <span>{test.latest_version.steps?.length || 0} steps</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Link
                          href={`/tests/${test.id}/run`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-chart-2 hover:text-chart-2 hover:bg-chart-2/10"
                            title="Run test"
                          >
                            <Play className="w-4 h-4" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewCode(test);
                          }}
                          title="View code"
                        >
                          <Code className="w-4 h-4" />
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            onClick={(e) => e.stopPropagation()}
                            render={(props) => (
                              <Button {...props} variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="w-4 h-4" />
                              </Button>
                            )}
                          />
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuSub>
                              <DropdownMenuSubTrigger>
                                <FolderInput className="w-4 h-4 mr-2" />
                                Move to Collection
                              </DropdownMenuSubTrigger>
                              <DropdownMenuSubContent className="w-40">
                                <DropdownMenuItem
                                  onClick={() => handleMoveToCollection(test.id, null)}
                                >
                                  Uncategorized
                                </DropdownMenuItem>
                                {collections.map((collection) => (
                                  <DropdownMenuItem
                                    key={collection.id}
                                    onClick={() => handleMoveToCollection(test.id, collection.id)}
                                  >
                                    <div
                                      className="w-2 h-2 rounded-full mr-2"
                                      style={{ backgroundColor: collection.color }}
                                    />
                                    {collection.name}
                                  </DropdownMenuItem>
                                ))}
                              </DropdownMenuSubContent>
                            </DropdownMenuSub>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => handleDelete(test.id)}
                              className="text-destructive"
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Code Viewer / Editor */}
            <div className="lg:sticky lg:top-6 h-fit">
              {showCode && selectedTest ? (
                <div className="rounded-xl border border-border/50 bg-card/30 overflow-hidden">
                  <div className="flex items-center justify-between p-4 border-b border-border/50">
                    <div>
                      <h3 className="font-medium text-sm">{selectedTest.name}</h3>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        {editMode ? 'Edit Code' : 'Playwright Test Code'}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {editMode ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7"
                            onClick={handleCancelEdit}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            className="text-xs h-7"
                            onClick={handleSaveSteps}
                            disabled={saving}
                          >
                            {saving ? 'Saving...' : 'Save'}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs h-7 gap-1"
                            onClick={handleGenerateVariants}
                            disabled={generatingVariants}
                          >
                            {generatingVariants ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Sparkles className="w-3 h-3" />
                            )}
                            {generatingVariants ? 'Generating...' : 'Variants'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7 gap-1"
                            onClick={handleEnterEditMode}
                          >
                            <Pencil className="w-3 h-3" />
                            Edit
                          </Button>
                          <Button
                            variant={codeLanguage === 'typescript' ? 'default' : 'ghost'}
                            size="sm"
                            className="text-xs h-7"
                            onClick={() => handleLanguageChange('typescript')}
                          >
                            TS
                          </Button>
                          <Button
                            variant={codeLanguage === 'python' ? 'default' : 'ghost'}
                            size="sm"
                            className="text-xs h-7"
                            onClick={() => handleLanguageChange('python')}
                          >
                            Py
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {editMode ? (
                    <div className="p-3 space-y-2 max-h-[500px] overflow-auto">
                      {editingSteps.map((step, i) => (
                        <div key={step.id} className="flex items-center gap-2 text-xs">
                          <span className="w-5 text-muted-foreground">{i + 1}.</span>
                          <Badge variant="outline" className="text-[10px] w-16 justify-center">{step.type}</Badge>
                          {step.type === 'navigate' ? (
                            <Input
                              value={step.value}
                              onChange={(e) => handleStepChange(step.id, 'value', e.target.value)}
                              className="h-7 text-xs font-mono flex-1"
                              placeholder="URL"
                            />
                          ) : step.type === 'wait' ? (
                            <span className="text-muted-foreground">wait for page</span>
                          ) : (
                            <>
                              <Input
                                value={step.selector}
                                onChange={(e) => handleStepChange(step.id, 'selector', e.target.value)}
                                className="h-7 text-xs font-mono flex-1"
                                placeholder="selector"
                              />
                              {(step.type === 'fill' || step.type === 'type') && (
                                <Input
                                  value={step.value}
                                  onChange={(e) => handleStepChange(step.id, 'value', e.target.value)}
                                  className="h-7 text-xs w-32"
                                  placeholder="value"
                                />
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="relative">
                      <pre className="p-4 overflow-auto max-h-[500px] text-xs font-mono bg-background/50">
                        <code className="text-muted-foreground">{playwrightCode}</code>
                      </pre>
                      <Button
                        variant="outline"
                        size="sm"
                        className="absolute top-3 right-3 h-7 text-xs gap-1.5"
                        onClick={copyToClipboard}
                      >
                        {copied ? (
                          <>
                            <Check className="w-3 h-3" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            Copy
                          </>
                        )}
                      </Button>
                    </div>
                  )}

                  {/* Variants Section */}
                  {showVariants && (
                    <div className="border-t border-border/50">
                      <div className="p-4 border-b border-border/50 bg-muted/20">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-primary" />
                            <span className="text-sm font-medium">
                              Generated Variants ({variants.length})
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            {variants.length > 0 && savedVariantIds.length === 0 && (
                              <Button
                                size="sm"
                                className="h-6 text-xs gap-1"
                                onClick={handleSaveVariants}
                                disabled={savingVariants}
                              >
                                {savingVariants ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Check className="w-3 h-3" />
                                )}
                                {savingVariants ? 'Saving...' : 'Save as Tests'}
                              </Button>
                            )}
                            {savedVariantIds.length > 0 && (
                              <Badge variant="outline" className="text-[10px] h-6 text-chart-2 border-chart-2/30">
                                <Check className="w-3 h-3 mr-1" />
                                Saved {savedVariantIds.length} tests
                              </Badge>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 text-xs"
                              onClick={() => setShowVariants(false)}
                            >
                              Hide
                            </Button>
                          </div>
                        </div>
                        {variantInfo && (
                          <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                            {variantInfo.setup_type !== 'none' && (
                              <span className="flex items-center gap-1">
                                <Badge variant="outline" className="text-[10px] h-4">
                                  {variantInfo.setup_type}
                                </Badge>
                                setup detected (steps 0-{variantInfo.setup_boundary - 1})
                              </span>
                            )}
                            {variantInfo.duplicate_skipped && (
                              <span className="text-amber-500">Pattern already has variants</span>
                            )}
                          </div>
                        )}
                      </div>

                      {variants.length === 0 ? (
                        <div className="p-8 text-center text-muted-foreground">
                          <p className="text-sm">
                            {variantInfo?.duplicate_skipped
                              ? 'This test pattern already has variants generated.'
                              : 'No variants generated. The test may not have form inputs to vary.'}
                          </p>
                        </div>
                      ) : (
                        <div className="divide-y divide-border/30 max-h-[300px] overflow-auto">
                          {variants.map((variant, i) => (
                            <div key={i} className="p-3">
                              <div
                                className="flex items-center justify-between cursor-pointer"
                                onClick={() => setExpandedVariant(expandedVariant === i ? null : i)}
                              >
                                <div className="flex items-center gap-2">
                                  <Badge
                                    variant="outline"
                                    className={`text-[10px] h-5 ${
                                      variant.type === 'security'
                                        ? 'border-red-500/30 text-red-500'
                                        : variant.type === 'boundary'
                                        ? 'border-amber-500/30 text-amber-500'
                                        : variant.type === 'empty'
                                        ? 'border-blue-500/30 text-blue-500'
                                        : 'border-primary/30 text-primary'
                                    }`}
                                  >
                                    {variant.type}
                                  </Badge>
                                  <span className="text-xs font-medium">{variant.name}</span>
                                </div>
                                {expandedVariant === i ? (
                                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                )}
                              </div>
                              {expandedVariant === i && (
                                <div className="mt-2 pl-2 border-l-2 border-border/50">
                                  <p className="text-[10px] text-muted-foreground mb-2">
                                    {variant.description}
                                  </p>
                                  <p className="text-[10px] mb-2">
                                    <span className="text-muted-foreground">Expected: </span>
                                    <span className="text-amber-500">{variant.expected_result}</span>
                                  </p>
                                  <div className="bg-muted/30 rounded p-2 text-[10px] font-mono max-h-32 overflow-auto">
                                    {variant.steps.map((step: any, si: number) => (
                                      <div
                                        key={si}
                                        className={`${step._variant_modified ? 'text-primary font-medium' : 'text-muted-foreground'}`}
                                      >
                                        {si + 1}. {step.type}: {step.selector || step.value}
                                        {step._variant_modified && (
                                          <span className="ml-2 text-primary">
                                            → &quot;{step.value}&quot;
                                          </span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border/50 p-16 text-center bg-card/10">
                  <Code className="w-10 h-10 mx-auto mb-4 text-muted-foreground/20" />
                  <p className="text-sm text-muted-foreground">
                    Select a test to view Playwright code
                  </p>
                </div>
              )}
            </div>
          </div>
        </main>

      </SidebarInset>
    </SidebarProvider>
  );
}

export default function TestsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
      <TestsPageContent />
    </Suspense>
  );
}
