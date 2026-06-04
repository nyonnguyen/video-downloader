import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { MediaFileResponse, SubtitleCue } from "@/lib/types";

interface Props {
  subtitle: MediaFileResponse;
  parentVideo?: MediaFileResponse | null;
  onClose: () => void;
  /** Called when a new subtitle file is created (translation save-as-new). */
  onSubtitleCreated?: (m: MediaFileResponse) => void;
  /** Called when the current subtitle is updated in-place. */
  onSubtitleUpdated?: (m: MediaFileResponse) => void;
  /** Hand the subtitle off to the voice form on the parent video. */
  onGenerateVoice?: (subtitle: MediaFileResponse) => void;
}

const COMMON_LANGS = [
  ["en", "English"],
  ["vi", "Vietnamese"],
  ["zh-CN", "Chinese (Simplified)"],
  ["zh-TW", "Chinese (Traditional)"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
  ["fr", "French"],
  ["de", "German"],
  ["es", "Spanish"],
  ["pt", "Portuguese"],
  ["ru", "Russian"],
  ["th", "Thai"],
  ["id", "Indonesian"],
  ["ar", "Arabic"],
];

export function SubtitleEditor({
  subtitle,
  parentVideo,
  onClose,
  onSubtitleCreated,
  onSubtitleUpdated,
  onGenerateVoice,
}: Props) {
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [original, setOriginal] = useState<SubtitleCue[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [targetLang, setTargetLang] = useState("en");
  const [saveAsNew, setSaveAsNew] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getSubtitleCues(subtitle.id)
      .then((r) => {
        setCues(r.cues);
        setOriginal(r.cues);
      })
      .catch((e) => setErr(e.message || String(e)))
      .finally(() => setLoading(false));
  }, [subtitle.id]);

  const dirty = useMemo(() => JSON.stringify(cues) !== JSON.stringify(original), [cues, original]);

  function updateText(idx: number, text: string) {
    setCues((prev) => prev.map((c, i) => (i === idx ? { ...c, text } : c)));
  }
  function updateTiming(idx: number, key: "start_sec" | "end_sec", v: string) {
    const num = parseTs(v);
    if (Number.isNaN(num)) return;
    setCues((prev) => prev.map((c, i) => (i === idx ? { ...c, [key]: num } : c)));
  }

  async function save() {
    setBusy(true); setErr(null); setInfo(null);
    try {
      const updated = await api.updateSubtitleCues(subtitle.id, cues);
      setOriginal(cues);
      setInfo("Subtitle saved.");
      onSubtitleUpdated?.(updated);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally { setBusy(false); }
  }

  async function translate() {
    setBusy(true); setErr(null); setInfo(null);
    try {
      const result = await api.translateSubtitle(subtitle.id, {
        target_language: targetLang,
        save_as_new: saveAsNew,
      });
      if (saveAsNew) {
        setInfo(`Translated subtitle saved as "${result.filename}".`);
        onSubtitleCreated?.(result);
      } else {
        setInfo("Subtitle translated in place. Reloading cues…");
        const r = await api.getSubtitleCues(subtitle.id);
        setCues(r.cues);
        setOriginal(r.cues);
        onSubtitleUpdated?.(result);
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="card max-w-3xl w-full my-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <div className="font-medium truncate">{subtitle.filename}</div>
            <div className="text-xs text-muted">
              Subtitle editor · {cues.length} cue{cues.length === 1 ? "" : "s"}
              {parentVideo && ` · for ${parentVideo.filename}`}
            </div>
          </div>
          <button className="btn-ghost text-xs" onClick={onClose}>Close</button>
        </div>

        <div className="border border-border rounded-md p-2 mb-3 flex flex-wrap items-end gap-2 bg-card/40">
          <label className="block">
            <div className="text-xs text-muted mb-1">Translate to</div>
            <select className="input max-w-[200px]" value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
              {COMMON_LANGS.map(([code, name]) => (
                <option key={code} value={code}>{name} ({code})</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={saveAsNew} onChange={(e) => setSaveAsNew(e.target.checked)} />
            <span className="text-xs">Save translation as a new subtitle file (recommended)</span>
          </label>
          <div className="flex-1" />
          <button className="btn text-sm" onClick={translate} disabled={busy || cues.length === 0}>
            {busy ? "…" : "Translate"}
          </button>
          {onGenerateVoice && parentVideo && (
            <button className="btn-ghost text-sm" onClick={() => onGenerateVoice(subtitle)} disabled={busy}>
              Generate voice from this subtitle
            </button>
          )}
        </div>

        {err && <div className="text-red-400 text-sm mb-2">{err}</div>}
        {info && <div className="text-green-400 text-sm mb-2">{info}</div>}

        {loading ? (
          <div className="text-muted">Loading cues…</div>
        ) : cues.length === 0 ? (
          <div className="text-muted">No cues found in this subtitle.</div>
        ) : (
          <div className="max-h-[55vh] overflow-y-auto border border-border rounded-md divide-y divide-border">
            {cues.map((c, i) => (
              <div key={i} className="flex gap-2 p-2 items-start">
                <div className="text-xs text-muted w-8 text-right pt-1.5 select-none">{i + 1}</div>
                <div className="grid grid-cols-2 gap-1 w-44 shrink-0">
                  <input
                    className="input !py-1 text-xs font-mono"
                    value={formatTs(c.start_sec)}
                    onChange={(e) => updateTiming(i, "start_sec", e.target.value)}
                    title="Start (HH:MM:SS.mmm)"
                  />
                  <input
                    className="input !py-1 text-xs font-mono"
                    value={formatTs(c.end_sec)}
                    onChange={(e) => updateTiming(i, "end_sec", e.target.value)}
                    title="End"
                  />
                </div>
                <textarea
                  className="input !py-1 text-sm flex-1 min-h-[2rem]"
                  rows={Math.min(3, Math.max(1, Math.ceil((c.text?.length || 0) / 60)))}
                  value={c.text}
                  onChange={(e) => updateText(i, e.target.value)}
                />
              </div>
            ))}
          </div>
        )}

        <div className="mt-3 flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onClose}>Close</button>
          <button className="btn text-sm" onClick={save} disabled={!dirty || busy || loading}>
            {busy ? "…" : dirty ? "Save changes" : "Saved"}
          </button>
        </div>
      </div>
    </div>
  );
}

function formatTs(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.round((sec - Math.floor(sec)) * 1000);
  const pad = (n: number, w = 2) => n.toString().padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
}

function parseTs(s: string): number {
  s = s.trim().replace(",", ".");
  if (!s) return NaN;
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  const m = s.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?$/);
  if (!m) return NaN;
  const h = parseInt(m[1] || "0", 10);
  const mi = parseInt(m[2], 10);
  const sec = parseInt(m[3], 10);
  const ms = parseInt((m[4] || "0").padEnd(3, "0").slice(0, 3), 10);
  return h * 3600 + mi * 60 + sec + ms / 1000;
}
