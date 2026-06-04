import { create } from "zustand";
import { api } from "@/lib/api";
import type { MediaFileResponse } from "@/lib/types";

interface LibraryState {
  items: MediaFileResponse[];
  archived: MediaFileResponse[];
  loading: boolean;
  fetch: (params?: { kind?: string; q?: string }) => Promise<void>;
  fetchArchived: () => Promise<void>;
  upsert: (m: MediaFileResponse) => void;
  removeLocal: (id: string) => void;
}

export const useLibraryStore = create<LibraryState>((set, get) => ({
  items: [],
  archived: [],
  loading: false,

  fetch: async (params) => {
    set({ loading: true });
    try {
      const items = await api.listLibrary({ ...params, archived: false });
      set({ items, loading: false });
    } catch (e) {
      console.error("fetch library failed", e);
      set({ loading: false });
    }
  },

  fetchArchived: async () => {
    try {
      const items = await api.listLibrary({ archived: true });
      set({ archived: items });
    } catch (e) {
      console.error("fetch archive failed", e);
    }
  },

  upsert: (m) => {
    const { items } = get();
    const idx = items.findIndex((x) => x.id === m.id);
    if (idx >= 0) {
      const copy = items.slice();
      copy[idx] = m;
      set({ items: copy });
    } else {
      set({ items: [m, ...items] });
    }
  },

  removeLocal: (id) => {
    const { items, archived } = get();
    set({
      items: items.filter((x) => x.id !== id),
      archived: archived.filter((x) => x.id !== id),
    });
  },
}));
