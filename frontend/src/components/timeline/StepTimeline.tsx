'use client';

import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  Clock,
  Save,
  Trash2,
  Play,
  Plus,
  MousePointer,
  Type,
  Navigation,
  Timer,
  CheckCircle2,
  Eye,
  EyeOff,
  FileText,
  FormInput,
  Tag,
  Link,
  Globe,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { useTimelineStore } from '@/stores/timelineStore';
import { StepCard } from './StepCard';
import { StepType, Step } from '@/types';
import { cn } from '@/lib/utils';

const stepTypeIcons: Record<StepType, React.ReactNode> = {
  // Action steps
  navigate: <Navigation className="w-3 h-3" />,
  click: <MousePointer className="w-3 h-3" />,
  fill: <Type className="w-3 h-3" />,
  wait: <Timer className="w-3 h-3" />,
  scroll: <Navigation className="w-3 h-3 rotate-90" />,
  hover: <MousePointer className="w-3 h-3" />,
  // Assertion steps
  assert_visible: <Eye className="w-3 h-3" />,
  assert_hidden: <EyeOff className="w-3 h-3" />,
  assert_text: <FileText className="w-3 h-3" />,
  assert_value: <FormInput className="w-3 h-3" />,
  assert_attribute: <Tag className="w-3 h-3" />,
  assert_url: <Link className="w-3 h-3" />,
  assert_api: <Globe className="w-3 h-3" />,
};

interface StepTimelineProps {
  onSave?: () => void;
  onRun?: () => void;
  onAddAssertion?: () => void;
  onEditStep?: (step: Step) => void;
}

export function StepTimeline({ onSave, onRun, onAddAssertion, onEditStep }: StepTimelineProps) {
  const { steps, reorderSteps, removeStep, selectStep, selectedStepId } =
    useTimelineStore();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = steps.findIndex((s) => s.id === active.id);
      const newIndex = steps.findIndex((s) => s.id === over.id);
      reorderSteps(oldIndex, newIndex);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Steps</h2>
            <p className="text-xs text-muted-foreground">
              {steps.length} action{steps.length !== 1 ? 's' : ''} captured
            </p>
          </div>
        </div>
        <Badge variant="outline" className="text-[10px]">
          Drag to reorder
        </Badge>
      </div>

      {/* Steps list */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-3 space-y-2">
          {steps.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-2xl bg-muted/50 flex items-center justify-center mb-4">
                <Plus className="w-6 h-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-medium mb-1">No steps yet</h3>
              <p className="text-xs text-muted-foreground max-w-[180px]">
                Start the automation to capture browser actions
              </p>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={steps.map((s) => s.id)}
                strategy={verticalListSortingStrategy}
              >
                {steps.map((step, index) => (
                  <StepCard
                    key={step.id}
                    step={step}
                    index={index}
                    icon={stepTypeIcons[step.type]}
                    isSelected={selectedStepId === step.id}
                    onSelect={() => selectStep(step.id)}
                    onDelete={() => removeStep(step.id)}
                    onEdit={onEditStep ? () => onEditStep(step) : undefined}
                  />
                ))}
              </SortableContext>
            </DndContext>
          )}
        </div>
        </ScrollArea>
      </div>

      {/* Actions */}
      {steps.length > 0 && (
        <div className="flex-shrink-0 p-3 border-t border-border/50 space-y-2 bg-card/50">
          {/* Add Assertion button */}
          {onAddAssertion && (
            <Button
              onClick={onAddAssertion}
              variant="outline"
              className="w-full gap-2 border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10 hover:text-emerald-400"
            >
              <ShieldCheck className="w-4 h-4" />
              Add Assertion
            </Button>
          )}
          <Button
            onClick={onSave}
            className="w-full gap-2"
            variant="default"
          >
            <Save className="w-4 h-4" />
            Save Test
          </Button>
          <div className="flex gap-2">
            <Button
              onClick={onRun}
              variant="outline"
              className="flex-1 gap-2"
            >
              <Play className="w-4 h-4" />
              Run
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="text-destructive hover:text-destructive"
              onClick={() => useTimelineStore.getState().clearSteps()}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
