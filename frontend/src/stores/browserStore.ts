import { create } from 'zustand';
import { BrowserStatus } from '@/types';

interface BrowserState {
  status: BrowserStatus;
  screenshot: string | null;
  currentUrl: string | null;
  setStatus: (status: BrowserStatus) => void;
  setScreenshot: (screenshot: string) => void;
  setCurrentUrl: (url: string) => void;
  reset: () => void;
}

export const useBrowserStore = create<BrowserState>((set) => ({
  status: 'idle',
  screenshot: null,
  currentUrl: null,

  setStatus: (status) => set({ status }),

  setScreenshot: (screenshot) => set({ screenshot }),

  setCurrentUrl: (url) => set({ currentUrl: url }),

  reset: () => set({
    status: 'idle',
    screenshot: null,
    currentUrl: null,
  }),
}));
