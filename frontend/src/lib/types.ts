// Manually maintained type definitions. Can be replaced with openapi-typescript output later.

export interface AnalyzeResponse {
  source: string;
  title: string | null;
  thumbnail: string | null;
  duration: number | null;
  available_qualities: string[];
  suggested_quality: string | null;
}

export type TaskStatus =
  | "pending"
  | "running"
  | "done"
  | "error"
  | "cancelled"
  | "paused";

export interface TaskResponse {
  id: string;
  type: string;
  status: TaskStatus;
  progress: number;
  message: string;
  error: string | null;
  media_file_id: string | null;
  payload_json?: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface MediaFileResponse {
  id: string;
  path: string;
  filename: string;
  size_bytes: number;
  duration_sec: number | null;
  container: string;
  width: number | null;
  height: number | null;
  thumbnail_path: string | null;
  kind: "video" | "audio" | "subtitle";
  parent_id: string | null;
  source_url: string | null;
  archived_at: string | null;
  created_at: string;
}

export interface SubtitleCue {
  index: number;
  start_sec: number;
  end_sec: number;
  text: string;
}

export interface SubtitleCuesResponse {
  media_file_id: string;
  cues: SubtitleCue[];
}

export interface VoiceInfo {
  short_name: string;
  locale: string;
  gender: string;
  display_name: string;
}

export interface WhisperModelInfo {
  name: string;
  size_mb: number;
  installed: boolean;
}

export interface ConvertPreset {
  id: string;
  label: string;
  container: string;
  description: string;
}

export interface WSEvent {
  type: "progress" | "done" | "error" | "log";
  task_id: string;
  status?: TaskStatus;
  progress?: number;
  message?: string;
  error?: string;
  media_file_id?: string | null;
  level?: string;
  line?: string;
  ts?: number;
}

export interface TaskLogResponse {
  task_id: string;
  lines: string[];
}
