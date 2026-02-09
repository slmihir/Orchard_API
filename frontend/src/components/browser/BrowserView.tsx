'use client';

import { Monitor, Globe, RefreshCw, Square, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useBrowserStore } from '@/stores/browserStore';
import { cn } from '@/lib/utils';

interface BrowserViewProps {
  onStart?: () => void;
  onStop?: () => void;
}

export function BrowserView({ onStart, onStop }: BrowserViewProps) {
  const { status, screenshot, currentUrl } = useBrowserStore();

  const isRunning = status === 'running' || status === 'starting';

  return (
    <div className="flex flex-col h-full">
      {/* Browser chrome */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50 bg-muted/20">
        {/* Window controls */}
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-destructive/60" />
          <div className="w-3 h-3 rounded-full bg-chart-4/60" />
          <div className="w-3 h-3 rounded-full bg-chart-2/60" />
        </div>

        {/* URL bar */}
        <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-md bg-input/50 border border-border/50">
          <Globe className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground font-mono truncate">
            {currentUrl || 'about:blank'}
          </span>
        </div>

        {/* Controls */}
        <div className="flex gap-1">
          {isRunning ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onStop}
              className="text-destructive hover:text-destructive"
            >
              <Square className="w-3.5 h-3.5" />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onStart}
              className="text-primary hover:text-primary"
            >
              <Play className="w-3.5 h-3.5" />
            </Button>
          )}
          <Button variant="ghost" size="icon-sm">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Browser viewport */}
      <div className="flex-1 relative bg-muted/10 overflow-hidden">
        {screenshot ? (
          <div className="absolute inset-0 scanlines">
            <img
              src={`data:image/jpeg;base64,${screenshot}`}
              alt="Browser view"
              className="w-full h-full object-contain"
            />
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center grid-pattern">
            <div
              className={cn(
                'w-16 h-16 rounded-2xl flex items-center justify-center mb-4',
                isRunning
                  ? 'bg-primary/20 text-primary pulse-live'
                  : 'bg-muted/50 text-muted-foreground'
              )}
            >
              <Monitor className="w-8 h-8" />
            </div>
            <h3 className="text-sm font-medium mb-1">
              {status === 'idle' && 'Browser Ready'}
              {status === 'starting' && 'Starting Browser...'}
              {status === 'running' && 'Running Automation...'}
              {status === 'stopped' && 'Browser Stopped'}
              {status === 'error' && 'Browser Error'}
            </h3>
            <p className="text-xs text-muted-foreground max-w-[240px] text-center">
              {status === 'idle' &&
                'Start a conversation to begin browser automation'}
              {status === 'starting' && 'Initializing headless browser...'}
              {status === 'running' && 'AI agent is performing actions'}
              {status === 'stopped' && 'Automation complete'}
              {status === 'error' && 'An error occurred during automation'}
            </p>
          </div>
        )}

        {/* Status indicator */}
        {isRunning && (
          <div className="absolute top-3 right-3 flex items-center gap-2 px-2 py-1 rounded-full bg-background/80 backdrop-blur-sm border border-primary/30">
            <span className="w-2 h-2 rounded-full bg-primary pulse-live" />
            <span className="text-[10px] font-medium text-primary uppercase tracking-wider">
              Live
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
