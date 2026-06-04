import { create } from "zustand";
import { api } from "@/lib/api";
import type { TaskResponse, WSEvent } from "@/lib/types";

const LOG_LIMIT = 500;

interface TasksState {
  tasks: Record<string, TaskResponse>;
  ordered: string[];           // newest first
  logs: Record<string, string[]>;
  loading: boolean;
  fetch: () => Promise<void>;
  applyEvent: (evt: WSEvent) => void;
  removeLocal: (id: string) => void;
  loadLog: (id: string) => Promise<void>;
}

export const useTasksStore = create<TasksState>((set, get) => ({
  tasks: {},
  ordered: [],
  logs: {},
  loading: false,

  fetch: async () => {
    set({ loading: true });
    try {
      const list = await api.listTasks();
      const tasks: Record<string, TaskResponse> = {};
      const ordered: string[] = [];
      for (const t of list) {
        tasks[t.id] = t;
        ordered.push(t.id);
      }
      set({ tasks, ordered, loading: false });
    } catch (e) {
      console.error("fetch tasks failed", e);
      set({ loading: false });
    }
  },

  applyEvent: (evt) => {
    const { tasks, ordered, logs } = get();

    if (evt.type === "log") {
      const existing = logs[evt.task_id] ?? [];
      const next = existing.concat(evt.line ?? evt.message ?? "");
      const trimmed = next.length > LOG_LIMIT ? next.slice(-LOG_LIMIT) : next;
      set({ logs: { ...logs, [evt.task_id]: trimmed } });
      return;
    }

    const existing = tasks[evt.task_id];
    const next: TaskResponse = existing
      ? { ...existing }
      : {
          id: evt.task_id,
          type: "download",
          status: "pending",
          progress: 0,
          message: "",
          error: null,
          media_file_id: null,
          created_at: new Date().toISOString(),
          started_at: null,
          finished_at: null,
        };

    if (evt.type === "progress") {
      next.status = (evt.status as TaskResponse["status"]) || next.status;
      next.progress = evt.progress ?? next.progress;
      next.message = evt.message ?? next.message;
    } else if (evt.type === "done") {
      next.status = "done";
      next.progress = 1;
      next.message = "Done";
      next.media_file_id = evt.media_file_id ?? next.media_file_id;
      next.finished_at = new Date().toISOString();
    } else if (evt.type === "error") {
      // Backend reuses the "error" event for cancel/pause too — respect the explicit status.
      if (evt.status === "cancelled" || evt.status === "paused") {
        next.status = evt.status;
        next.message = evt.status === "paused" ? "Paused" : "Cancelled";
      } else {
        next.status = next.status === "running" ? "error" : next.status;
        next.error = evt.error || next.error;
        next.message = "Error";
      }
      next.finished_at = new Date().toISOString();
    }

    const newOrdered = ordered.includes(evt.task_id) ? ordered : [evt.task_id, ...ordered];
    set({ tasks: { ...tasks, [evt.task_id]: next }, ordered: newOrdered });
  },

  removeLocal: (id) => {
    const { tasks, ordered, logs } = get();
    const { [id]: _, ...rest } = tasks;
    const { [id]: __, ...restLogs } = logs;
    set({ tasks: rest, ordered: ordered.filter((x) => x !== id), logs: restLogs });
  },

  loadLog: async (id) => {
    try {
      const { lines } = await api.getTaskLog(id);
      const { logs } = get();
      set({ logs: { ...logs, [id]: lines } });
    } catch (e) {
      console.error("loadLog failed", e);
    }
  },
}));
