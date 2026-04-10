const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Capture
export function captureNote(content: string, title?: string, tags?: string[]) {
  return request<{ note_id: string; status: string; message: string }>(
    "/capture/note",
    { method: "POST", body: JSON.stringify({ content, title, tags }) },
  );
}

export function captureUrl(url: string, context?: string, tags?: string[]) {
  return request<{ note_id: string; status: string; message: string }>(
    "/capture/url",
    { method: "POST", body: JSON.stringify({ url, context, tags }) },
  );
}

// Search
export function searchNotes(
  q: string,
  filters?: { source_type?: string; concepts?: string; after?: string; before?: string },
) {
  const params = new URLSearchParams({ q });
  if (filters?.source_type) params.set("source_type", filters.source_type);
  if (filters?.concepts) params.set("concepts", filters.concepts);
  if (filters?.after) params.set("after", filters.after);
  if (filters?.before) params.set("before", filters.before);
  return request<{ results: SearchResult[]; total: number }>(
    `/search?${params}`,
  );
}

// Notes
export function getNotes(params?: {
  sort?: string;
  limit?: number;
  offset?: number;
  is_starred?: boolean;
  processing_status?: string;
}) {
  const sp = new URLSearchParams();
  if (params?.sort) sp.set("sort", params.sort);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.is_starred !== undefined)
    sp.set("is_starred", String(params.is_starred));
  if (params?.processing_status)
    sp.set("processing_status", params.processing_status);
  return request<{ notes: Note[]; total: number }>(`/notes?${sp}`);
}

export function getNote(id: string) {
  return request<NoteDetail>(`/notes/${id}`);
}

export function updateNote(id: string, data: Record<string, unknown>) {
  return request<{ ok: boolean }>(`/notes/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteNote(id: string) {
  return request<{ ok: boolean }>(`/notes/${id}`, { method: "DELETE" });
}

// Concepts & Entities
export function getConcepts() {
  return request<{ concepts: Concept[] }>("/concepts");
}

export function getEntities(type?: string) {
  const params = type ? `?entity_type=${type}` : "";
  return request<{ entities: Entity[] }>(`/entities${params}`);
}

export function getEntity(id: string) {
  return request<EntityDetail>(`/entities/${id}`);
}

export function getConcept(id: string) {
  return request<ConceptDetail>(`/concepts/${id}`);
}

// Graph
export function getGraph(filters?: {
  concept?: string;
  entity?: string;
  connection_type?: string;
  min_strength?: number;
}) {
  const sp = new URLSearchParams();
  if (filters?.concept) sp.set("concept", filters.concept);
  if (filters?.entity) sp.set("entity", filters.entity);
  if (filters?.connection_type) sp.set("connection_type", filters.connection_type);
  if (filters?.min_strength) sp.set("min_strength", String(filters.min_strength));
  return request<GraphData>(`/graph?${sp}`);
}

// Ask
export function askQuestion(q: string) {
  return request<AskResponse>(`/search?q=${encodeURIComponent(q)}&mode=ask`);
}

// Export
export function getExportJsonUrl() {
  return `${BASE}/export/json`;
}

export function getExportMarkdownUrl() {
  return `${BASE}/export/markdown`;
}

// Stats
export function getStats() {
  return request<Stats>("/stats");
}

// Settings
export function getSettings() {
  return request<Record<string, unknown>>("/settings");
}

export function updateSettings(key: string, value: unknown) {
  return request<{ ok: boolean }>("/settings", {
    method: "PUT",
    body: JSON.stringify({ key, value }),
  });
}

// Harness
export function getHarnessHealth() {
  return request<{ status: Record<string, boolean> }>("/harness/health");
}

export function getHarnessConfig() {
  return request<Record<string, { provider: string; model: string }>>(
    "/harness/config",
  );
}

export function applyPreset(name: string) {
  return request<{ ok: boolean }>(`/harness/presets/${name}/apply`, {
    method: "POST",
  });
}

// Agent
export function getBrief(date?: string) {
  const params = date ? `?date=${date}` : "";
  return request<{ brief: DailyBrief | null }>(`/agent/brief${params}`);
}

export function generateBrief() {
  return request<{ ok: boolean; brief?: DailyBrief }>("/agent/brief/generate", {
    method: "POST",
  });
}

export function getResurfaceItems(limit = 10) {
  return request<{ items: ResurfaceItem[] }>(
    `/agent/resurface?limit=${limit}`,
  );
}

export function clickResurface(id: string) {
  return request<{ ok: boolean }>(`/agent/resurface/${id}/click`, {
    method: "POST",
  });
}

export function dismissResurface(id: string) {
  return request<{ ok: boolean }>(`/agent/resurface/${id}/dismiss`, {
    method: "POST",
  });
}

export function getAgentActivity(limit = 20) {
  return request<{ log: AgentLogEntry[]; total: number }>(
    `/agent/activity?limit=${limit}`,
  );
}

export function getInterests() {
  return request<{ interests: { topic: string; score: number }[] }>(
    "/agent/interests",
  );
}

export function triggerDeepScan() {
  return request<{ ok: boolean; result: Record<string, number> }>(
    "/agent/deep-scan",
    { method: "POST" },
  );
}

export function triggerTaxonomyRebuild() {
  return request<{ ok: boolean; result: Record<string, number> }>(
    "/agent/taxonomy-rebuild",
    { method: "POST" },
  );
}

// Bridge
export function getBridgeStatus() {
  return request<BridgeStatus>("/bridge/status");
}

export function getBridgeConfig() {
  return request<BridgeConfig>("/bridge/config");
}

export function updateBridgeConfig(config: BridgeConfig) {
  return request<{ status: string }>("/bridge/config", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export function testBridge(platform: string) {
  return request<{ success: boolean; error?: string }>(
    `/bridge/test/${platform}`,
    { method: "POST" },
  );
}

export function getBridgeLog(limit = 50, offset = 0) {
  return request<BridgeLogEntry[]>(
    `/bridge/log?limit=${limit}&offset=${offset}`,
  );
}

// Types

export interface BridgeStatus {
  configured: boolean;
  platforms: Record<string, { connected: boolean; info?: Record<string, unknown>; error?: string }>;
}

export interface BridgeConfig {
  enabled_platforms?: string[];
  telegram?: { bot_token?: string; webhook_base_url?: string; user_id?: string };
  mattermost?: { url?: string; bot_token?: string; channel_id?: string; user_id?: string };
  outbound_channels?: { daily_brief?: string[]; connection_alert?: string[]; resurface?: string[] };
  security?: { allowed_sender_ids?: { telegram?: string[]; mattermost?: string[] } };
}

export interface BridgeLogEntry {
  id: string;
  platform: string;
  direction: string;
  sender_id: string | null;
  intent: string | null;
  text: string | null;
  status: string;
  response_text: string | null;
  created_at: string;
}

export interface DailyBrief {
  id: string;
  brief_date: string;
  content: string;
  sections: {
    recent: { title: string; created_at: string }[];
    connections: { source: string; target: string; type: string; explanation: string }[];
    resurface: { title: string; reason: string }[];
    dangling: { title: string; created_at: string }[];
    historical: { title: string }[];
  };
  generated_at: string;
}

export interface ResurfaceItem {
  id: string;
  queue_type: string;
  note_id: string;
  reason: string;
  priority: number;
  note_title: string | null;
  created_at: string;
}

export interface AgentLogEntry {
  id: string;
  action_type: string;
  details: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
  status: string;
  error_message: string | null;
}

export interface Note {
  id: string;
  title: string | null;
  synthesis: string | null;
  source_type: string;
  content_type: string;
  raw_content: string;
  processed_content: string | null;
  created_at: string;
  is_starred: number;
  is_archived: number;
  word_count: number | null;
  processing_status: string;
  concepts: string[];
  tags: string[];
}

export interface NoteDetail extends Note {
  source_uri: string | null;
  updated_at: string;
  processed_at: string | null;
  reading_time_seconds: number | null;
  entities: { id: string; name: string; entity_type: string; context: string | null }[];
  connections: {
    id: string;
    target_note_id: string;
    connection_type: string;
    strength: number;
    explanation: string | null;
    target_title: string | null;
  }[];
}

export interface SearchResult {
  note_id: string;
  title: string | null;
  synthesis: string | null;
  score: number;
  highlights: string | null;
  concepts: string[];
  source_type: string;
  created_at: string;
}

export interface Concept {
  id: string;
  name: string;
  description: string | null;
  note_count: number;
}

export interface Entity {
  id: string;
  name: string;
  entity_type: string;
}

export interface Stats {
  notes: number;
  concepts: number;
  connections: number;
  entities: number;
  pending: number;
  processing: number;
  errored: number;
}

export interface EntityDetail extends Entity {
  description: string | null;
  metadata: Record<string, unknown> | null;
  notes: { id: string; title: string; synthesis: string; source_type: string; created_at: string; context: string | null }[];
  co_entities: { id: string; name: string; entity_type: string; co_count: number }[];
  concepts: { id: string; name: string; note_count: number }[];
  note_count: number;
}

export interface ConceptDetail extends Concept {
  notes: { id: string; title: string; synthesis: string; source_type: string; created_at: string; relevance_score: number }[];
  children: { id: string; name: string; note_count: number }[];
  parents: { id: string; name: string }[];
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  title: string;
  source_type: string;
  created_at: string;
  is_starred: number;
  concepts: string[];
  connection_count: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  strength: number;
  explanation: string | null;
}

export interface AskResponse {
  answer: string;
  sources: { note_id: string; title: string; score: number }[];
  confidence: number;
}
