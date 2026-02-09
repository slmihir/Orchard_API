import { create } from 'zustand';
import { Step } from '@/types';

interface TimelineState {
  steps: Step[];
  selectedStepId: string | null;
  addStep: (step: Omit<Step, 'id'>) => void;
  updateStep: (id: string, updates: Partial<Step>) => void;
  removeStep: (id: string) => void;
  reorderSteps: (fromIndex: number, toIndex: number) => void;
  selectStep: (id: string | null) => void;
  clearSteps: () => void;
  setSteps: (steps: Step[]) => void;
}

export const useTimelineStore = create<TimelineState>((set) => ({
  steps: [],
  selectedStepId: null,

  addStep: (step) => set((state) => ({
    steps: [
      ...state.steps,
      {
        ...step,
        id: crypto.randomUUID(),
      },
    ],
  })),

  updateStep: (id, updates) => set((state) => ({
    steps: state.steps.map((step) =>
      step.id === id ? { ...step, ...updates } : step
    ),
  })),

  removeStep: (id) => set((state) => ({
    steps: state.steps.filter((step) => step.id !== id),
    selectedStepId: state.selectedStepId === id ? null : state.selectedStepId,
  })),

  reorderSteps: (fromIndex, toIndex) => set((state) => {
    const newSteps = [...state.steps];
    const [removed] = newSteps.splice(fromIndex, 1);
    newSteps.splice(toIndex, 0, removed);
    return { steps: newSteps };
  }),

  selectStep: (id) => set({ selectedStepId: id }),

  clearSteps: () => set({ steps: [], selectedStepId: null }),

  setSteps: (steps) => set({ steps }),
}));
