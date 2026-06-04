import { useEffect } from "react";
import { useTasksStore } from "@/store/tasks";
import { useLibraryStore } from "@/store/library";

export function Dashboard() {
  const tasks = useTasksStore();
  const library = useLibraryStore();

  useEffect(() => {
    tasks.fetch();
    library.fetch();
  }, []);

  const running = tasks.ordered.filter((id) => tasks.tasks[id].status === "running").length;
  const done = tasks.ordered.filter((id) => tasks.tasks[id].status === "done").length;
  const totalSize = library.items.reduce((a, m) => a + m.size_bytes, 0);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Active jobs" value={running.toString()} />
        <Stat label="Completed" value={done.toString()} />
        <Stat label="Library size" value={`${(totalSize / 1024 / 1024).toFixed(1)} MB`} sub={`${library.items.length} files`} />
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <div className="text-xs text-muted uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}
