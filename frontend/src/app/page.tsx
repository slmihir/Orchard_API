'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/app-sidebar';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { BrowserView } from '@/components/browser/BrowserView';
import { StepTimeline } from '@/components/timeline/StepTimeline';
import { AssertionEditor } from '@/components/timeline/AssertionEditor';
import { useChatStore } from '@/stores/chatStore';
import { useBrowserStore } from '@/stores/browserStore';
import { useTimelineStore } from '@/stores/timelineStore';
import { useAuthStore } from '@/stores/authStore';
import { AutoflowWebSocket } from '@/lib/socket';
import { chatApi, testsApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Step, StepType, AssertionConfig } from '@/types';

export default function Home() {
  const router = useRouter();
  const [ws, setWs] = useState<AutoflowWebSocket | null>(null);
  const [rightPanelWidth, setRightPanelWidth] = useState(320);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);
  const [assertionEditorOpen, setAssertionEditorOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<Step | undefined>(undefined);

  const { addMessage, setTyping, setSessionId, sessionId } = useChatStore();
  const { setStatus, setScreenshot, setCurrentUrl } = useBrowserStore();
  const { addStep, updateStep } = useTimelineStore();
  const { isAuthenticated } = useAuthStore();

  // Auth check
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!isAuthenticated) return;

    let socket: AutoflowWebSocket | null = null;

    const initSession = async () => {
      try {
        const { session_id } = await chatApi.createSession();
        setSessionId(session_id);

        socket = new AutoflowWebSocket(session_id);
        await socket.connect();

        socket.on('chat', (data: unknown) => {
          const { role, content } = data as { role: string; content: string };
          if (role === 'assistant') {
            setTyping(false);
            addMessage({ role: 'assistant', content });
          }
        });

        socket.on('status', (data: unknown) => {
          const { status } = data as { status: string };
          if (status === 'thinking') {
            setTyping(true);
          } else if (status === 'starting_browser') {
            setStatus('starting');
          } else if (status === 'running') {
            setStatus('running');
          } else if (status === 'stopped') {
            setStatus('stopped');
          }
        });

        socket.on('screenshot', (data: unknown) => {
          const { image } = data as { image: string };
          setScreenshot(image);
        });

        socket.on('action', (data: unknown) => {
          const action = data as {
            type: string;
            selector?: string;
            value?: string;
            screenshot?: string;
            timestamp: string;
            assertion_config?: AssertionConfig;
          };
          addStep({
            type: action.type as StepType,
            selector: action.selector,
            value: action.value,
            screenshot: action.screenshot,
            timestamp: action.timestamp,
            assertion_config: action.assertion_config,
          });

          if (action.type === 'navigate' && action.value) {
            setCurrentUrl(action.value);
          }
        });

        socket.on('complete', (data: unknown) => {
          const { success, message } = data as { success: boolean; message: string };
          setStatus('stopped');
          addMessage({
            role: 'assistant',
            content: success
              ? `Automation complete: ${message}`
              : `Automation failed: ${message}`,
          });
        });

        socket.on('error', (data: unknown) => {
          const { message } = data as { message: string };
          setStatus('error');
          setTyping(false);
          addMessage({
            role: 'assistant',
            content: `Error: ${message}`,
          });
        });

        setWs(socket);
      } catch (error) {
        console.error('Failed to initialize session:', error);
      }
    };

    initSession();

    return () => {
      socket?.disconnect();
    };
  }, [isAuthenticated, addMessage, addStep, setCurrentUrl, setScreenshot, setSessionId, setStatus, setTyping]);

  const handleSendMessage = useCallback(
    (content: string) => {
      if (!ws) return;
      addMessage({ role: 'user', content });
      setTyping(true);
      ws.send('chat', { content });
    },
    [ws, addMessage, setTyping]
  );

  const handleStartAutomation = useCallback(() => {
    if (!ws) return;
    setStatus('starting');
  }, [ws, setStatus]);

  const handleStopAutomation = useCallback(() => {
    if (!ws) return;
    ws.send('stop_automation', {});
    setStatus('stopped');
  }, [ws, setStatus]);

  const handleSaveTest = useCallback(async () => {
    const steps = useTimelineStore.getState().steps;
    if (steps.length === 0) return;

    const firstNavigate = steps.find((s) => s.type === 'navigate');
    const targetUrl = firstNavigate?.value || 'https://example.com';

    const validStepTypes = [
      'navigate', 'click', 'fill', 'wait', 'scroll', 'hover',
      'assert_visible', 'assert_hidden', 'assert_text',
      'assert_value', 'assert_attribute', 'assert_url', 'assert_api'
    ];
    const actionableSteps = steps.filter((s) => validStepTypes.includes(s.type));

    try {
      await testsApi.create({
        name: `Test ${new Date().toLocaleDateString()}`,
        target_url: targetUrl,
        steps: actionableSteps.map((s, i) => ({
          type: s.type,
          selector: s.selector,
          value: s.value,
          order_index: i,
          assertion_config: s.assertion_config,
        })),
      });

      addMessage({
        role: 'assistant',
        content: 'Test saved successfully! You can find it in your test library.',
      });
    } catch (error) {
      console.error('Failed to save test:', error);
    }
  }, [addMessage]);

  const handleRunTest = useCallback(() => {
  }, []);

  const handleAddAssertion = useCallback(() => {
    setEditingStep(undefined);
    setAssertionEditorOpen(true);
  }, []);

  const handleEditStep = useCallback((step: Step) => {
    if (step.type.startsWith('assert_')) {
      setEditingStep(step);
      setAssertionEditorOpen(true);
    }
  }, []);

  const handleSaveAssertion = useCallback((stepData: Partial<Step>) => {
    if (stepData.id) {
      updateStep(stepData.id, stepData);
    } else {
      addStep({
        type: stepData.type!,
        selector: stepData.selector,
        assertion_config: stepData.assertion_config,
        timestamp: stepData.timestamp || new Date().toISOString(),
      });
    }
  }, [addStep, updateStep]);

  const handleRightResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = rightPanelWidth;

      const handleMouseMove = (e: MouseEvent) => {
        const delta = startX - e.clientX;
        setRightPanelWidth(Math.max(280, Math.min(450, startWidth + delta)));
      };

      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [rightPanelWidth]
  );

  const stepsCount = useTimelineStore((state) => state.steps.length);

  if (!isAuthenticated) return null;

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="flex items-center gap-2 px-4 py-2 border-b border-border/50 bg-card/30">
          <SidebarTrigger className="-ml-1" />
          <div className="flex-1" />
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-chart-2 animate-pulse" />
              Session: {sessionId?.slice(0, 8) || '—'}
            </span>
            <span>Steps: {stepsCount}</span>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex overflow-hidden">
          {/* Left Panel - Chat */}
          <div className="w-80 flex-shrink-0 border-r border-border/30 bg-card/20">
            <ChatPanel onSendMessage={handleSendMessage} />
          </div>

          {/* Center Panel - Browser */}
          <div className="flex-1 bg-background">
            <BrowserView
              onStart={handleStartAutomation}
              onStop={handleStopAutomation}
            />
          </div>

          {/* Right resize handle */}
          {!isRightCollapsed && (
            <div className="resize-handle" onMouseDown={handleRightResize} />
          )}

          {/* Right Panel - Timeline */}
          <div
            className={cn(
              'flex-shrink-0 border-l border-border/30 bg-card/20 transition-all duration-300',
              isRightCollapsed ? 'w-12' : ''
            )}
            style={{ width: isRightCollapsed ? 48 : rightPanelWidth }}
          >
            {isRightCollapsed ? (
              <div className="h-full flex flex-col items-center py-4">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsRightCollapsed(false)}
                  className="h-8 w-8"
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="h-full flex flex-col relative">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsRightCollapsed(true)}
                  className="absolute top-2 left-2 z-10 h-6 w-6 opacity-0 hover:opacity-100 transition-opacity"
                >
                  <ChevronRight className="w-3 h-3" />
                </Button>
                <StepTimeline
                  onSave={handleSaveTest}
                  onRun={handleRunTest}
                  onAddAssertion={handleAddAssertion}
                  onEditStep={handleEditStep}
                />
              </div>
            )}
          </div>
        </main>

        {/* Assertion Editor Dialog */}
        <AssertionEditor
          open={assertionEditorOpen}
          onOpenChange={setAssertionEditorOpen}
          step={editingStep}
          onSave={handleSaveAssertion}
        />
      </SidebarInset>
    </SidebarProvider>
  );
}
