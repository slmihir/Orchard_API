'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Trash2, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Step } from '@/types';
import { cn } from '@/lib/utils';

interface StepCardProps {
  step: Step;
  index: number;
  icon: React.ReactNode;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onEdit?: () => void;
}

export function StepCard({
  step,
  index,
  icon,
  isSelected,
  onSelect,
  onDelete,
  onEdit,
}: StepCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const isAssertion = step.type.startsWith('assert_');

  const getStepLabel = () => {
    const config = step.assertion_config;

    switch (step.type) {
      case 'navigate':
        return `Go to ${step.value || 'URL'}`;
      case 'click':
        return `Click ${step.selector || 'element'}`;
      case 'fill':
        return `Type "${step.value || '...'}"`;
      case 'wait':
        return `Wait ${step.value || '1000'}ms`;
      case 'scroll':
        return `Scroll ${step.selector ? 'to element' : 'down'}`;
      case 'hover':
        return `Hover ${step.selector || 'element'}`;
      // Assertion types
      case 'assert_visible':
        return `Verify visible: ${step.selector || 'element'}`;
      case 'assert_hidden':
        return `Verify hidden: ${step.selector || 'element'}`;
      case 'assert_text':
        return `Verify text ${config?.operator || 'equals'} "${config?.expected || '...'}"`;
      case 'assert_value':
        return `Verify value ${config?.operator || 'equals'} "${config?.expected || '...'}"`;
      case 'assert_attribute':
        return `Verify [${config?.attribute || 'attr'}] ${config?.operator || 'equals'} "${config?.expected || ''}"`;
      case 'assert_url':
        return `Verify URL ${config?.operator || 'contains'} "${config?.expected || ''}"`;
      case 'assert_api':
        return `Verify API ${config?.api_method || ''} ${config?.api_url_pattern || ''} → ${config?.api_status || 200}`;
      default:
        return step.type;
    }
  };

  const getStepTypeColor = () => {
    if (isAssertion) {
      return 'bg-emerald-500/20 text-emerald-500';
    }
    switch (step.type) {
      case 'navigate':
        return 'bg-chart-1/20 text-chart-1';
      case 'click':
        return 'bg-chart-2/20 text-chart-2';
      case 'fill':
        return 'bg-chart-3/20 text-chart-3';
      case 'wait':
        return 'bg-chart-4/20 text-chart-4';
      case 'scroll':
        return 'bg-chart-5/20 text-chart-5';
      case 'hover':
        return 'bg-primary/20 text-primary';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'step-card group relative flex items-center gap-2 p-2 rounded-lg border border-border/50 bg-card/50',
        isSelected && 'border-primary/50 bg-primary/5',
        isDragging && 'dragging z-50'
      )}
      onClick={onSelect}
    >
      {/* Drag handle */}
      <button
        className="flex-shrink-0 p-1 rounded cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground transition-colors"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="w-4 h-4" />
      </button>

      {/* Step number */}
      <div className="flex-shrink-0 w-5 h-5 rounded bg-muted/50 flex items-center justify-center text-[10px] font-mono text-muted-foreground">
        {index + 1}
      </div>

      {/* Step icon */}
      <div
        className={cn(
          'flex-shrink-0 w-6 h-6 rounded flex items-center justify-center',
          getStepTypeColor()
        )}
      >
        {icon}
      </div>

      {/* Step content */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{getStepLabel()}</p>
        {step.selector && step.type !== 'navigate' && (
          <p className="text-[10px] text-muted-foreground font-mono truncate">
            {step.selector}
          </p>
        )}
      </div>

      {/* Thumbnail */}
      {step.screenshot && (
        <div className="flex-shrink-0 w-12 h-8 rounded overflow-hidden border border-border/50">
          <img
            src={`data:image/jpeg;base64,${step.screenshot}`}
            alt=""
            className="w-full h-full object-cover"
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onEdit && (
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
          >
            <Edit2 className="w-3 h-3" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 className="w-3 h-3" />
        </Button>
      </div>
    </div>
  );
}
