import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useLibraryStore } from "@/store/library";
import { useTasksStore } from "@/store/tasks";
import { api } from "@/lib/api";
import type { MediaFileResponse, TaskResponse } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { MediaActionsPanel } from "./MediaActionsPanel";
import { AddMediaPanel } from "./AddMediaPanel";
import { ProgressBar } from "./ProgressBar";
import { SubtitleEditor } from "./SubtitleEditor";
import {
  LibraryView,
  LibraryViewMode,
  LibraryViewPicker,
} from "./LibraryViews";

type View = "library" | "archive";
type ActionKind = "convert" | "subtitle" | "voice";

const VIEW_MODE_STORAGE_KEY = "library.viewMode";

function loadViewMode(): LibraryViewMode {
  const v = (typeof window !== "undefined" && window.localStorage.getItem(VIEW_MODE_STORAGE_KEY)) || "";
  if (["grid-lg", "grid-sm", "list", "detail", "relations"].includes(v)) {
    return v as LibraryViewMode;
  }
  return "grid-lg";
}

export function LibraryGrid() {
  const nav = useNavigate();
  const { items, archived, loading, fetch, fetchArchived, removeLocal, upsert } = useLibraryStore();
  const { tasks, ordered, fetch: fetchTasks, removeLocal: removeTaskLocal } = useTasksStore();
  const [view, setView] = useState<View>("library");
  const [viewMode, setViewMode] = useState<LibraryViewMode>(loadViewMode);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<string>("");
  const [selected, setSelected] = useState<MediaFileResponse | null>(null);
  const [subs, setSubs] = useState<MediaFileResponse[]>([]);
  const [activeSubId, setActiveSubId] = useState<string | null>(null);
  const [audioTracks, setAudioTracks] = useState<MediaFileResponse[]>([]);
  const [activeAudioId, setActiveAudioId] = useState<string | null>(null);
  const [editSub, setEditSub] = useState<MediaFileResponse | null>(null);
  const [action, setAction] = useState<ActionKind | null>(null);
  const [actionSubId, setActionSubId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<null | { kind: "archive" | "permanent"; media: MediaFileResponse }>(null);
  const [bulkConfirm, setBulkConfirm] = useState<null | { kind: "archive" | "permanent"; ids: string[] }>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showAdd, setShowAdd] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    try { window.localStorage.setItem(VIEW_MODE_STORAGE_KEY, viewMode); } catch {}
  }, [viewMode]);

  useEffect(() => {
    fetch({ kind: kind || undefined, q: search || undefined });
  }, [kind]);

  useEffect(() => {
    fetchTasks();
  }, []);

  useEffect(() => {
    if (view === "archive") fetchArchived();
    setSelectedIds(new Set());
  }, [view]);

  // For relations view, we need every item (videos + their subtitle/audio children),
  // not just whatever the kind filter produces.
  useEffect(() => {
    if (viewMode === "relations" && kind) {
      setKind("");
    }
  }, [viewMode]);

  const inProgress = useMemo<TaskResponse[]>(() => {
    if (view !== "library") return [];
    return ordered
      .map((id) => tasks[id])
      .filter(
        (t) =>
          t &&
          t.type === "download" &&
          (t.status === "pending" || t.status === "running" || t.status === "error"),
      );
  }, [tasks, ordered, view]);

  useEffect(() => {
    if (!selected || selected.kind !== "video") {
      setSubs([]); setActiveSubId(null);
      setAudioTracks([]); setActiveAudioId(null);
      return;
    }
    api.listSubtitlesFor(selected.id).then((list) => {
      setSubs(list);
      setActiveSubId(list[0]?.id ?? null);
    }).catch(() => setSubs([]));
    api.listAudioTracksFor(selected.id).then((list) => {
      setAudioTracks(list);
      setActiveAudioId(null);
    }).catch(() => setAudioTracks([]));
  }, [selected?.id]);

  const list = view === "library" ? items : archived;

  useEffect(() => {
    // Drop selected ids that disappeared from the current list (e.g. after fetch/filter).
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const live = new Set(list.map((m) => m.id));
      let changed = false;
      const next = new Set<string>();
      prev.forEach((id) => {
        if (live.has(id)) next.add(id);
        else changed = true;
      });
      return changed ? next : prev;
    });
  }, [list]);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleGroup(ids: string[]) {
    setSelectedIds((prev) => {
      if (ids.length === 0) return prev;
      const allIn = ids.every((id) => prev.has(id));
      const next = new Set(prev);
      if (allIn) ids.forEach((id) => next.delete(id));
      else ids.forEach((id) => next.add(id));
      return next;
    });
  }
  function selectAllOnPage() {
    setSelectedIds(new Set(list.map((m) => m.id)));
  }
  function clearSelection() {
    setSelectedIds(new Set());
  }
  const isSelected = (id: string) => selectedIds.has(id);
  const allSelectedOnPage = list.length > 0 && list.every((m) => selectedIds.has(m.id));

  async function doBulk(kind: "archive" | "permanent", ids: string[]) {
    const fn = kind === "archive" ? api.archiveMedia : api.permanentDelete;
    const results = await Promise.allSettled(ids.map((id) => fn(id)));
    const failed: string[] = [];
    results.forEach((r, i) => {
      if (r.status === "fulfilled") {
        removeLocal(ids[i]);
        if (selected?.id === ids[i]) setSelected(null);
      } else {
        failed.push(ids[i]);
      }
    });
    if (view === "archive" && kind === "archive") fetchArchived();
    setSelectedIds(new Set(failed));
    if (failed.length > 0) {
      setErr(`Failed on ${failed.length} of ${ids.length} item${ids.length === 1 ? "" : "s"}.`);
    }
  }

  async function doArchive(m: MediaFileResponse) {
    try {
      await api.archiveMedia(m.id);
      removeLocal(m.id);
      if (selected?.id === m.id) setSelected(null);
      if (view === "archive") fetchArchived();
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  async function doRestore(m: MediaFileResponse) {
    try {
      const restored = await api.restoreMedia(m.id);
      removeLocal(m.id);
      upsert(restored);
      fetchArchived();
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  async function doPermanentDelete(m: MediaFileResponse) {
    try {
      await api.permanentDelete(m.id);
      removeLocal(m.id);
      if (selected?.id === m.id) setSelected(null);
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  function openMedia(m: MediaFileResponse) {
    if (m.kind === "subtitle") {
      if (m.parent_id) {
        const parent = items.find((x) => x.id === m.parent_id) || archived.find((x) => x.id === m.parent_id);
        if (parent && parent.kind === "video") setSelected(parent);
      }
      setEditSub(m);
      return;
    }
    setSelected(m);
    setAction(null);
    setActionSubId(null);
  }

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    fetch({ kind: kind || undefined, q: search || undefined });
  }

  const progressCards = inProgress.map((t) => (
    <InProgressCard
      key={t.id}
      task={t}
      onCancel={() => api.cancelTask(t.id)}
      onRetry={() => api.retryTask(t.id)}
      onDismiss={async () => {
        await api.deleteTask(t.id);
        removeTaskLocal(t.id);
      }}
    />
  ));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex gap-2">
          <button
            className={"btn-ghost text-sm " + (view === "library" ? "border-accent text-white" : "")}
            onClick={() => setView("library")}
          >
            Library ({items.length})
          </button>
          <button
            className={"btn-ghost text-sm " + (view === "archive" ? "border-accent text-white" : "")}
            onClick={() => setView("archive")}
          >
            Archive ({archived.length})
          </button>
        </div>
        {view === "library" && (
          <div className="flex gap-2">
            <button className="btn" onClick={() => setShowAdd((x) => !x)}>
              {showAdd ? "Close" : "+ Add media"}
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <LibraryViewPicker mode={viewMode} onChange={setViewMode} />
        <div className="text-xs text-muted">
          {viewMode === "relations" && "Tree of original videos and derivatives (subtitles, audio, voiced/embedded variants)."}
        </div>
      </div>

      {view === "library" && showAdd && (
        <AddMediaPanel onClose={() => setShowAdd(false)} onQueued={() => setShowAdd(false)} />
      )}

      {view === "library" && viewMode !== "relations" && (
        <form className="flex gap-2" onSubmit={onSearchSubmit}>
          <input
            className="input"
            placeholder="Search filenames…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select className="input max-w-[160px]" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All kinds</option>
            <option value="video">Video</option>
            <option value="audio">Audio</option>
            <option value="subtitle">Subtitle</option>
          </select>
          <button className="btn-ghost text-sm">Search</button>
        </form>
      )}

      {err && <div className="text-red-400 text-sm">{err}</div>}

      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-30 flex flex-wrap items-center gap-2 px-3 py-2 rounded border border-accent bg-card/95 backdrop-blur">
          <span className="text-sm">
            {selectedIds.size} selected
          </span>
          <button className="btn-ghost text-xs" onClick={selectAllOnPage} disabled={allSelectedOnPage}>
            Select all ({list.length})
          </button>
          <button className="btn-ghost text-xs" onClick={clearSelection}>Clear</button>
          <div className="flex-1" />
          {view === "library" ? (
            <button
              className="btn-ghost text-sm !text-red-300"
              onClick={() => setBulkConfirm({ kind: "archive", ids: Array.from(selectedIds) })}
            >
              Archive selected
            </button>
          ) : (
            <>
              <button
                className="btn-ghost text-sm"
                onClick={async () => {
                  const ids = Array.from(selectedIds);
                  const results = await Promise.allSettled(ids.map((id) => api.restoreMedia(id).then((m) => { upsert(m); removeLocal(id); })));
                  const failed = results.filter((r) => r.status === "rejected").length;
                  setSelectedIds(new Set());
                  fetchArchived();
                  if (failed) setErr(`Failed to restore ${failed} of ${ids.length} item${ids.length === 1 ? "" : "s"}.`);
                }}
              >
                Restore selected
              </button>
              <button
                className="btn-ghost text-sm !text-red-300"
                onClick={() => setBulkConfirm({ kind: "permanent", ids: Array.from(selectedIds) })}
              >
                Delete forever
              </button>
            </>
          )}
        </div>
      )}

      {loading && list.length === 0 && inProgress.length === 0 ? (
        <div className="text-muted">Loading…</div>
      ) : list.length === 0 && inProgress.length === 0 ? (
        <div className="text-muted">
          {view === "library"
            ? "Library is empty. Add media via URL or upload."
            : "No archived items."}
        </div>
      ) : (
        <LibraryView
          mode={viewMode}
          items={list}
          archived={view === "archive"}
          onOpen={openMedia}
          onArchive={(m) => setConfirm({ kind: "archive", media: m })}
          onRestore={doRestore}
          onPermanentDelete={(m) => setConfirm({ kind: "permanent", media: m })}
          isSelected={isSelected}
          onToggleSelect={toggleSelect}
          onToggleGroup={toggleGroup}
          allSelectedOnPage={allSelectedOnPage}
          onSelectAllOnPage={selectAllOnPage}
          onClearSelection={clearSelection}
          prepend={viewMode === "grid-lg" || viewMode === "grid-sm" || viewMode === "list" ? progressCards : undefined}
        />
      )}

      {selected && (
        <MediaPreview
          media={selected}
          subs={subs}
          activeSubId={activeSubId}
          setActiveSubId={setActiveSubId}
          audioTracks={audioTracks}
          activeAudioId={activeAudioId}
          setActiveAudioId={setActiveAudioId}
          onEditSubtitle={(s) => setEditSub(s)}
          action={action}
          setAction={setAction}
          actionSubId={actionSubId}
          archived={view === "archive"}
          onClose={() => { setSelected(null); setAction(null); setActionSubId(null); }}
          onArchive={() => setConfirm({ kind: "archive", media: selected })}
          onRestore={() => doRestore(selected)}
          onPermanentDelete={() => setConfirm({ kind: "permanent", media: selected })}
          onQueued={() => { setAction(null); setActionSubId(null); nav("/jobs"); }}
        />
      )}

      {editSub && (
        <SubtitleEditor
          subtitle={editSub}
          parentVideo={selected && selected.kind === "video" ? selected : null}
          onClose={() => setEditSub(null)}
          onSubtitleUpdated={(m) => { upsert(m); }}
          onSubtitleCreated={(m) => { upsert(m); }}
          onGenerateVoice={(sub) => {
            // Switch over to the voice form on the parent video with this sub preselected.
            const parent = selected && selected.kind === "video" ? selected : null;
            if (!parent) return;
            setEditSub(null);
            setAction("voice");
            setActionSubId(sub.id);
          }}
        />
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.kind === "archive" ? "Move to archive?" : "Permanently delete?"}
          message={
            confirm.kind === "archive"
              ? `"${confirm.media.filename}" will be moved into the archive. You can restore it later.`
              : `"${confirm.media.filename}" will be permanently deleted from disk. This cannot be undone.`
          }
          confirmLabel={confirm.kind === "archive" ? "Archive" : "Delete forever"}
          danger={confirm.kind === "permanent"}
          onCancel={() => setConfirm(null)}
          onConfirm={async () => {
            const target = confirm.media;
            setConfirm(null);
            if (confirm.kind === "archive") await doArchive(target);
            else await doPermanentDelete(target);
          }}
        />
      )}

      {bulkConfirm && (
        <ConfirmDialog
          title={bulkConfirm.kind === "archive" ? `Archive ${bulkConfirm.ids.length} items?` : `Permanently delete ${bulkConfirm.ids.length} items?`}
          message={
            bulkConfirm.kind === "archive"
              ? `${bulkConfirm.ids.length} item${bulkConfirm.ids.length === 1 ? "" : "s"} will be moved to the archive. You can restore them later.`
              : `${bulkConfirm.ids.length} item${bulkConfirm.ids.length === 1 ? "" : "s"} will be permanently deleted from disk. This cannot be undone.`
          }
          confirmLabel={bulkConfirm.kind === "archive" ? "Archive" : "Delete forever"}
          danger={bulkConfirm.kind === "permanent"}
          onCancel={() => setBulkConfirm(null)}
          onConfirm={async () => {
            const { kind, ids } = bulkConfirm;
            setBulkConfirm(null);
            await doBulk(kind, ids);
          }}
        />
      )}
    </div>
  );
}

interface PreviewProps {
  media: MediaFileResponse;
  subs: MediaFileResponse[];
  activeSubId: string | null;
  setActiveSubId: (id: string | null) => void;
  audioTracks: MediaFileResponse[];
  activeAudioId: string | null;
  setActiveAudioId: (id: string | null) => void;
  onEditSubtitle: (s: MediaFileResponse) => void;
  action: ActionKind | null;
  setAction: (a: ActionKind | null) => void;
  actionSubId: string | null;
  archived: boolean;
  onClose: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onPermanentDelete: () => void;
  onQueued: () => void;
}

function MediaPreview({
  media, subs, activeSubId, setActiveSubId,
  audioTracks, activeAudioId, setActiveAudioId,
  onEditSubtitle,
  action, setAction, actionSubId,
  archived, onClose, onArchive, onRestore, onPermanentDelete, onQueued,
}: PreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Subtitle switch: drive via the textTracks API instead of remounting <video>
  // with a different `key` — that's what was killing playback on switch.
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const apply = () => {
      const tracks = v.textTracks;
      for (let i = 0; i < tracks.length; i++) {
        const sub = subs[i];
        tracks[i].mode = sub && sub.id === activeSubId ? "showing" : "hidden";
      }
    };
    apply();
    // textTracks list grows asynchronously as <track> children load; re-apply
    // when that happens so newly added tracks pick up the right mode.
    const onChange = () => apply();
    v.textTracks.addEventListener?.("change", onChange);
    v.textTracks.addEventListener?.("addtrack", onChange);
    return () => {
      v.textTracks.removeEventListener?.("change", onChange);
      v.textTracks.removeEventListener?.("addtrack", onChange);
    };
  }, [activeSubId, subs]);

  // Audio switch: mute the video and slave a hidden <audio> to its timeline.
  // The <audio> element is freshly mounted whenever activeAudioId changes, so
  // we drive the initial sync+play from this effect directly (not from React's
  // onCanPlay synthetic event, which races the mount and can be missed).
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const a = audioRef.current;
    if (activeAudioId === null) {
      v.muted = false;
      if (a) { try { a.pause(); } catch {} }
      return;
    }
    v.muted = true;
    if (!a) return;

    const sync = () => {
      try { a.currentTime = v.currentTime; } catch {}
      a.volume = v.volume;
      a.playbackRate = v.playbackRate;
      if (!v.paused) {
        a.play().catch((err) => console.warn("Alt audio play failed:", err));
      }
    };

    if (a.readyState >= 1 /* HAVE_METADATA */) {
      sync();
    } else {
      a.addEventListener("loadedmetadata", sync, { once: true });
      return () => a.removeEventListener("loadedmetadata", sync);
    }
  }, [activeAudioId]);

  function onVidPlay() {
    const a = audioRef.current;
    const v = videoRef.current;
    if (!a || !v || activeAudioId === null) return;
    if (Math.abs(a.currentTime - v.currentTime) > 0.15) a.currentTime = v.currentTime;
    a.play().catch((err) => console.warn("Alt audio play failed:", err));
  }
  function onVidPause() {
    const a = audioRef.current;
    if (a && activeAudioId !== null) { try { a.pause(); } catch {} }
  }
  function onVidSeeked() {
    const a = audioRef.current;
    const v = videoRef.current;
    if (a && v && activeAudioId !== null) {
      a.currentTime = v.currentTime;
      if (!v.paused) a.play().catch((err) => console.warn("Alt audio play failed:", err));
    }
  }
  function onVidTimeUpdate() {
    const a = audioRef.current;
    const v = videoRef.current;
    if (!a || !v || activeAudioId === null || v.paused) return;
    if (Math.abs(a.currentTime - v.currentTime) > 0.3) {
      a.currentTime = v.currentTime;
    }
  }
  function onVidRateChange() {
    const a = audioRef.current;
    const v = videoRef.current;
    if (a && v) a.playbackRate = v.playbackRate;
  }
  function onVidVolumeChange() {
    const a = audioRef.current;
    const v = videoRef.current;
    if (a && v && activeAudioId !== null) a.volume = v.volume;
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="card max-w-3xl w-full my-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3 gap-3">
          <div className="min-w-0">
            <div className="font-medium truncate">{media.filename}</div>
            <div className="text-xs text-muted">
              {media.container.toUpperCase()} · {prettyBytes(media.size_bytes)}
              {media.duration_sec != null && ` · ${formatDuration(media.duration_sec)}`}
            </div>
          </div>
          <button className="btn-ghost text-xs" onClick={onClose}>Close</button>
        </div>

        {media.kind === "video" ? (
          <>
            <video
              key={media.id}
              ref={videoRef}
              src={api.streamUrl(media.id)}
              controls
              crossOrigin="anonymous"
              className="w-full rounded bg-black"
              onPlay={onVidPlay}
              onPause={onVidPause}
              onSeeked={onVidSeeked}
              onTimeUpdate={onVidTimeUpdate}
              onRateChange={onVidRateChange}
              onVolumeChange={onVidVolumeChange}
            >
              {subs.map((s) => (
                <track
                  key={s.id}
                  kind="subtitles"
                  src={api.vttUrl(s.id)}
                  srcLang={subtitleLang(s.filename) || "und"}
                  label={subtitleLabel(s.filename)}
                />
              ))}
            </video>
            {activeAudioId && (
              <audio
                key={activeAudioId}
                ref={audioRef}
                src={api.streamUrl(activeAudioId)}
                preload="auto"
                className="hidden"
              />
            )}
            {audioTracks.length > 0 && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted">Audio:</span>
                <button
                  className={"btn-ghost text-xs " + (activeAudioId === null ? "border-accent text-white" : "")}
                  onClick={() => setActiveAudioId(null)}
                >
                  Original
                </button>
                {audioTracks.map((a) => (
                  <button
                    key={a.id}
                    className={"btn-ghost text-xs " + (activeAudioId === a.id ? "border-accent text-white" : "")}
                    onClick={() => setActiveAudioId(a.id)}
                    title={a.filename}
                  >
                    {audioLabel(a.filename)}
                  </button>
                ))}
              </div>
            )}
            {subs.length > 0 && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted">Subtitle:</span>
                <button
                  className={"btn-ghost text-xs " + (activeSubId === null ? "border-accent text-white" : "")}
                  onClick={() => setActiveSubId(null)}
                >
                  Off
                </button>
                {subs.map((s) => (
                  <span key={s.id} className="inline-flex items-center gap-1">
                    <button
                      className={"btn-ghost text-xs " + (activeSubId === s.id ? "border-accent text-white" : "")}
                      onClick={() => setActiveSubId(s.id)}
                    >
                      {subtitleLabel(s.filename)}
                    </button>
                    <button
                      className="btn-ghost text-xs !px-1.5"
                      title="Preview / edit / translate"
                      onClick={() => onEditSubtitle(s)}
                    >
                      ✎
                    </button>
                  </span>
                ))}
              </div>
            )}
          </>
        ) : media.kind === "audio" ? (
          <audio src={api.streamUrl(media.id)} controls className="w-full" />
        ) : (
          <div className="text-muted text-sm">Subtitle file — preview not available. Open the file in a text editor.</div>
        )}

        <div className="flex flex-wrap gap-2 mt-4">
          {!archived && media.kind !== "subtitle" && (
            <>
              <button
                className={"btn-ghost text-sm " + (action === "convert" ? "border-accent text-white" : "")}
                onClick={() => setAction(action === "convert" ? null : "convert")}
              >
                Convert
              </button>
              {media.kind === "video" && (
                <button
                  className={"btn-ghost text-sm " + (action === "subtitle" ? "border-accent text-white" : "")}
                  onClick={() => setAction(action === "subtitle" ? null : "subtitle")}
                >
                  Generate subtitle
                </button>
              )}
              {media.kind === "video" && (
                <button
                  className={"btn-ghost text-sm " + (action === "voice" ? "border-accent text-white" : "")}
                  onClick={() => setAction(action === "voice" ? null : "voice")}
                >
                  Translated voice
                </button>
              )}
            </>
          )}
          <div className="flex-1" />
          {archived ? (
            <>
              <button className="btn-ghost text-sm" onClick={onRestore}>Restore</button>
              <button className="btn-ghost text-sm !text-red-300" onClick={onPermanentDelete}>Delete forever</button>
            </>
          ) : (
            <button className="btn-ghost text-sm !text-red-300" onClick={onArchive}>Move to archive</button>
          )}
        </div>

        {action && !archived && (
          <MediaActionsPanel
            media={media}
            subtitles={subs}
            action={action}
            preselectSubtitleId={actionSubId}
            onClose={() => setAction(null)}
            onQueued={onQueued}
          />
        )}
      </div>
    </div>
  );
}

interface InProgressCardProps {
  task: TaskResponse;
  onCancel: () => void;
  onRetry: () => void;
  onDismiss: () => void;
}

function InProgressCard({ task, onCancel, onRetry, onDismiss }: InProgressCardProps) {
  const meta = useMemo(() => {
    if (!task.payload_json) return {} as { url?: string; title?: string; quality?: string; thumbnail?: string };
    try { return JSON.parse(task.payload_json); } catch { return {}; }
  }, [task.payload_json]);

  const label = meta.title || meta.url || task.id;
  const sublabel = meta.quality ? `${meta.quality} · ${meta.url ?? ""}` : meta.url ?? "";

  const statusText =
    task.status === "pending" ? "Pending" :
    task.status === "running" ? (task.message || "Downloading…") :
    task.status === "error" ? "Failed" : task.status;

  return (
    <div className="card relative border border-dashed border-muted/40 opacity-95">
      <div className="aspect-video bg-black/60 rounded mb-2 overflow-hidden relative flex items-center justify-center">
        {meta.thumbnail ? (
          <img src={meta.thumbnail} alt="" className="w-full h-full object-cover opacity-50" />
        ) : null}
        <span className={clsx(
          "absolute text-xs uppercase tracking-wide px-2 py-1 rounded bg-black/60",
          task.status === "error" ? "text-red-300" : "text-white",
        )}>
          {statusText}
        </span>
      </div>
      <div className="text-sm font-medium truncate" title={label}>{label}</div>
      {sublabel && <div className="text-xs text-muted truncate" title={sublabel}>{sublabel}</div>}
      <div className="mt-2">
        <ProgressBar value={task.progress} status={task.status} />
      </div>
      {task.error && <div className="text-xs text-red-400 mt-1 truncate" title={task.error}>{task.error}</div>}
      <div className="mt-2 flex gap-1">
        {(task.status === "pending" || task.status === "running") && (
          <button className="btn-ghost text-xs flex-1" onClick={onCancel}>Cancel</button>
        )}
        {task.status === "error" && (
          <>
            <button className="btn-ghost text-xs flex-1" onClick={onRetry}>Retry</button>
            <button className="btn-ghost text-xs !text-red-300" onClick={onDismiss}>Dismiss</button>
          </>
        )}
      </div>
    </div>
  );
}

function subtitleLang(filename: string): string {
  const m = filename.match(/\.([a-z]{2,3})\.srt$/i);
  return m ? m[1].toLowerCase() : "";
}

function subtitleLabel(filename: string): string {
  const lang = subtitleLang(filename);
  return lang ? lang.toUpperCase() : filename;
}

function audioLabel(filename: string): string {
  // Voice files look like "<base>__voice_<short_name>.mp3".
  const m = filename.match(/__voice_([^.]+)\.[^.]+$/i);
  if (m) {
    const sn = m[1];
    const parts = sn.split("-");
    if (parts.length >= 2) {
      const lang = parts[0].toLowerCase();
      const region = parts[1].toUpperCase();
      const voiceName = parts.slice(2).join("-").replace(/Neural$/i, "");
      return voiceName ? `${lang}-${region} · ${voiceName}` : `${lang}-${region}`;
    }
    return sn;
  }
  return filename.replace(/\.[^.]+$/, "");
}

function prettyBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}
