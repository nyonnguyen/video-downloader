import { useEffect, useState } from "react";

interface AppSettings {
  downloads_dir: string;
  browser: string;
  timeout: number;
  whisper_default_model: string;
  ffmpeg_available: boolean;
  ffmpeg_path: string | null;
}

export function Settings() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then(setS)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-red-400">{err}</div>;
  if (!s) return <div className="text-muted">Loading…</div>;

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <div className="card space-y-3">
        <Row label="Downloads directory" value={s.downloads_dir} />
        <Row label="Browser (Playwright)" value={s.browser} />
        <Row label="Timeout (seconds)" value={s.timeout.toString()} />
        <Row label="Whisper default model" value={s.whisper_default_model} />
        <Row
          label="FFmpeg"
          value={s.ffmpeg_available ? `${s.ffmpeg_path}` : "Not installed"}
          status={s.ffmpeg_available ? "ok" : "warn"}
        />
        {!s.ffmpeg_available && (
          <div className="text-yellow-400 text-sm">
            FFmpeg is required for Convert and Subtitle features. Install with: <code className="text-white">brew install ffmpeg</code>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, status }: { label: string; value: string; status?: "ok" | "warn" }) {
  return (
    <div className="flex justify-between items-start gap-4 border-b border-border last:border-0 pb-2 last:pb-0">
      <div className="text-muted text-sm">{label}</div>
      <div className={"text-sm font-mono " + (status === "warn" ? "text-yellow-400" : "")}>{value}</div>
    </div>
  );
}
