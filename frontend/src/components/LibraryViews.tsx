import { useMemo } from "react";
import { api } from "@/lib/api";
import type { MediaFileResponse } from "@/lib/types";

export type LibraryViewMode = "grid-lg" | "grid-sm" | "list" | "detail" | "relations";

export const VIEW_LABELS: Record<LibraryViewMode, string> = {
  "grid-lg": "Large thumbnails",
  "grid-sm": "Small thumbnails",
  "list": "List",
  "detail": "Detail",
  "relations": "Relations",
};

interface ItemEvents {
  onOpen: (m: MediaFileResponse) => void;
  onArchive: (m: MediaFileResponse) => void;
  onRestore: (m: MediaFileResponse) => void;
  onPermanentDelete: (m: MediaFileResponse) => void;
  isSelected: (id: string) => boolean;
  onToggleSelect: (id: string) => void;
  /** Toggle a set of ids together. Used by Relations view to select a whole subtree. */
  onToggleGroup?: (ids: string[]) => void;
}

export interface ViewProps extends ItemEvents {
  items: MediaFileResponse[];
  archived: boolean;
  /** Extra cards (e.g. in-progress download placeholders). Only honored on grid/list. */
  prepend?: React.ReactNode;
  /** Bulk selection helpers used by views with a header row (Detail). */
  allSelectedOnPage?: boolean;
  onSelectAllOnPage?: () => void;
  onClearSelection?: () => void;
}

export function LibraryViewPicker({
  mode,
  onChange,
}: {
  mode: LibraryViewMode;
  onChange: (m: LibraryViewMode) => void;
}) {
  const modes: LibraryViewMode[] = ["grid-lg", "grid-sm", "list", "detail", "relations"];
  return (
    <div className="flex gap-1 flex-wrap">
      {modes.map((m) => (
        <button
          key={m}
          className={"btn-ghost text-xs " + (mode === m ? "border-accent text-white" : "")}
          onClick={() => onChange(m)}
          title={VIEW_LABELS[m]}
        >
          {iconFor(m)} {VIEW_LABELS[m]}
        </button>
      ))}
    </div>
  );
}

function iconFor(m: LibraryViewMode): string {
  // Simple unicode glyphs to avoid pulling in an icon library.
  return {
    "grid-lg": "▦",
    "grid-sm": "▩",
    "list": "≡",
    "detail": "≣",
    "relations": "⌘",
  }[m];
}

export function LibraryView({ mode, ...props }: ViewProps & { mode: LibraryViewMode }) {
  if (mode === "grid-lg") return <GridView size="lg" {...props} />;
  if (mode === "grid-sm") return <GridView size="sm" {...props} />;
  if (mode === "list") return <ListView {...props} />;
  if (mode === "detail") return <DetailView {...props} />;
  return <RelationsView {...props} />;
}

function GridView({ items, archived, prepend, size, allSelectedOnPage: _a, onSelectAllOnPage: _b, onClearSelection: _c, ...ev }: ViewProps & { size: "lg" | "sm" }) {
  const gridCls =
    size === "lg"
      ? "grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
      : "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2";

  return (
    <div className={gridCls}>
      {prepend}
      {items.map((m) =>
        size === "lg" ? (
          <MediaCardLarge key={m.id} media={m} archived={archived} {...ev} />
        ) : (
          <MediaCardSmall key={m.id} media={m} archived={archived} {...ev} />
        ),
      )}
    </div>
  );
}

function ListView({ items, archived, prepend, allSelectedOnPage: _a, onSelectAllOnPage: _b, onClearSelection: _c, ...ev }: ViewProps) {
  return (
    <div className="space-y-1">
      {prepend && <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">{prepend}</div>}
      {items.map((m) => (
        <ListRow key={m.id} media={m} archived={archived} {...ev} />
      ))}
    </div>
  );
}

function DetailView({ items, archived, allSelectedOnPage, onSelectAllOnPage, onClearSelection, ...ev }: ViewProps) {
  const headerChecked = !!allSelectedOnPage && items.length > 0;
  return (
    <div className="overflow-x-auto border border-border rounded-md">
      <table className="w-full text-sm">
        <thead className="bg-card text-muted">
          <tr>
            <th className="px-3 py-2 w-8">
              <input
                type="checkbox"
                aria-label={headerChecked ? "Clear selection" : "Select all on this page"}
                checked={headerChecked}
                onChange={() => {
                  if (headerChecked) onClearSelection?.();
                  else onSelectAllOnPage?.();
                }}
              />
            </th>
            <th className="text-left px-3 py-2 font-medium">Name</th>
            <th className="text-left px-3 py-2 font-medium">Kind</th>
            <th className="text-left px-3 py-2 font-medium">Container</th>
            <th className="text-right px-3 py-2 font-medium">Size</th>
            <th className="text-right px-3 py-2 font-medium">Duration</th>
            <th className="text-right px-3 py-2 font-medium">Resolution</th>
            <th className="text-left px-3 py-2 font-medium">Created</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr
              key={m.id}
              className={
                "border-t border-border hover:bg-card/40 " +
                (ev.isSelected(m.id) ? "bg-accent/10" : "")
              }
            >
              <td className="px-3 py-2 w-8">
                <input
                  type="checkbox"
                  aria-label={`Select ${m.filename}`}
                  checked={ev.isSelected(m.id)}
                  onChange={() => ev.onToggleSelect(m.id)}
                />
              </td>
              <td
                className="px-3 py-2 cursor-pointer truncate max-w-[320px]"
                title={m.filename}
                onClick={() => ev.onOpen(m)}
              >
                {m.filename}
              </td>
              <td className="px-3 py-2 text-muted">{m.kind}</td>
              <td className="px-3 py-2 text-muted">{m.container?.toUpperCase()}</td>
              <td className="px-3 py-2 text-right">{prettyBytes(m.size_bytes)}</td>
              <td className="px-3 py-2 text-right">{m.duration_sec != null ? formatDuration(m.duration_sec) : "—"}</td>
              <td className="px-3 py-2 text-right">{m.width && m.height ? `${m.width}×${m.height}` : "—"}</td>
              <td className="px-3 py-2 text-muted">{formatDate(m.created_at)}</td>
              <td className="px-3 py-2 text-right whitespace-nowrap">
                <button className="btn-ghost text-xs" onClick={() => ev.onOpen(m)}>Open</button>{" "}
                {archived ? (
                  <>
                    <button className="btn-ghost text-xs" onClick={() => ev.onRestore(m)}>Restore</button>{" "}
                    <button className="btn-ghost text-xs !text-red-300" onClick={() => ev.onPermanentDelete(m)}>Delete</button>
                  </>
                ) : (
                  <button className="btn-ghost text-xs !text-red-300" onClick={() => ev.onArchive(m)}>Archive</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RelationsView({ items, archived, allSelectedOnPage: _a, onSelectAllOnPage: _b, onClearSelection: _c, prepend: _p, ...ev }: ViewProps) {
  const { roots, childrenOf } = useMemo(() => buildTree(items), [items]);
  if (roots.length === 0) {
    return <div className="text-muted">No items to show.</div>;
  }
  return (
    <div className="space-y-3">
      {roots.map((root) => (
        <RelationNode
          key={root.id}
          node={root}
          childrenOf={childrenOf}
          depth={0}
          archived={archived}
          {...ev}
        />
      ))}
    </div>
  );
}

interface CardProps extends ItemEvents {
  media: MediaFileResponse;
  archived: boolean;
}

function MediaCardLarge({ media, archived, onOpen, onArchive, onRestore, onPermanentDelete, isSelected, onToggleSelect }: CardProps) {
  const selected = isSelected(media.id);
  return (
    <div className={"card group relative hover:border-muted transition " + (selected ? "ring-2 ring-accent" : "")}>
      <label
        className="absolute top-2 left-2 z-10 bg-black/60 rounded p-1 cursor-pointer"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          type="checkbox"
          aria-label={`Select ${media.filename}`}
          checked={selected}
          onChange={() => onToggleSelect(media.id)}
        />
      </label>
      <div
        className="aspect-video bg-black rounded overflow-hidden mb-2 flex items-center justify-center cursor-pointer"
        onClick={() => onOpen(media)}
      >
        {media.thumbnail_path ? (
          <img src={api.thumbnailUrl(media.id)} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-muted text-xs uppercase">{media.kind}</span>
        )}
      </div>
      <div className="text-sm font-medium truncate cursor-pointer" title={media.filename} onClick={() => onOpen(media)}>
        {media.filename}
      </div>
      <div className="text-xs text-muted mt-1 flex justify-between">
        <span>{media.container.toUpperCase()}</span>
        <span>{prettyBytes(media.size_bytes)}</span>
      </div>

      <div className="mt-2 flex flex-wrap gap-1 opacity-80 group-hover:opacity-100 transition">
        {archived ? (
          <>
            <button className="btn-ghost text-xs flex-1" onClick={() => onRestore(media)}>Restore</button>
            <button className="btn-ghost text-xs !text-red-300" onClick={() => onPermanentDelete(media)}>Delete</button>
          </>
        ) : (
          <>
            <button className="btn-ghost text-xs flex-1" onClick={() => onOpen(media)}>Open</button>
            <button className="btn-ghost text-xs !text-red-300" onClick={() => onArchive(media)} title="Move to archive">
              Archive
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function MediaCardSmall({ media, archived, onOpen, onArchive, onRestore, onPermanentDelete, isSelected, onToggleSelect }: CardProps) {
  const selected = isSelected(media.id);
  return (
    <div className={"bg-card border rounded p-1.5 group relative " + (selected ? "border-accent ring-1 ring-accent" : "border-border")}>
      <label
        className="absolute top-1 left-1 z-10 bg-black/60 rounded px-1 cursor-pointer"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          type="checkbox"
          aria-label={`Select ${media.filename}`}
          checked={selected}
          onChange={() => onToggleSelect(media.id)}
        />
      </label>
      <div
        className="aspect-video bg-black rounded overflow-hidden mb-1 flex items-center justify-center cursor-pointer"
        onClick={() => onOpen(media)}
      >
        {media.thumbnail_path ? (
          <img src={api.thumbnailUrl(media.id)} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-muted text-[10px] uppercase">{media.kind}</span>
        )}
      </div>
      <div className="text-[11px] truncate cursor-pointer" title={media.filename} onClick={() => onOpen(media)}>
        {media.filename}
      </div>
      <div className="hidden group-hover:flex gap-1 mt-1">
        {archived ? (
          <>
            <button className="btn-ghost text-[10px] flex-1 !px-1 !py-0.5" onClick={() => onRestore(media)}>↩</button>
            <button className="btn-ghost text-[10px] !text-red-300 !px-1 !py-0.5" onClick={() => onPermanentDelete(media)}>×</button>
          </>
        ) : (
          <button className="btn-ghost text-[10px] !text-red-300 !px-1 !py-0.5 flex-1" onClick={() => onArchive(media)}>Archive</button>
        )}
      </div>
    </div>
  );
}

function ListRow({ media, archived, onOpen, onArchive, onRestore, onPermanentDelete, isSelected, onToggleSelect }: CardProps) {
  const selected = isSelected(media.id);
  return (
    <div
      className={
        "flex items-center gap-3 px-2 py-1.5 rounded border transition " +
        (selected ? "border-accent bg-accent/10" : "border-border bg-card/40 hover:bg-card/80")
      }
    >
      <input
        type="checkbox"
        aria-label={`Select ${media.filename}`}
        checked={selected}
        onChange={() => onToggleSelect(media.id)}
      />
      <div
        className="w-20 h-12 bg-black rounded overflow-hidden shrink-0 cursor-pointer flex items-center justify-center"
        onClick={() => onOpen(media)}
      >
        {media.thumbnail_path ? (
          <img src={api.thumbnailUrl(media.id)} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-muted text-[10px] uppercase">{media.kind}</span>
        )}
      </div>
      <div className="flex-1 min-w-0 cursor-pointer" onClick={() => onOpen(media)}>
        <div className="text-sm truncate" title={media.filename}>{media.filename}</div>
        <div className="text-xs text-muted">
          {media.kind} · {media.container.toUpperCase()} · {prettyBytes(media.size_bytes)}
          {media.duration_sec != null && ` · ${formatDuration(media.duration_sec)}`}
        </div>
      </div>
      <div className="flex gap-1 shrink-0">
        <button className="btn-ghost text-xs" onClick={() => onOpen(media)}>Open</button>
        {archived ? (
          <>
            <button className="btn-ghost text-xs" onClick={() => onRestore(media)}>Restore</button>
            <button className="btn-ghost text-xs !text-red-300" onClick={() => onPermanentDelete(media)}>Delete</button>
          </>
        ) : (
          <button className="btn-ghost text-xs !text-red-300" onClick={() => onArchive(media)}>Archive</button>
        )}
      </div>
    </div>
  );
}

interface TreeNode {
  media: MediaFileResponse;
  id: string;
}

function buildTree(items: MediaFileResponse[]): {
  roots: TreeNode[];
  childrenOf: Map<string, TreeNode[]>;
} {
  const byId = new Map(items.map((m) => [m.id, m]));
  const childrenOf = new Map<string, TreeNode[]>();
  const roots: TreeNode[] = [];
  for (const m of items) {
    const node = { media: m, id: m.id };
    if (m.parent_id && byId.has(m.parent_id)) {
      const arr = childrenOf.get(m.parent_id) || [];
      arr.push(node);
      childrenOf.set(m.parent_id, arr);
    } else {
      roots.push(node);
    }
  }
  // Sort: videos first within roots; children by kind then date.
  roots.sort((a, b) => kindRank(a.media.kind) - kindRank(b.media.kind));
  for (const arr of childrenOf.values()) {
    arr.sort((a, b) => kindRank(a.media.kind) - kindRank(b.media.kind));
  }
  return { roots, childrenOf };
}

function kindRank(k: string): number {
  return { video: 0, audio: 1, subtitle: 2 }[k as "video" | "audio" | "subtitle"] ?? 3;
}

function gatherSubtreeIds(rootId: string, childrenOf: Map<string, TreeNode[]>): string[] {
  const ids: string[] = [rootId];
  const stack: string[] = [rootId];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const k of childrenOf.get(cur) || []) {
      ids.push(k.id);
      stack.push(k.id);
    }
  }
  return ids;
}

function RelationNode({
  node,
  childrenOf,
  depth,
  archived,
  onOpen,
  onArchive,
  onRestore,
  onPermanentDelete,
  isSelected,
  onToggleSelect,
  onToggleGroup,
}: {
  node: TreeNode;
  childrenOf: Map<string, TreeNode[]>;
  depth: number;
  archived: boolean;
} & ItemEvents) {
  const kids = childrenOf.get(node.id) || [];
  const m = node.media;
  const selected = isSelected(m.id);

  const groupIds = useMemo(
    () => (kids.length > 0 ? gatherSubtreeIds(node.id, childrenOf) : null),
    [node.id, childrenOf, kids.length],
  );
  const groupAllSelected =
    groupIds != null && groupIds.length > 0 && groupIds.every((id) => isSelected(id));

  return (
    <div className="relative">
      <div
        className={
          "flex items-center gap-2 py-1.5 px-2 rounded border " +
          (selected
            ? "border-accent bg-accent/10"
            : depth === 0
              ? "border-border bg-card"
              : "border-border/60 bg-card/40")
        }
        style={{ marginLeft: depth * 20 }}
      >
        {depth > 0 && (
          <span className="text-muted text-xs select-none" aria-hidden>
            └─
          </span>
        )}
        <input
          type="checkbox"
          aria-label={`Select ${m.filename}`}
          checked={selected}
          onChange={() => onToggleSelect(m.id)}
        />
        <div
          className="w-16 h-10 bg-black rounded overflow-hidden shrink-0 cursor-pointer flex items-center justify-center"
          onClick={() => onOpen(m)}
        >
          {m.thumbnail_path ? (
            <img src={api.thumbnailUrl(m.id)} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-muted text-[10px] uppercase">{m.kind}</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm truncate cursor-pointer" title={m.filename} onClick={() => onOpen(m)}>
            {m.filename}
          </div>
          <div className="text-xs text-muted">
            {kindBadge(m.kind)} · {prettyBytes(m.size_bytes)}
            {m.duration_sec != null && ` · ${formatDuration(m.duration_sec)}`}
            {kids.length > 0 && ` · ${kids.length} derivative${kids.length === 1 ? "" : "s"}`}
          </div>
        </div>
        <div className="flex gap-1 shrink-0 items-center">
          {groupIds && onToggleGroup && (
            <label
              className={
                "flex items-center gap-1 text-xs px-2 py-0.5 rounded border cursor-pointer " +
                (groupAllSelected ? "border-accent text-white" : "border-border text-muted")
              }
              title="Select / deselect this item and all derivatives"
            >
              <input
                type="checkbox"
                aria-label={`Select group rooted at ${m.filename}`}
                checked={groupAllSelected}
                onChange={() => onToggleGroup(groupIds)}
              />
              Group
            </label>
          )}
          <button className="btn-ghost text-xs" onClick={() => onOpen(m)}>Open</button>
          {archived ? (
            <>
              <button className="btn-ghost text-xs" onClick={() => onRestore(m)}>↩</button>
              <button className="btn-ghost text-xs !text-red-300" onClick={() => onPermanentDelete(m)}>×</button>
            </>
          ) : (
            <button className="btn-ghost text-xs !text-red-300" onClick={() => onArchive(m)}>Archive</button>
          )}
        </div>
      </div>
      {kids.length > 0 && (
        <div className="mt-1 space-y-1">
          {kids.map((k) => (
            <RelationNode
              key={k.id}
              node={k}
              childrenOf={childrenOf}
              depth={depth + 1}
              archived={archived}
              onOpen={onOpen}
              onArchive={onArchive}
              onRestore={onRestore}
              onPermanentDelete={onPermanentDelete}
              isSelected={isSelected}
              onToggleSelect={onToggleSelect}
              onToggleGroup={onToggleGroup}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function kindBadge(k: string): string {
  return k === "video" ? "🎬 video" : k === "audio" ? "🎵 audio" : "💬 subtitle";
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

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
