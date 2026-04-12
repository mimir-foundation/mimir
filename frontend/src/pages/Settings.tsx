import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getStats,
  getHarnessConfig,
  getHarnessHealth,
  applyPreset,
  getAgentActivity,
  generateBrief,
  triggerDeepScan,
  triggerTaxonomyRebuild,
  getInterests,
  getBridgeStatus,
  getBridgeConfig,
  updateBridgeConfig,
  patchBridgeConfig,
  testBridge,
  getBridgeLog,
  getApiKeys,
  updateApiKeys,
  importNotion,
  importObsidian,
  importBookmarks,
} from "../lib/api";
import type { BridgeConfig, BridgeLogEntry, BridgeStatus } from "../lib/api";
import {
  Activity,
  CheckCircle,
  XCircle,
  Cpu,
  Loader2,
  Brain,
  Newspaper,
  Search,
  GitBranch,
  Clock,
  MessageSquare,
  Send,
  Eye,
  EyeOff,
  BellRing,
  Upload,
  Download,
  Code,
} from "lucide-react";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

type SettingsTab = "general" | "ai" | "bridge" | "data";

export default function Settings() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<SettingsTab>("general");
  const [applying, setApplying] = useState("");
  const [running, setRunning] = useState("");

  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });
  const { data: config } = useQuery({ queryKey: ["harness-config"], queryFn: getHarnessConfig });
  const { data: health } = useQuery({ queryKey: ["harness-health"], queryFn: getHarnessHealth });
  const { data: activityData } = useQuery({
    queryKey: ["agent-activity"], queryFn: () => getAgentActivity(15), refetchInterval: 15_000,
  });
  const { data: interests } = useQuery({ queryKey: ["interests"], queryFn: getInterests });
  const { data: bridgeStatus } = useQuery({
    queryKey: ["bridge-status"],
    queryFn: async () => { try { return await getBridgeStatus(); } catch { return { configured: false, platforms: {} } as BridgeStatus; } },
    refetchInterval: 15_000,
  });
  const { data: bridgeConfig } = useQuery({
    queryKey: ["bridge-config"],
    queryFn: async () => { try { return await getBridgeConfig(); } catch { return {} as BridgeConfig; } },
  });
  const { data: bridgeLog } = useQuery({
    queryKey: ["bridge-log"],
    queryFn: async () => { try { return await getBridgeLog(20); } catch { return [] as BridgeLogEntry[]; } },
    refetchInterval: 15_000,
  });
  const { data: apiKeys } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => { try { return await getApiKeys(); } catch { return { anthropic: "", openai: "", google: "" }; } },
  });

  // AI keys state
  const [editingKeys, setEditingKeys] = useState(false);
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [keySaveResult, setKeySaveResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({});

  // Bridge state
  const [bridgeEditing, setBridgeEditing] = useState(false);
  const [bridgeDraft, setBridgeDraft] = useState<BridgeConfig>({});
  const [bridgeTesting, setBridgeTesting] = useState("");
  const [bridgeTestResult, setBridgeTestResult] = useState<Record<string, { ok: boolean; msg: string }>>({});
  const [showTokens, setShowTokens] = useState<Record<string, boolean>>({});
  const [showBridgeLog, setShowBridgeLog] = useState(false);
  const [bridgeSaveResult, setBridgeSaveResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // Import state
  const [importLoading, setImportLoading] = useState("");
  const [importResult, setImportResult] = useState<{ format: string; msg: string; ok: boolean } | null>(null);

  // Handlers
  async function handleApplyPreset(preset: string) {
    setApplying(preset);
    try {
      await applyPreset(preset);
      queryClient.invalidateQueries({ queryKey: ["harness-config"] });
      queryClient.invalidateQueries({ queryKey: ["harness-health"] });
    } finally { setApplying(""); }
  }

  async function handleAction(action: string, fn: () => Promise<unknown>) {
    setRunning(action);
    try { await fn(); queryClient.invalidateQueries({ queryKey: ["agent-activity"] }); }
    finally { setRunning(""); }
  }

  function startEditKeys() {
    setKeyDraft({ anthropic: "", openai: "", google: "" });
    setEditingKeys(true);
    setKeySaveResult(null);
  }

  async function saveApiKeys() {
    setKeySaveResult(null);
    try {
      const toSend: Record<string, string> = {};
      for (const [k, v] of Object.entries(keyDraft)) { if (v.trim()) toSend[k] = v.trim(); }
      const res = await updateApiKeys(toSend);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      queryClient.invalidateQueries({ queryKey: ["harness-config"] });
      queryClient.invalidateQueries({ queryKey: ["harness-health"] });
      setEditingKeys(false);
      setKeySaveResult({ ok: true, msg: res.reloaded ? "Keys saved and AI engine reloaded." : "Keys saved." });
    } catch (e: unknown) {
      setKeySaveResult({ ok: false, msg: e instanceof Error ? e.message : "Save failed" });
    }
  }

  function startEditBridge() {
    setBridgeDraft(bridgeConfig || {});
    setBridgeEditing(true);
  }

  async function saveBridgeConfig() {
    setBridgeSaveResult(null);
    try {
      const res = await updateBridgeConfig(bridgeDraft);
      queryClient.invalidateQueries({ queryKey: ["bridge-config"] });
      queryClient.invalidateQueries({ queryKey: ["bridge-status"] });
      setBridgeEditing(false);
      if (res.status === "reloaded") {
        const platforms = (res as Record<string, unknown>).platforms as string[] | undefined;
        setBridgeSaveResult({ ok: true, msg: platforms?.length ? `Connected: ${platforms.join(", ")}` : "Saved. No platforms configured yet." });
      } else {
        setBridgeSaveResult({ ok: false, msg: (res as Record<string, unknown>).error as string || "Saved but reload failed." });
      }
    } catch (e: unknown) {
      setBridgeSaveResult({ ok: false, msg: e instanceof Error ? e.message : "Save failed" });
    }
  }

  async function handleTestBridge(platform: string) {
    setBridgeTesting(platform);
    setBridgeTestResult((prev) => ({ ...prev, [platform]: { ok: false, msg: "..." } }));
    try {
      const res = await testBridge(platform);
      setBridgeTestResult((prev) => ({ ...prev, [platform]: { ok: res.success, msg: res.success ? "Connected!" : res.error || "Failed" } }));
    } catch (e: unknown) {
      setBridgeTestResult((prev) => ({ ...prev, [platform]: { ok: false, msg: e instanceof Error ? e.message : "Failed" } }));
    } finally { setBridgeTesting(""); }
  }

  async function handleImport(format: string, file: File) {
    setImportLoading(format);
    setImportResult(null);
    try {
      const fn = format === "notion" ? importNotion : format === "obsidian" ? importObsidian : importBookmarks;
      const res = await fn(file);
      if (res.error) { setImportResult({ format, msg: res.error, ok: false }); }
      else { setImportResult({ format, msg: `Imported ${res.imported} items${res.errors ? `, ${res.errors} errors` : ""}`, ok: true }); queryClient.invalidateQueries({ queryKey: ["stats"] }); }
    } catch (e: unknown) {
      setImportResult({ format, msg: e instanceof Error ? e.message : "Import failed", ok: false });
    } finally { setImportLoading(""); }
  }

  async function toggleNotification(notifType: string, channel: string, isEnabled: boolean) {
    const channels = { ...(bridgeConfig?.outbound_channels ?? {}) };
    let list = [...(channels[notifType] ?? [])];
    if (isEnabled) {
      list = list.filter((e) => !(typeof e === "object" && e.platform === channel));
    } else {
      const recipientId = channel === "telegram" ? bridgeConfig?.telegram?.user_id ?? "" : "";
      list.push({ platform: channel, recipient_id: recipientId });
    }
    channels[notifType] = list;
    try {
      await patchBridgeConfig({ outbound_channels: channels });
      queryClient.invalidateQueries({ queryKey: ["bridge-config"] });
    } catch { /* silent */ }
  }

  const presets = [
    { name: "local", desc: "All local via Ollama (free, private)" },
    { name: "hybrid", desc: "Local embeddings + cloud reasoning" },
    { name: "cloud", desc: "All cloud APIs (best quality)" },
    { name: "budget", desc: "Local + cheap cloud model" },
  ];

  const statusColors: Record<string, string> = {
    complete: "text-emerald-400", running: "text-blue-400", error: "text-red-400",
  };

  const tabs: { key: SettingsTab; icon: typeof Activity; label: string }[] = [
    { key: "general", icon: Activity, label: "General" },
    { key: "ai", icon: Cpu, label: "AI Engine" },
    { key: "bridge", icon: MessageSquare, label: "Messaging" },
    { key: "data", icon: Download, label: "Data" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Settings</h1>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface-2 rounded-xl p-1 border border-border-subtle w-fit">
        {tabs.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
              tab === key ? "bg-brand-500 text-white shadow-sm" : "text-zinc-400 hover:text-white"
            }`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {/* ===== GENERAL TAB ===== */}
      {tab === "general" && (
        <div className="space-y-6">
          {/* System Status */}
          {stats && (
            <Card title="System Status" icon={Activity}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                {[
                  { label: "Notes", value: stats.notes },
                  { label: "Concepts", value: stats.concepts },
                  { label: "Connections", value: stats.connections },
                  { label: "Entities", value: stats.entities },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <span className="text-zinc-500 text-xs">{label}</span>
                    <p className="text-xl font-bold text-white tabular-nums">{value.toLocaleString()}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Agent Controls */}
          <Card title="Agent Controls" icon={Brain}>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { key: "brief", fn: generateBrief, icon: Newspaper, label: "Generate Brief", desc: "Daily digest now" },
                { key: "scan", fn: triggerDeepScan, icon: Search, label: "Deep Scan", desc: "Find connections" },
                { key: "taxonomy", fn: triggerTaxonomyRebuild, icon: GitBranch, label: "Rebuild Taxonomy", desc: "Merge & organize" },
              ].map(({ key, fn, icon: Icon, label, desc }) => (
                <button
                  key={key}
                  onClick={() => handleAction(key, fn)}
                  disabled={!!running}
                  className="flex items-center gap-3 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors disabled:opacity-50 text-left"
                >
                  {running === key ? <Loader2 className="w-4 h-4 animate-spin text-brand-400" /> : <Icon className="w-4 h-4 text-zinc-500" />}
                  <div>
                    <span className="text-sm text-white">{label}</span>
                    <p className="text-xs text-zinc-500">{desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* Interest Signals */}
          {interests?.interests && interests.interests.length > 0 && (
            <Card title="Current Interests (decayed)">
              <div className="flex flex-wrap gap-2">
                {interests.interests.slice(0, 15).map((i) => (
                  <span key={i.topic} className="px-2 py-1 bg-surface-3 text-zinc-300 rounded-lg text-xs" style={{ opacity: Math.min(1, 0.3 + i.score * 0.7) }}>
                    {i.topic} <span className="text-zinc-600">{i.score.toFixed(1)}</span>
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* Activity Log */}
          {activityData?.log && activityData.log.length > 0 && (
            <Card title="Agent Activity" icon={Clock}>
              <div className="space-y-1.5 max-h-72 overflow-y-auto">
                {activityData.log.map((entry) => (
                  <div key={entry.id} className="flex items-center justify-between bg-surface-3 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center gap-3">
                      <span className={statusColors[entry.status] || "text-zinc-400"}>
                        {entry.status === "running" ? "●" : entry.status === "complete" ? "✓" : "✗"}
                      </span>
                      <span className="text-zinc-300">{entry.action_type.replace("_", " ")}</span>
                      {entry.error_message && <span className="text-red-400 truncate max-w-48">{entry.error_message}</span>}
                    </div>
                    <span className="text-zinc-600 shrink-0">{formatDistanceToNow(new Date(entry.started_at), { addSuffix: true })}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ===== AI ENGINE TAB ===== */}
      {tab === "ai" && (
        <div className="space-y-6">
          {/* Presets */}
          <Card title="Presets" icon={Cpu}>
            <div className="grid grid-cols-2 gap-2">
              {presets.map((p) => (
                <button key={p.name} onClick={() => handleApplyPreset(p.name)} disabled={!!applying}
                  className="flex items-center gap-3 p-3 bg-surface-3 border border-border-subtle rounded-xl text-left hover:border-brand-500/30 transition-colors disabled:opacity-50">
                  {applying === p.name ? <Loader2 className="w-4 h-4 text-brand-400 animate-spin" /> : <Cpu className="w-4 h-4 text-zinc-500" />}
                  <div>
                    <span className="text-sm text-white capitalize">{p.name}</span>
                    <p className="text-xs text-zinc-500">{p.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* API Keys */}
          <Card title="API Keys">
            {!editingKeys ? (
              <div>
                <div className="space-y-2 mb-3">
                  {[{ key: "anthropic", label: "Anthropic" }, { key: "openai", label: "OpenAI" }, { key: "google", label: "Google" }].map(({ key, label }) => (
                    <div key={key} className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                      <span className="text-sm text-zinc-300">{label}</span>
                      <span className="text-xs text-zinc-500">{(apiKeys as Record<string, string>)?.[key] || "Not set"}</span>
                    </div>
                  ))}
                </div>
                <button onClick={startEditKeys} className="px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-white border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors">
                  Edit API Keys
                </button>
                {keySaveResult && <p className={`text-xs mt-2 ${keySaveResult.ok ? "text-emerald-400" : "text-red-400"}`}>{keySaveResult.msg}</p>}
              </div>
            ) : (
              <div className="space-y-3">
                {[
                  { key: "anthropic", label: "Anthropic API Key", placeholder: "sk-ant-..." },
                  { key: "openai", label: "OpenAI API Key", placeholder: "sk-..." },
                  { key: "google", label: "Google API Key", placeholder: "AIza..." },
                ].map(({ key, label, placeholder }) => (
                  <div key={key}>
                    <label className="text-xs text-zinc-400 block mb-1">{label}</label>
                    <div className="flex gap-2">
                      <input type={showApiKeys[key] ? "text" : "password"} value={keyDraft[key] || ""} onChange={(e) => setKeyDraft((d) => ({ ...d, [key]: e.target.value }))} placeholder={placeholder}
                        className="flex-1 bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600" />
                      <button onClick={() => setShowApiKeys((s) => ({ ...s, [key]: !s[key] }))} className="p-1.5 text-zinc-500 hover:text-white">
                        {showApiKeys[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                ))}
                <p className="text-xs text-zinc-600">Leave blank to keep existing key.</p>
                <div className="flex gap-2 pt-1">
                  <button onClick={saveApiKeys} className="px-4 py-1.5 bg-brand-500 hover:bg-brand-400 text-white rounded-lg text-sm transition-colors">Save Keys</button>
                  <button onClick={() => setEditingKeys(false)} className="px-4 py-1.5 bg-surface-3 text-zinc-400 hover:text-white border border-border-subtle rounded-lg text-sm transition-colors">Cancel</button>
                </div>
              </div>
            )}
          </Card>

          {/* Current Configuration */}
          {config && (
            <Card title="Current Configuration">
              <div className="space-y-2">
                {Object.entries(config).map(([op, cfg]) => (
                  <div key={op} className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                    <span className="text-sm text-zinc-300 capitalize">{op}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-500">{cfg.provider}</span>
                      <span className="text-xs text-brand-400">{cfg.model}</span>
                      {health?.status && (health.status[op] ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ===== MESSAGING TAB ===== */}
      {tab === "bridge" && (
        <div className="space-y-6">
          {/* Platform Status */}
          <Card title="Platform Status" icon={MessageSquare}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {["telegram", "mattermost"].map((p) => {
                const plat = bridgeStatus?.platforms?.[p];
                const connected = plat?.connected;
                const configured = !!plat;
                return (
                  <div key={p} className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-3">
                    <span className="text-sm text-white capitalize">{p}</span>
                    <div className="flex items-center gap-2">
                      {!bridgeStatus?.configured || !configured ? (
                        <span className="text-xs text-zinc-500">Not configured</span>
                      ) : connected ? (
                        <><CheckCircle className="w-4 h-4 text-emerald-400" /><span className="text-xs text-emerald-400">Connected</span></>
                      ) : (
                        <><XCircle className="w-4 h-4 text-red-400" /><span className="text-xs text-red-400">Disconnected</span></>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Bridge Configuration */}
          <Card title="Configuration">
            {!bridgeEditing ? (
              <div>
                <div className="space-y-2 mb-4">
                  {bridgeConfig?.telegram?.bot_token && (
                    <ConfigRow label="Telegram Bot Token" value={bridgeConfig.telegram.bot_token} />
                  )}
                  {bridgeConfig?.telegram?.user_id && (
                    <ConfigRow label="Telegram User ID" value={bridgeConfig.telegram.user_id} accent />
                  )}
                  {bridgeConfig?.mattermost?.url && (
                    <ConfigRow label="Mattermost URL" value={bridgeConfig.mattermost.url} accent />
                  )}
                  {bridgeConfig?.mattermost?.bot_token && (
                    <ConfigRow label="Mattermost Bot Token" value={bridgeConfig.mattermost.bot_token} />
                  )}
                  {!bridgeConfig?.telegram?.bot_token && !bridgeConfig?.mattermost?.url && (
                    <p className="text-xs text-zinc-500">No platforms configured. Click Edit to set up.</p>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button onClick={startEditBridge} className="px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-white border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors">Edit Configuration</button>
                  {bridgeStatus?.platforms?.telegram && (
                    <button onClick={() => handleTestBridge("telegram")} disabled={!!bridgeTesting} className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-white border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors disabled:opacity-50">
                      {bridgeTesting === "telegram" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />} Test Telegram
                    </button>
                  )}
                  {bridgeStatus?.platforms?.mattermost && (
                    <button onClick={() => handleTestBridge("mattermost")} disabled={!!bridgeTesting} className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-white border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors disabled:opacity-50">
                      {bridgeTesting === "mattermost" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />} Test Mattermost
                    </button>
                  )}
                </div>
                {bridgeSaveResult && <p className={`text-xs mt-3 ${bridgeSaveResult.ok ? "text-emerald-400" : "text-amber-400"}`}>{bridgeSaveResult.msg}</p>}
                {Object.entries(bridgeTestResult).map(([p, r]) => (
                  <p key={p} className={`text-xs mt-2 ${r.ok ? "text-emerald-400" : "text-red-400"}`}>{p}: {r.msg}</p>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                <h3 className="text-xs text-zinc-500 font-semibold uppercase tracking-wider">Telegram</h3>
                <div className="space-y-2">
                  <InputField label="Bot Token" type={showTokens.tgToken ? "text" : "password"} value={bridgeDraft.telegram?.bot_token || ""} placeholder="123456:ABC-DEF..."
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, telegram: { ...d.telegram, bot_token: v } }))}
                    toggle={() => setShowTokens((s) => ({ ...s, tgToken: !s.tgToken }))} showToggle toggled={showTokens.tgToken} />
                  <InputField label="User ID (for notifications)" value={bridgeDraft.telegram?.user_id || ""} placeholder="123456789"
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, telegram: { ...d.telegram, user_id: v } }))} />
                  <InputField label="Webhook Base URL (blank for polling)" value={bridgeDraft.telegram?.webhook_base_url || ""} placeholder="https://your-server.com"
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, telegram: { ...d.telegram, webhook_base_url: v } }))} />
                </div>
                <h3 className="text-xs text-zinc-500 font-semibold uppercase tracking-wider pt-2">Mattermost</h3>
                <div className="space-y-2">
                  <InputField label="Server URL" value={bridgeDraft.mattermost?.url || ""} placeholder="https://mattermost.example.com"
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, mattermost: { ...d.mattermost, url: v } }))} />
                  <InputField label="Bot Token" type={showTokens.mmToken ? "text" : "password"} value={bridgeDraft.mattermost?.bot_token || ""} placeholder="abcdefghijklmnop"
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, mattermost: { ...d.mattermost, bot_token: v } }))}
                    toggle={() => setShowTokens((s) => ({ ...s, mmToken: !s.mmToken }))} showToggle toggled={showTokens.mmToken} />
                  <InputField label="Channel ID" value={bridgeDraft.mattermost?.channel_id || ""} placeholder="abc123def456"
                    onChange={(v) => setBridgeDraft((d) => ({ ...d, mattermost: { ...d.mattermost, channel_id: v } }))} />
                </div>
                <div className="flex gap-2 pt-2">
                  <button onClick={saveBridgeConfig} className="px-4 py-1.5 bg-brand-500 hover:bg-brand-400 text-white rounded-lg text-sm transition-colors">Save & Connect</button>
                  <button onClick={() => setBridgeEditing(false)} className="px-4 py-1.5 bg-surface-3 text-zinc-400 hover:text-white border border-border-subtle rounded-lg text-sm transition-colors">Cancel</button>
                </div>
              </div>
            )}
          </Card>

          {/* Notification Preferences */}
          <Card title="Notification Routing" icon={BellRing}>
            <p className="text-xs text-zinc-500 mb-4">Choose which notifications go to each channel.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-zinc-500 uppercase tracking-wider">
                    <th className="text-left pb-3 pr-4 font-medium">Notification</th>
                    <th className="text-center pb-3 px-4 font-medium">Dashboard</th>
                    <th className="text-center pb-3 px-4 font-medium">Telegram</th>
                  </tr>
                </thead>
                <tbody className="text-zinc-300">
                  {(["daily_brief", "connection_alert", "resurface"] as const).map((notifType) => {
                    const channels = bridgeConfig?.outbound_channels ?? {};
                    const entries = channels[notifType] ?? [];
                    return (
                      <tr key={notifType} className="border-t border-border-subtle">
                        <td className="py-3 pr-4 text-[13px] capitalize">{notifType.replace(/_/g, " ")}</td>
                        {(["dashboard", "telegram"] as const).map((channel) => {
                          const isEnabled = entries.some((e) => typeof e === "object" && e.platform === channel);
                          return (
                            <td key={channel} className="py-3 px-4 text-center">
                              <input type="checkbox" checked={isEnabled} onChange={() => toggleNotification(notifType, channel, isEnabled)}
                                className="w-4 h-4 accent-cyan-500 cursor-pointer rounded" />
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Message Log */}
          {bridgeLog && bridgeLog.length > 0 && (
            <Card title="Message Log">
              <button onClick={() => setShowBridgeLog(!showBridgeLog)} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mb-3">
                {showBridgeLog ? "Hide" : "Show"} log ({bridgeLog.length} messages)
              </button>
              {showBridgeLog && (
                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {bridgeLog.map((entry: BridgeLogEntry) => (
                    <div key={entry.id} className="flex items-center justify-between bg-surface-3 rounded-lg px-3 py-1.5 text-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={entry.direction === "inbound" ? "text-blue-400" : "text-emerald-400"}>{entry.direction === "inbound" ? "IN" : "OUT"}</span>
                        <span className="text-zinc-500 uppercase">{entry.platform}</span>
                        {entry.intent && <span className="text-brand-400">{entry.intent}</span>}
                        <span className="text-zinc-400 truncate max-w-64">{entry.text || ""}</span>
                      </div>
                      <span className="text-zinc-600 shrink-0 ml-2">{formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {/* ===== DATA TAB ===== */}
      {tab === "data" && (
        <div className="space-y-6">
          {/* Import */}
          <Card title="Import" icon={Upload}>
            <p className="text-xs text-zinc-500 mb-4">Import notes from other tools. Files are processed in the background.</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { format: "notion", label: "Notion Export", accept: ".zip", desc: "Markdown zip" },
                { format: "obsidian", label: "Obsidian Vault", accept: ".zip", desc: "Zipped vault" },
                { format: "bookmarks", label: "Bookmarks", accept: ".html,.htm", desc: "Browser HTML export" },
              ].map(({ format, label, accept, desc }) => (
                <label key={format} className="flex items-center gap-3 p-3.5 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors cursor-pointer">
                  <input type="file" accept={accept} className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) handleImport(format, file); e.target.value = ""; }} />
                  {importLoading === format ? <Loader2 className="w-5 h-5 text-brand-400 animate-spin shrink-0" /> : <Upload className="w-5 h-5 text-zinc-500 shrink-0" />}
                  <div><span className="text-sm text-white">{label}</span><p className="text-xs text-zinc-500">{desc}</p></div>
                </label>
              ))}
            </div>
            {importResult && <p className={`text-xs mt-3 ${importResult.ok ? "text-emerald-400" : "text-red-400"}`}>{importResult.msg}</p>}
          </Card>

          {/* Export */}
          <Card title="Export & Backup" icon={Download}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <a href="/api/export/json" className="flex items-center gap-3 p-3.5 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors">
                <Download className="w-5 h-5 text-zinc-500" />
                <div><span className="text-sm text-white">JSON Backup</span><p className="text-xs text-zinc-500">Full database export</p></div>
              </a>
              <a href="/api/export/markdown" className="flex items-center gap-3 p-3.5 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors">
                <Download className="w-5 h-5 text-zinc-500" />
                <div><span className="text-sm text-white">Markdown Archive</span><p className="text-xs text-zinc-500">All notes as .md (zip)</p></div>
              </a>
            </div>
          </Card>

          {/* API */}
          <Card title="API" icon={Code}>
            <p className="text-xs text-zinc-500">
              API documentation available at{" "}
              <a href="/docs" target="_blank" className="text-brand-400 hover:text-brand-300 transition-colors">/docs</a> (Swagger UI)
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}

// --- Helper components ---

function Card({ title, icon: Icon, children }: { title: string; icon?: typeof Activity; children: React.ReactNode }) {
  return (
    <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
      <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-4 flex items-center gap-2">
        {Icon && <Icon className="w-3.5 h-3.5" />} {title}
      </h2>
      {children}
    </section>
  );
}

function ConfigRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
      <span className="text-sm text-zinc-300">{label}</span>
      <span className={`text-xs ${accent ? "text-brand-400" : "text-zinc-500"}`}>{value}</span>
    </div>
  );
}

function InputField({ label, value, placeholder, type = "text", onChange, showToggle, toggle, toggled }: {
  label: string; value: string; placeholder: string; type?: string;
  onChange: (v: string) => void; showToggle?: boolean; toggle?: () => void; toggled?: boolean;
}) {
  return (
    <div>
      <label className="text-xs text-zinc-400 block mb-1">{label}</label>
      <div className="flex gap-2">
        <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
          className="flex-1 bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600" />
        {showToggle && toggle && (
          <button onClick={toggle} className="p-1.5 text-zinc-500 hover:text-white">
            {toggled ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );
}
