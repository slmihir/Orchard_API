'use client';

import { useState } from 'react';
import { Check, X, Wand2, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface HealingSuggestion {
  step_index: number;
  original_selector: string;
  suggested_selector: string;
  confidence: number;
  reasoning: string;
  alternative_selectors?: string[];
  auto_approved: boolean;
  context?: {
    url: string;
    error: string;
  };
}

interface HealingDiffProps {
  suggestion: HealingSuggestion;
  onApprove: (suggestion: HealingSuggestion) => void;
  onReject: (suggestion: HealingSuggestion) => void;
  isProcessing?: boolean;
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.85) return 'text-chart-2 bg-chart-2/10 border-chart-2/30';
  if (confidence >= 0.6) return 'text-chart-4 bg-chart-4/10 border-chart-4/30';
  return 'text-destructive bg-destructive/10 border-destructive/30';
};

const getConfidenceLabel = (confidence: number) => {
  if (confidence >= 0.85) return 'High';
  if (confidence >= 0.6) return 'Medium';
  return 'Low';
};

export function HealingDiff({ suggestion, onApprove, onReject, isProcessing }: HealingDiffProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-3 bg-muted/30">
        <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
          <Wand2 className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium">Selector Fix</span>
          <p className="text-xs text-muted-foreground">Step {suggestion.step_index + 1}</p>
        </div>
        <Badge variant="outline" className={`text-[10px] ${getConfidenceColor(suggestion.confidence)}`}>
          {Math.round(suggestion.confidence * 100)}% {getConfidenceLabel(suggestion.confidence)}
        </Badge>
        {suggestion.auto_approved && (
          <Badge className="bg-chart-2/20 text-chart-2 border-chart-2/30 text-[10px]">
            Auto-applied
          </Badge>
        )}
      </div>

      {/* Diff */}
      <div className="p-4 space-y-3">
        {/* Original */}
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] uppercase tracking-wider text-destructive/80 font-medium">Failed</span>
          </div>
          <code className="block px-3 py-2 rounded-md text-xs font-mono bg-destructive/5 text-destructive border border-destructive/20 break-all">
            {suggestion.original_selector}
          </code>
        </div>

        {/* Suggested */}
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] uppercase tracking-wider text-chart-2/80 font-medium">Suggested</span>
          </div>
          <code className="block px-3 py-2 rounded-md text-xs font-mono bg-chart-2/5 text-chart-2 border border-chart-2/20 break-all">
            {suggestion.suggested_selector}
          </code>
        </div>

        {/* Reasoning */}
        {suggestion.reasoning && (
          <div className="p-3 rounded-md bg-muted/30 border border-border">
            <div className="flex items-start gap-2">
              <Sparkles className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
              <p className="text-xs text-muted-foreground leading-relaxed">{suggestion.reasoning}</p>
            </div>
          </div>
        )}

        {/* Expandable details */}
        {(suggestion.context?.url || suggestion.context?.error || suggestion.alternative_selectors?.length) && (
          <>
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {showDetails ? 'Hide details' : 'Show details'}
            </button>

            {showDetails && (
              <div className="space-y-2 text-xs pt-2 border-t border-border">
                {suggestion.context?.url && (
                  <div>
                    <span className="text-muted-foreground">URL: </span>
                    <span className="break-all">{suggestion.context.url}</span>
                  </div>
                )}
                {suggestion.context?.error && (
                  <div>
                    <span className="text-muted-foreground">Error: </span>
                    <span className="text-destructive">{suggestion.context.error}</span>
                  </div>
                )}
                {suggestion.alternative_selectors && suggestion.alternative_selectors.length > 0 && (
                  <div>
                    <span className="text-muted-foreground">Alternatives: </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {suggestion.alternative_selectors.map((sel, i) => (
                        <code key={i} className="text-[10px] bg-muted px-1.5 py-0.5 rounded border border-border font-mono">
                          {sel}
                        </code>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Actions */}
      {!suggestion.auto_approved && (
        <div className="px-4 py-3 border-t border-border bg-muted/20 flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onReject(suggestion)}
            disabled={isProcessing}
            className="text-xs h-8 text-muted-foreground hover:text-destructive"
          >
            <X className="w-3.5 h-3.5 mr-1" />
            Reject
          </Button>
          <Button
            size="sm"
            onClick={() => onApprove(suggestion)}
            disabled={isProcessing}
            className="text-xs h-8"
          >
            <Check className="w-3.5 h-3.5 mr-1" />
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}

interface HealingPanelProps {
  suggestions: HealingSuggestion[];
  onApprove: (suggestion: HealingSuggestion) => void;
  onReject: (suggestion: HealingSuggestion) => void;
  onApproveAll: () => void;
  isProcessing?: boolean;
}

export function HealingPanel({
  suggestions,
  onApprove,
  onReject,
  onApproveAll,
  isProcessing,
}: HealingPanelProps) {
  const pendingSuggestions = suggestions.filter((s) => !s.auto_approved);
  const autoApplied = suggestions.filter((s) => s.auto_approved);

  if (suggestions.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wand2 className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">
            {pendingSuggestions.length > 0
              ? `${pendingSuggestions.length} pending`
              : `${autoApplied.length} applied`}
          </span>
        </div>
        {pendingSuggestions.length > 1 && (
          <Button
            size="sm"
            variant="outline"
            onClick={onApproveAll}
            disabled={isProcessing}
            className="text-xs h-7"
          >
            <Check className="w-3 h-3 mr-1" />
            Apply All
          </Button>
        )}
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {suggestions.map((suggestion, i) => (
          <HealingDiff
            key={`${suggestion.step_index}-${i}`}
            suggestion={suggestion}
            onApprove={onApprove}
            onReject={onReject}
            isProcessing={isProcessing}
          />
        ))}
      </div>
    </div>
  );
}

/* Inline Approval for Test Execution */
interface InlineApprovalProps {
  stepIndex: number;
  originalSelector: string;
  suggestedSelector: string;
  confidence: number;
  reasoning?: string;
  onApprove: () => void;
  onReject: () => void;
}

export function InlineApprovalDialog({
  stepIndex,
  originalSelector,
  suggestedSelector,
  confidence,
  reasoning,
  onApprove,
  onReject,
}: InlineApprovalProps) {
  return (
    <div className="rounded-lg border border-primary/50 bg-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-primary/5 flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
          <Wand2 className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium">Fix Required</span>
          <p className="text-xs text-muted-foreground">Step {stepIndex + 1} failed</p>
        </div>
        <Badge variant="outline" className={`text-[10px] ${getConfidenceColor(confidence)}`}>
          {Math.round(confidence * 100)}%
        </Badge>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Failed */}
        <div>
          <span className="text-[10px] uppercase tracking-wider text-destructive/80 font-medium">Failed</span>
          <code className="block mt-1 px-3 py-2 rounded-md text-xs font-mono bg-destructive/5 text-destructive border border-destructive/20 break-all">
            {originalSelector}
          </code>
        </div>

        {/* Suggested */}
        <div>
          <span className="text-[10px] uppercase tracking-wider text-chart-2/80 font-medium">Suggested</span>
          <code className="block mt-1 px-3 py-2 rounded-md text-xs font-mono bg-chart-2/5 text-chart-2 border border-chart-2/20 break-all">
            {suggestedSelector}
          </code>
        </div>

        {/* Reasoning */}
        {reasoning && (
          <div className="p-3 rounded-md bg-muted/30 border border-border">
            <div className="flex items-start gap-2">
              <Sparkles className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
              <p className="text-xs text-muted-foreground leading-relaxed">{reasoning}</p>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-border bg-muted/20 flex items-center justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onReject}
          className="text-xs h-8 text-muted-foreground hover:text-destructive"
        >
          <X className="w-3.5 h-3.5 mr-1" />
          Reject
        </Button>
        <Button
          size="sm"
          onClick={onApprove}
          className="text-xs h-8"
        >
          <Check className="w-3.5 h-3.5 mr-1" />
          Approve
        </Button>
      </div>
    </div>
  );
}
