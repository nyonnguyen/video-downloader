import { useEffect, useState } from "react";
import { useTasksStore } from "@/store/tasks";
import { api } from "@/lib/api";
import { ProgressBar } from "./ProgressBar";
import { TaskLogModal } from "./TaskLogModal";
import clsx from "clsx";

function formatStartedAt(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 1) return "<1s";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function jobDurationSec(t: { started_at?: string | null; finished_at?: string | null; status: string }, now: number): number | null {
  if (!t.started_at) return null;
  const start = new Date(t.started_at).getTime();
  const end = t.finished_at ? new Date(t.finished_at).getTime() : (t.status === "running" ? now : null);
  if (end == null) return null;
  return Math.max(0, (end - start) / 1000);
}

export function JobsTable() {
  const { tasks, ordered, loading, fetch, removeLocal } = useTasksStore();
  const [openId, setOpenId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => { fetch(); }, []);

  // Tick once per second so the running-job duration counts up live.
  useEffect(() => {
    const hasRunning = ordered.some((id) => tasks[id]?.status === "running");
    if (!hasRunning) return;
    const handle = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(handle);
  }, [ordered, tasks]);

  if (loading && ordered.length === 0) {
    return <div className="text-muted">Loading…</div>;
  }
  if (ordered.length === 0) {
    return <div className="text-muted">No jobs yet. Submit a download to see it here.</div>;
  }

  const stop = (e: React.MouseEvent) => e.stopPropagation();

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted text-xs uppercase">
          <tr>
            <th className="py-2 pr-3">Type</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3 w-1/4">Progress</th>
            <th className="py-2 pr-3">Message</th>
            <th className="py-2 pr-3">Started</th>
            <th className="py-2 pr-3">Duration</th>
            <th className="py-2 pr-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((id) => {
            const t = tasks[id];
            const durSec = jobDurationSec(t, now);
            return (
              <tr
                key={id}
                className="border-t border-border cursor-pointer hover:bg-white/[0.02]"
                onClick={() => setOpenId(id)}
                title="Click to view live log"
              >
                <td className="py-2 pr-3">{t.type}</td>
                <td className="py-2 pr-3">
                  <span className={clsx(
                    "badge",
                    t.status === "done" && "bg-emerald-500/20 text-emerald-300",
                    t.status === "running" && "bg-accent/20 text-blue-300",
                    t.status === "error" && "bg-red-500/20 text-red-300",
                    t.status === "cancelled" && "bg-yellow-500/20 text-yellow-300",
                    t.status === "paused" && "bg-orange-500/20 text-orange-300",
                    t.status === "pending" && "bg-white/10 text-muted",
                  )}>
                    {t.status}
                  </span>
                </td>
                <td className="py-2 pr-3"><ProgressBar value={t.progress} status={t.status} /></td>
                <td className="py-2 pr-3 truncate max-w-xs">{t.error ? <span className="text-red-400">{t.error}</span> : t.message}</td>
                <td className="py-2 pr-3 text-muted text-xs whitespace-nowrap">{formatStartedAt(t.started_at)}</td>
                <td className="py-2 pr-3 text-muted text-xs whitespace-nowrap">{durSec == null ? "—" : formatDuration(durSec)}</td>
                <td className="py-2 pr-3 text-right space-x-2" onClick={stop}>
                  {t.status === "running" && (
                    <>
                      <button className="btn-ghost text-xs" onClick={() => api.pauseTask(id)}>Pause</button>
                      <button className="btn-ghost text-xs" onClick={() => api.cancelTask(id)}>Cancel</button>
                    </>
                  )}
                  {t.status === "pending" && (
                    <>
                      <button className="btn-ghost text-xs" onClick={() => api.pauseTask(id)}>Pause</button>
                      <button className="btn-ghost text-xs" onClick={() => api.cancelTask(id)}>Cancel</button>
                    </>
                  )}
                  {t.status === "paused" && (
                    <button className="btn-ghost text-xs" onClick={() => api.resumeTask(id)}>Resume</button>
                  )}
                  {(t.status === "error" || t.status === "cancelled" || t.status === "paused") && (
                    <button className="btn-ghost text-xs" onClick={() => api.retryTask(id)}>Retry</button>
                  )}
                  {t.status !== "running" && (
                    <button
                      className="btn-ghost text-xs"
                      onClick={async () => {
                        await api.deleteTask(id);
                        removeLocal(id);
                      }}
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {openId && <TaskLogModal taskId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
