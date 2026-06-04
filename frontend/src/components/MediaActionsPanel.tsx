import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ConvertPreset, MediaFileResponse, VoiceInfo, WhisperModelInfo } from "@/lib/types";

type ActionKind = "convert" | "subtitle" | "voice";

interface Props {
  media: MediaFileResponse;
  subtitles: MediaFileResponse[];
  action: ActionKind;
  preselectSubtitleId?: string | null;
  onClose: () => void;
  onQueued: (taskId: string) => void;
}

export function MediaActionsPanel({ media, subtitles, action, preselectSubtitleId, onClose, onQueued }: Props) {
  return (
    <div className="border border-border rounded-lg p-3 bg-card/60 mt-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">
          {action === "convert" && "Convert"}
          {action === "subtitle" && "Generate subtitle"}
          {action === "voice" && "Generate translated voice"}
        </div>
        <button className="btn-ghost text-xs" onClick={onClose}>Cancel</button>
      </div>

      {action === "convert" && <ConvertForm media={media} onQueued={onQueued} />}
      {action === "subtitle" && <SubtitleForm media={media} onQueued={onQueued} />}
      {action === "voice" && (
        <VoiceForm
          media={media}
          subtitles={subtitles}
          preselectSubtitleId={preselectSubtitleId}
          onQueued={onQueued}
        />
      )}
    </div>
  );
}

function ConvertForm({ media, onQueued }: { media: MediaFileResponse; onQueued: (id: string) => void }) {
  const [presets, setPresets] = useState<ConvertPreset[]>([]);
  const [presetId, setPresetId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listPresets().then((r) => {
      setPresets(r);
      setPresetId(r[0]?.id || "");
    }).catch((e) => setErr(e.message));
  }, []);

  async function submit() {
    if (!presetId) return;
    setBusy(true); setErr(null);
    try {
      const { task_id } = await api.createConvert({ media_file_id: media.id, preset_id: presetId });
      onQueued(task_id);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  }

  const active = presets.find((p) => p.id === presetId);

  return (
    <div className="space-y-3">
      <label className="block">
        <div className="text-xs text-muted mb-1">Preset</div>
        <select className="input" value={presetId} onChange={(e) => setPresetId(e.target.value)}>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        {active && <div className="text-xs text-muted mt-1">{active.description}</div>}
      </label>
      {err && <div className="text-red-400 text-sm">{err}</div>}
      <button className="btn" onClick={submit} disabled={!presetId || busy}>
        {busy ? "…" : "Start convert"}
      </button>
    </div>
  );
}

type SubtitleTarget = "srt_only" | "soft_embed" | "burn_in";

function SubtitleForm({ media, onQueued }: { media: MediaFileResponse; onQueued: (id: string) => void }) {
  const [models, setModels] = useState<WhisperModelInfo[]>([]);
  const [model, setModel] = useState("small");
  const [language, setLanguage] = useState("");
  const [translateEn, setTranslateEn] = useState(false);
  const [target, setTarget] = useState<SubtitleTarget>("srt_only");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listWhisperModels().then(setModels).catch((e) => setErr(e.message));
  }, []);

  const modelInfo = models.find((m) => m.name === model);
  const installedNote = modelInfo?.installed
    ? "✓ installed"
    : `will download ~${modelInfo?.size_mb ?? "?"} MB on first use`;

  async function submit() {
    setBusy(true); setErr(null);
    try {
      const { task_id } = await api.createSubtitle({
        media_file_id: media.id,
        model,
        language: language || undefined,
        translate_to_en: translateEn,
        output_target: target,
        embed_soft: target === "soft_embed",
        burn_in: target === "burn_in",
      });
      onQueued(task_id);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); setConfirming(false); }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <div className="text-xs text-muted mb-1">Whisper model</div>
          <select className="input" value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name} ({m.size_mb} MB){m.installed ? " ✓" : ""}
              </option>
            ))}
          </select>
          <div className="text-xs text-muted mt-1">{installedNote}</div>
        </label>
        <label className="block">
          <div className="text-xs text-muted mb-1">Source language (blank = auto)</div>
          <input className="input" placeholder="e.g. en, vi, zh, ja" value={language} onChange={(e) => setLanguage(e.target.value)} />
        </label>
      </div>

      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-1" checked={translateEn} onChange={(e) => setTranslateEn(e.target.checked)} />
        <div>
          <div>Translate to English</div>
          <div className="text-xs text-muted">Whisper translates non-English audio directly to English subtitles.</div>
        </div>
      </label>

      <div className="border border-border rounded-md p-2 space-y-2">
        <div className="text-xs text-muted uppercase tracking-wide">Output</div>
        <label className="flex items-start gap-2">
          <input type="radio" name="sub_target" className="mt-1" checked={target === "srt_only"} onChange={() => setTarget("srt_only")} />
          <div>
            <div>Subtitle file only <span className="text-xs text-muted">(recommended)</span></div>
            <div className="text-xs text-muted">Keep the original video untouched. Produces an .srt sidecar — the player can toggle it on the original.</div>
          </div>
        </label>
        <label className="flex items-start gap-2">
          <input type="radio" name="sub_target" className="mt-1" checked={target === "soft_embed"} onChange={() => setTarget("soft_embed")} />
          <div>
            <div>Also create a new video with the subtitle muxed in</div>
            <div className="text-xs text-muted">Original is preserved. New MP4 has a toggleable soft subtitle track (mov_text).</div>
          </div>
        </label>
        <label className="flex items-start gap-2">
          <input type="radio" name="sub_target" className="mt-1" checked={target === "burn_in"} onChange={() => setTarget("burn_in")} />
          <div>
            <div>Create a new video with the subtitle burned into pixels</div>
            <div className="text-xs text-muted">Original is preserved. Subtitle is permanent and not toggleable.</div>
          </div>
        </label>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}
      <button className="btn" onClick={() => setConfirming(true)} disabled={busy || media.kind !== "video"}>
        {busy ? "…" : "Generate subtitle"}
      </button>

      {confirming && (
        <ConfirmActionDialog
          title="Generate subtitle"
          onCancel={() => setConfirming(false)}
          onConfirm={submit}
          summary={[
            ["Source video", media.filename],
            ["Whisper model", model],
            ["Source language", language || "auto-detect"],
            ["Translate to English", translateEn ? "yes" : "no"],
            ["Output", target === "srt_only"
              ? "SRT sidecar only — original video unchanged"
              : target === "soft_embed"
                ? "New MP4 with soft subtitle track — original preserved"
                : "New MP4 with burned-in subtitle — original preserved"],
          ]}
        />
      )}
    </div>
  );
}

function ConfirmActionDialog({
  title,
  summary,
  onCancel,
  onConfirm,
}: {
  title: string;
  summary: [string, string][];
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[55] bg-black/70 flex items-center justify-center p-4" onClick={onCancel}>
      <div className="card max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="font-medium text-base mb-2">{title}</div>
        <div className="text-xs text-muted mb-3">Review the settings, then start the task.</div>
        <div className="text-sm space-y-1 mb-4">
          {summary.map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <span className="text-muted w-32 shrink-0">{k}</span>
              <span className="flex-1 break-words">{v}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancel}>Cancel</button>
          <button className="btn text-sm" onClick={onConfirm}>Start</button>
        </div>
      </div>
    </div>
  );
}

type VoiceTarget = "audio_only" | "mux_new" | "mux_new_default";

function VoiceForm({
  media,
  subtitles,
  preselectSubtitleId,
  onQueued,
}: {
  media: MediaFileResponse;
  subtitles: MediaFileResponse[];
  preselectSubtitleId?: string | null;
  onQueued: (id: string) => void;
}) {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [models, setModels] = useState<WhisperModelInfo[]>([]);
  const [locale, setLocale] = useState("en-US");
  const [voice, setVoice] = useState("en-US-AriaNeural");
  const [rate, setRate] = useState("+0%");
  const [useExistingSub, setUseExistingSub] = useState(subtitles.length > 0);
  const [subId, setSubId] = useState<string>(preselectSubtitleId || subtitles[0]?.id || "");
  const [whisperModel, setWhisperModel] = useState("small");
  const [sourceLang, setSourceLang] = useState("");
  const [target, setTarget] = useState<VoiceTarget>("audio_only");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listVoices().then((v) => {
      setVoices(v);
      if (v.length && !v.find((x) => x.short_name === voice)) {
        setVoice(v[0].short_name);
        setLocale(v[0].locale);
      }
    }).catch((e) => setErr(e.message));
    api.listWhisperModels().then(setModels).catch(() => {});
  }, []);

  const locales = useMemo(() => Array.from(new Set(voices.map((v) => v.locale))).sort(), [voices]);
  const localeVoices = useMemo(() => voices.filter((v) => v.locale === locale), [voices, locale]);

  useEffect(() => {
    if (localeVoices.length && !localeVoices.find((v) => v.short_name === voice)) {
      setVoice(localeVoices[0].short_name);
    }
  }, [locale, localeVoices]);

  async function submit() {
    setBusy(true); setErr(null);
    try {
      const { task_id } = await api.createVoice({
        media_file_id: media.id,
        subtitle_file_id: useExistingSub ? subId : undefined,
        whisper_model: useExistingSub ? undefined : whisperModel,
        source_language: useExistingSub ? undefined : (sourceLang || undefined),
        voice,
        rate,
        mux_into_video: target !== "audio_only",
        make_default_track: target === "mux_new_default",
      });
      onQueued(task_id);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); setConfirming(false); }
  }

  return (
    <div className="space-y-3">
      <div className="border border-border rounded-md p-2 space-y-2">
        <label className="flex items-center gap-2">
          <input
            type="radio" name="src" checked={useExistingSub} onChange={() => setUseExistingSub(true)}
            disabled={subtitles.length === 0}
          />
          <span className={subtitles.length === 0 ? "text-muted" : ""}>
            Use existing subtitle ({subtitles.length} available)
          </span>
        </label>
        {useExistingSub && subtitles.length > 0 && (
          <select className="input" value={subId} onChange={(e) => setSubId(e.target.value)}>
            {subtitles.map((s) => (
              <option key={s.id} value={s.id}>{s.filename}</option>
            ))}
          </select>
        )}

        <label className="flex items-center gap-2 pt-1 border-t border-border">
          <input type="radio" name="src" checked={!useExistingSub} onChange={() => setUseExistingSub(false)} />
          <span>Transcribe + translate to English first (whisper)</span>
        </label>
        {!useExistingSub && (
          <div className="grid grid-cols-2 gap-2">
            <select className="input" value={whisperModel} onChange={(e) => setWhisperModel(e.target.value)}>
              {models.map((m) => (
                <option key={m.name} value={m.name}>{m.name} ({m.size_mb} MB){m.installed ? " ✓" : ""}</option>
              ))}
            </select>
            <input className="input" placeholder="source lang (blank = auto)" value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} />
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <div className="text-xs text-muted mb-1">Locale</div>
          <select className="input" value={locale} onChange={(e) => setLocale(e.target.value)}>
            {locales.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <div className="text-xs text-muted mb-1">Voice</div>
          <select className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
            {localeVoices.map((v) => (
              <option key={v.short_name} value={v.short_name}>
                {v.short_name} ({v.gender})
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="block">
        <div className="text-xs text-muted mb-1">Rate (e.g. -10%, +0%, +20%)</div>
        <input className="input max-w-[140px]" value={rate} onChange={(e) => setRate(e.target.value)} />
      </label>

      <div className="border border-border rounded-md p-2 space-y-2">
        <div className="text-xs text-muted uppercase tracking-wide">Output</div>
        <label className="flex items-start gap-2">
          <input type="radio" name="voice_target" className="mt-1" checked={target === "audio_only"} onChange={() => setTarget("audio_only")} />
          <div>
            <div>Audio file only <span className="text-xs text-muted">(recommended)</span></div>
            <div className="text-xs text-muted">Keep the original video untouched. Produces an MP3 sidecar — the player can switch to it without re-encoding.</div>
          </div>
        </label>
        <label className="flex items-start gap-2">
          <input type="radio" name="voice_target" className="mt-1" checked={target === "mux_new"} onChange={() => setTarget("mux_new")} />
          <div>
            <div>Also create a new video with the voice as an extra track</div>
            <div className="text-xs text-muted">Original is preserved. Players keep the original audio by default.</div>
          </div>
        </label>
        <label className="flex items-start gap-2">
          <input type="radio" name="voice_target" className="mt-1" checked={target === "mux_new_default"} onChange={() => setTarget("mux_new_default")} />
          <div>
            <div>Create a new video and make the generated voice the default audio</div>
            <div className="text-xs text-muted">Original video is preserved. Players will play the generated voice automatically.</div>
          </div>
        </label>
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}
      <button className="btn" onClick={() => setConfirming(true)} disabled={busy || media.kind !== "video"}>
        {busy ? "…" : "Generate voice"}
      </button>

      {confirming && (
        <ConfirmActionDialog
          title="Generate translated voice"
          onCancel={() => setConfirming(false)}
          onConfirm={submit}
          summary={[
            ["Source video", media.filename],
            ["Subtitle source", useExistingSub
              ? (subtitles.find((s) => s.id === subId)?.filename || "existing subtitle")
              : `transcribe + translate via whisper (${whisperModel})`],
            ["Voice", `${voice} (${rate})`],
            ["Output", target === "audio_only"
              ? "MP3 only — original video unchanged"
              : target === "mux_new"
                ? "New MP4 with extra audio track — original preserved"
                : "New MP4, generated voice is default audio — original preserved"],
          ]}
        />
      )}
    </div>
  );
}
