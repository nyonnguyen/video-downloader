import clsx from "clsx";

export function ProgressBar({ value, status }: { value: number; status?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="w-full h-2 bg-border rounded overflow-hidden">
      <div
        className={clsx(
          "h-full transition-all",
          status === "error" ? "bg-red-500" :
          status === "done" ? "bg-emerald-500" :
          "bg-accent",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
