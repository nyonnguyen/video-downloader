import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useLibraryStore } from "@/store/library";
import { useTasksStore } from "@/store/tasks";
import type { AnalyzeResponse } from "@/lib/types";

type Mode = "url" | "upload";

interface Props {
  onClose: () => void;
  onQueued?: (taskId: string) => void;
}

export function AddMediaPanel({ onClose, onQueued }: Props) {
  const [mode, setMode] = useState<Mode>("url");

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            className={"btn-ghost text-sm " + (mode === "url" ? "border-accent text-white" : "")}
            onClick={() => setMode("url")}
          >
            From URL
          </button>
          <button
            className={"btn-ghost text-sm " + (mode === "upload" ? "border-accent text-white" : "")}
            onClick={() => setMode("upload")}
          >
            Upload local file
          </button>
        </div>
        <button className="btn-ghost text-xs" onClick={onClose}>Close</button>
      </div>

      {mode === "url" ? <UrlForm onQueued={onQueued} /> : <UploadForm onClose={onClose} />}
    </div>
  );
}

function UrlForm({ onQueued }: { onQueued?: (taskId: string) => void }) {
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState<AnalyzeResponse | null>(null);
  const [quality, setQuality] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function analyze() {
    setBusy(true); setErr(null); setInfo(null);
    try {
      const r = await api.analyze(url.trim());
      setInfo(r);
      setQuality(r.suggested_quality || (r.available_qualities[0] ?? ""));
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function enqueue() {
    setBusy(true); setErr(null);
    try {
      const { task_id } = await api.createDownload({
        url: url.trim(),
        quality,
        title: info?.title ?? undefined,
        thumbnail: info?.thumbnail ?? undefined,
      });
      // Surface the new task in the in-progress list right away, even before the worker
      // broadcasts its first WS event (especially relevant when the queue is busy).
      await useTasksStore.getState().fetch();
      onQueued?.(task_id);
      setInfo(null); setUrl(""); setQuality("");
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          className="input"
          placeholder="Paste a video URL (YouTube, Vimeo, TikTok, Douyin, iXiGua, …)"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && url.trim() && analyze()}
        />
        <button className="btn" onClick={analyze} disabled={!url.trim() || busy}>
          {busy ? "…" : "Analyze"}
        </button>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}

      {info && (
        <div className="border-t border-border pt-3 space-y-3">
          <div className="flex gap-3">
            {info.thumbnail && (
              <img src={info.thumbnail} alt="" className="w-40 h-24 object-cover rounded" />
            )}
            <div className="flex-1 min-w-0">
              <div className="text-xs uppercase tracking-wide text-muted">{info.source}</div>
              <div className="font-medium truncate">{info.title || "(no title detected)"}</div>
              {info.duration != null && (
                <div className="text-xs text-muted">{formatDuration(info.duration)}</div>
              )}
            </div>
          </div>

          <div className="flex gap-2 items-center">
            <label className="text-xs text-muted">Quality:</label>
            <select
              className="input max-w-xs"
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
            >
              {info.available_qualities.map((q) => (
                <option key={q} value={q}>{q}</option>
              ))}
            </select>
            <button className="btn" onClick={enqueue} disabled={busy}>
              Add job
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function UploadForm({ onClose }: { onClose: () => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const upsert = useLibraryStore((s) => s.upsert);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  async function handlePick() {
    const f = inputRef.current?.files?.[0];
    if (!f) return;
    setBusy(true); setErr(null);
    setProgress(`Uploading ${f.name}…`);
    try {
      const mf = await api.uploadMedia(f);
      upsert(mf);
      setProgress(`Added: ${mf.filename}`);
      setTimeout(onClose, 700);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="text-sm text-muted">
        Accepts video (mp4, webm, mkv, …), audio (mp3, wav, m4a, …) and subtitle files (srt, vtt).
      </div>
      <input
        ref={inputRef}
        type="file"
        className="input"
        accept="video/*,audio/*,.srt,.vtt,.ass,.ssa"
        onChange={handlePick}
        disabled={busy}
      />
      {progress && <div className="text-xs text-muted">{progress}</div>}
      {err && <div className="text-red-400 text-sm">{err}</div>}
    </div>
  );
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}
