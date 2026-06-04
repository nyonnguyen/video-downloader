import { useEffect, useRef } from "react";
import { useTasksStore } from "@/store/tasks";
import { ProgressBar } from "./ProgressBar";
import clsx from "clsx";

interface Props {
  taskId: string;
  onClose: () => void;
}

export function TaskLogModal({ taskId, onClose }: Props) {
  const task = useTasksStore((s) => s.tasks[taskId]);
  const lines = useTasksStore((s) => s.logs[taskId] ?? []);
  const loadLog = useTasksStore((s) => s.loadLog);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadLog(taskId);
  }, [taskId, loadLog]);

  // Auto-scroll to bottom as new lines arrive (only if user hasn't scrolled up).
  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines.length]);

  // Close on Escape.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!task) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-3xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 pb-3 border-b border-border">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted uppercase tracking-wide">{task.type}</span>
              <span className={clsx(
                "badge",
                task.status === "done" && "bg-emerald-500/20 text-emerald-300",
                task.status === "running" && "bg-accent/20 text-blue-300",
                task.status === "error" && "bg-red-500/20 text-red-300",
                task.status === "cancelled" && "bg-yellow-500/20 text-yellow-300",
                task.status === "paused" && "bg-orange-500/20 text-orange-300",
                task.status === "pending" && "bg-white/10 text-muted",
              )}>
                {task.status}
              </span>
            </div>
            <div className="text-xs text-muted mt-1 font-mono truncate">{task.id}</div>
            <div className="mt-2 max-w-xl">
              <ProgressBar value={task.progress} status={task.status} />
            </div>
            {task.message && <div className="text-sm mt-2">{task.message}</div>}
            {task.error && <div className="text-sm mt-1 text-red-400">{task.error}</div>}
          </div>
          <button className="btn-ghost text-xs" onClick={onClose}>Close</button>
        </div>

        <div
          ref={bodyRef}
          className="flex-1 overflow-y-auto mt-3 font-mono text-xs whitespace-pre-wrap leading-relaxed bg-black/30 rounded p-3"
        >
          {lines.length === 0 ? (
            <div className="text-muted">No log lines yet — waiting for the worker to pick this task up.</div>
          ) : (
            lines.map((l, i) => <div key={i}>{l}</div>)
          )}
        </div>
      </div>
    </div>
  );
}
