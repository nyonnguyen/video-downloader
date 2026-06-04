import type {
  AnalyzeResponse,
  ConvertPreset,
  MediaFileResponse,
  SubtitleCue,
  SubtitleCuesResponse,
  TaskLogResponse,
  TaskResponse,
  VoiceInfo,
  WhisperModelInfo,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  analyze: (url: string) =>
    request<AnalyzeResponse>("/api/analyze", { method: "POST", body: JSON.stringify({ url }) }),

  createDownload: (payload: {
    url: string;
    quality?: string;
    audio_only?: boolean;
    title?: string;
    thumbnail?: string;
  }) =>
    request<{ task_id: string }>("/api/downloads", { method: "POST", body: JSON.stringify(payload) }),

  listTasks: (status?: string) =>
    request<TaskResponse[]>(`/api/tasks${status ? `?status=${status}` : ""}`),

  cancelTask: (id: string) => request(`/api/tasks/${id}/cancel`, { method: "POST" }),
  pauseTask: (id: string) => request(`/api/tasks/${id}/pause`, { method: "POST" }),
  resumeTask: (id: string) => request(`/api/tasks/${id}/resume`, { method: "POST" }),
  retryTask: (id: string) => request(`/api/tasks/${id}/retry`, { method: "POST" }),
  deleteTask: (id: string) => request(`/api/tasks/${id}`, { method: "DELETE" }),
  getTaskLog: (id: string) => request<TaskLogResponse>(`/api/tasks/${id}/log`),

  listLibrary: (params?: { kind?: string; q?: string; archived?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.kind) q.set("kind", params.kind);
    if (params?.q) q.set("q", params.q);
    if (params?.archived) q.set("archived", "true");
    return request<MediaFileResponse[]>(`/api/library?${q.toString()}`);
  },

  archiveMedia: (id: string) => request(`/api/library/${id}`, { method: "DELETE" }),
  restoreMedia: (id: string) =>
    request<MediaFileResponse>(`/api/library/${id}/restore`, { method: "POST" }),
  permanentDelete: (id: string) =>
    request(`/api/library/${id}/permanent`, { method: "DELETE" }),

  uploadMedia: async (file: File): Promise<MediaFileResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/library/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  },

  streamUrl: (id: string) => `/api/library/${id}/stream`,
  thumbnailUrl: (id: string) => `/api/library/${id}/thumbnail`,
  vttUrl: (id: string) => `/api/library/${id}/vtt`,

  listSubtitlesFor: (videoId: string) =>
    request<MediaFileResponse[]>(`/api/library/${videoId}/subtitles`),

  listAudioTracksFor: (videoId: string) =>
    request<MediaFileResponse[]>(`/api/library/${videoId}/audio_tracks`),

  getSubtitleCues: (subId: string) =>
    request<SubtitleCuesResponse>(`/api/library/${subId}/cues`),
  updateSubtitleCues: (subId: string, cues: SubtitleCue[]) =>
    request<MediaFileResponse>(`/api/library/${subId}/cues`, {
      method: "PUT",
      body: JSON.stringify({ cues }),
    }),
  translateSubtitle: (subId: string, payload: { target_language: string; source_language?: string; save_as_new?: boolean }) =>
    request<MediaFileResponse>(`/api/library/${subId}/translate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listPresets: () => request<ConvertPreset[]>("/api/convert/presets"),
  createConvert: (payload: { media_file_id: string; preset_id: string }) =>
    request<{ task_id: string }>("/api/convert", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listWhisperModels: () => request<WhisperModelInfo[]>("/api/subtitle/models"),
  createSubtitle: (payload: {
    media_file_id: string;
    model: string;
    language?: string;
    translate_to_en?: boolean;
    output_target?: "srt_only" | "soft_embed" | "burn_in";
    embed_soft?: boolean;
    burn_in?: boolean;
  }) =>
    request<{ task_id: string }>("/api/subtitle", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listVoices: () => request<VoiceInfo[]>("/api/voice/voices"),
  createVoice: (payload: {
    media_file_id: string;
    subtitle_file_id?: string;
    whisper_model?: string;
    source_language?: string;
    voice: string;
    rate?: string;
    mux_into_video?: boolean;
    make_default_track?: boolean;
  }) =>
    request<{ task_id: string }>("/api/voice", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
