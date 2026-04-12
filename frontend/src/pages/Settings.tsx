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
} from "lucide-react";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

export default function Settings() {
  const queryClient = useQueryClient();
  const [applying, setApplying] = useState("");
  const [running, setRunning] = useState("");

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const { data: config } = useQuery({
    queryKey: ["harness-config"],
    queryFn: getHarnessConfig,
  });

  const { data: health } = useQuery({
    queryKey: ["harness-health"],
    queryFn: getHarnessHealth,
  });

  const { data: activityData } = useQuery({
    queryKey: ["agent-activity"],
    queryFn: () => getAgentActivity(15),
    refetchInterval: 15_000,
  });

  const { data: interests } = useQuery({
    queryKey: ["interests"],
    queryFn: getInterests,
  });

  const { data: bridgeStatus } = useQuery({
    queryKey: ["bridge-status"],
    queryFn: async () => {
      try { return await getBridgeStatus(); }
      catch { return { configured: false, platforms: {} } as BridgeStatus; }
    },
    refetchInterval: 15_000,
  });

  const { data: bridgeConfig } = useQuery({
    queryKey: ["bridge-config"],
    queryFn: async () => {
      try { return await getBridgeConfig(); }
      catch { return {} as BridgeConfig; }
    },
  });

  const { data: bridgeLog } = useQuery({
    queryKey: ["bridge-log"],
    queryFn: async () => {
      try { return await getBridgeLog(20); }
      catch { return [] as BridgeLogEntry[]; }
    },
    refetchInterval: 15_000,
  });

  const { data: apiKeys } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      try { return await getApiKeys(); }
      catch { return { anthropic: "", openai: "", google: "" }; }
    },
  });

  const [editingKeys, setEditingKeys] = useState(false);
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [keySaveResult, setKeySaveResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({});

  function startEditKeys() {
    // Start with empty — user enters full keys (masked values aren't useful to edit)
    setKeyDraft({ anthropic: "", openai: "", google: "" });
    setEditingKeys(true);
    setKeySaveResult(null);
  }

  async function saveApiKeys() {
    setKeySaveResult(null);
    try {
      // Only send keys the user actually typed — blank means "don't change"
      const toSend: Record<string, string> = {};
      for (const [k, v] of Object.entries(keyDraft)) {
        if (v.trim()) toSend[k] = v.trim();
      }
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

  async function handleApplyPreset(preset: string) {
    setApplying(preset);
    try {
      await applyPreset(preset);
      queryClient.invalidateQueries({ queryKey: ["harness-config"] });
      queryClient.invalidateQueries({ queryKey: ["harness-health"] });
    } finally {
      setApplying("");
    }
  }

  async function handleAction(action: string, fn: () => Promise<unknown>) {
    setRunning(action);
    try {
      await fn();
      queryClient.invalidateQueries({ queryKey: ["agent-activity"] });
    } finally {
      setRunning("");
    }
  }

  // Bridge state
  const [bridgeEditing, setBridgeEditing] = useState(false);
  const [bridgeDraft, setBridgeDraft] = useState<BridgeConfig>({});
  const [bridgeTesting, setBridgeTesting] = useState("");
  const [bridgeTestResult, setBridgeTestResult] = useState<Record<string, { ok: boolean; msg: string }>>({});
  const [showTokens, setShowTokens] = useState<Record<string, boolean>>({});
  const [showBridgeLog, setShowBridgeLog] = useState(false);
  const [importLoading, setImportLoading] = useState("");
  const [importResult, setImportResult] = useState<{ format: string; msg: string; ok: boolean } | null>(null);

  async function handleImport(format: string, file: File) {
    setImportLoading(format);
    setImportResult(null);
    try {
      const fn = format === "notion" ? importNotion : format === "obsidian" ? importObsidian : importBookmarks;
      const res = await fn(file);
      if (res.error) {
        setImportResult({ format, msg: res.error, ok: false });
      } else {
        setImportResult({ format, msg: `Imported ${res.imported} items${res.errors ? `, ${res.errors} errors` : ""}`, ok: true });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
      }
    } catch (e: unknown) {
      setImportResult({ format, msg: e instanceof Error ? e.message : "Import failed", ok: false });
    } finally {
      setImportLoading("");
    }
  }

  function startEditBridge() {
    setBridgeDraft(bridgeConfig || {});
    setBridgeEditing(true);
  }

  const [bridgeSaveResult, setBridgeSaveResult] = useState<{ ok: boolean; msg: string } | null>(null);

  async function saveBridgeConfig() {
    setBridgeSaveResult(null);
    try {
      const res = await updateBridgeConfig(bridgeDraft);
      queryClient.invalidateQueries({ queryKey: ["bridge-config"] });
      queryClient.invalidateQueries({ queryKey: ["bridge-status"] });
      setBridgeEditing(false);
      if (res.status === "reloaded") {
        const platforms = (res as Record<string, unknown>).platforms as string[] | undefined;
        setBridgeSaveResult({
          ok: true,
          msg: platforms?.length
            ? `Connected: ${platforms.join(", ")}`
            : "Saved. No platforms configured yet.",
        });
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
      setBridgeTestResult((prev) => ({
        ...prev,
        [platform]: { ok: res.success, msg: res.success ? "Connected!" : res.error || "Failed" },
      }));
    } catch (e: unknown) {
      setBridgeTestResult((prev) => ({
        ...prev,
        [platform]: { ok: false, msg: e instanceof Error ? e.message : "Failed" },
      }));
    } finally {
      setBridgeTesting("");
    }
  }

  const presets = [
    { name: "local", desc: "All local via Ollama (free, private)" },
    { name: "hybrid", desc: "Local embeddings + cloud reasoning" },
    { name: "cloud", desc: "All cloud APIs (best quality)" },
    { name: "budget", desc: "Local + cheap cloud model" },
  ];

  const statusColors: Record<string, string> = {
    complete: "text-emerald-400",
    running: "text-blue-400",
    error: "text-red-400",
  };

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-bold text-white">Settings</h1>

      {/* System Status */}
      {stats && (
        <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
          <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" /> System Status
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-zinc-500">Total Notes</span>
              <p className="text-xl font-bold text-white">{stats.notes}</p>
            </div>
            <div>
              <span className="text-zinc-500">Concepts</span>
              <p className="text-xl font-bold text-white">{stats.concepts}</p>
            </div>
            <div>
              <span className="text-zinc-500">Connections</span>
              <p className="text-xl font-bold text-white">{stats.connections}</p>
            </div>
            <div>
              <span className="text-zinc-500">Entities</span>
              <p className="text-xl font-bold text-white">{stats.entities}</p>
            </div>
          </div>
        </section>
      )}

      {/* Agent Controls */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
          <Brain className="w-4 h-4" /> Agent Controls
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={() => handleAction("brief", generateBrief)}
            disabled={!!running}
            className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors disabled:opacity-50"
          >
            {running === "brief" ? (
              <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
            ) : (
              <Newspaper className="w-4 h-4 text-zinc-500" />
            )}
            <div className="text-left">
              <span className="text-sm text-white">Generate Brief</span>
              <p className="text-xs text-zinc-500">Daily digest now</p>
            </div>
          </button>
          <button
            onClick={() => handleAction("scan", triggerDeepScan)}
            disabled={!!running}
            className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors disabled:opacity-50"
          >
            {running === "scan" ? (
              <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
            ) : (
              <Search className="w-4 h-4 text-zinc-500" />
            )}
            <div className="text-left">
              <span className="text-sm text-white">Deep Scan</span>
              <p className="text-xs text-zinc-500">Find connections</p>
            </div>
          </button>
          <button
            onClick={() => handleAction("taxonomy", triggerTaxonomyRebuild)}
            disabled={!!running}
            className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors disabled:opacity-50"
          >
            {running === "taxonomy" ? (
              <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
            ) : (
              <GitBranch className="w-4 h-4 text-zinc-500" />
            )}
            <div className="text-left">
              <span className="text-sm text-white">Rebuild Taxonomy</span>
              <p className="text-xs text-zinc-500">Merge & organize</p>
            </div>
          </button>
        </div>
      </section>

      {/* Interest Signals */}
      {interests?.interests && interests.interests.length > 0 && (
        <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
          <h2 className="text-sm font-medium text-zinc-400 mb-3">
            Current Interests (decayed)
          </h2>
          <div className="flex flex-wrap gap-2">
            {interests.interests.slice(0, 15).map((i) => (
              <span
                key={i.topic}
                className="px-2 py-1 bg-surface-3 text-zinc-300 rounded text-xs"
                style={{ opacity: Math.min(1, 0.3 + i.score * 0.7) }}
              >
                {i.topic}{" "}
                <span className="text-zinc-600">{i.score.toFixed(1)}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {/* AI Engine Config */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
          <Cpu className="w-4 h-4" /> AI Engine
        </h2>

        <div className="mb-6">
          <h3 className="text-xs text-zinc-500 mb-2">Presets</h3>
          <div className="grid grid-cols-2 gap-2">
            {presets.map((p) => (
              <button
                key={p.name}
                onClick={() => handleApplyPreset(p.name)}
                disabled={!!applying}
                className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl text-left hover:border-brand-500/30 transition-colors"
              >
                {applying === p.name ? (
                  <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                ) : (
                  <Cpu className="w-4 h-4 text-zinc-500" />
                )}
                <div>
                  <span className="text-sm text-white capitalize">
                    {p.name}
                  </span>
                  <p className="text-xs text-zinc-500">{p.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* API Keys */}
        <div className="mb-6">
          <h3 className="text-xs text-zinc-500 mb-2">API Keys</h3>
          {!editingKeys ? (
            <div>
              <div className="space-y-2 mb-3">
                {[
                  { key: "anthropic", label: "Anthropic" },
                  { key: "openai", label: "OpenAI" },
                  { key: "google", label: "Google" },
                ].map(({ key, label }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5"
                  >
                    <span className="text-sm text-zinc-300">{label}</span>
                    <span className="text-xs text-zinc-500">
                      {(apiKeys as Record<string, string>)?.[key] || "Not set"}
                    </span>
                  </div>
                ))}
              </div>
              <button
                onClick={startEditKeys}
                className="px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-zinc-100 border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors"
              >
                Edit API Keys
              </button>
              {keySaveResult && (
                <p className={`text-xs mt-2 ${keySaveResult.ok ? "text-emerald-400" : "text-red-400"}`}>
                  {keySaveResult.msg}
                </p>
              )}
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
                    <input
                      type={showApiKeys[key] ? "text" : "password"}
                      value={keyDraft[key] || ""}
                      onChange={(e) => setKeyDraft((d) => ({ ...d, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="flex-1 bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                    />
                    <button
                      onClick={() => setShowApiKeys((s) => ({ ...s, [key]: !s[key] }))}
                      className="p-1.5 text-zinc-500 hover:text-zinc-100"
                    >
                      {showApiKeys[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              ))}
              <p className="text-xs text-zinc-600">Leave blank to keep existing key. Only non-empty fields are updated.</p>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={saveApiKeys}
                  className="px-4 py-1.5 bg-brand-500 hover:bg-brand-400 text-white rounded-lg text-sm transition-colors"
                >
                  Save Keys
                </button>
                <button
                  onClick={() => setEditingKeys(false)}
                  className="px-4 py-1.5 bg-surface-3 text-zinc-400 hover:text-zinc-100 border border-border-subtle rounded-lg text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {config && (
          <div>
            <h3 className="text-xs text-zinc-500 mb-2">
              Current Configuration
            </h3>
            <div className="space-y-2">
              {Object.entries(config).map(([op, cfg]) => (
                <div
                  key={op}
                  className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5"
                >
                  <span className="text-sm text-zinc-300 capitalize">{op}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-500">
                      {cfg.provider}
                    </span>
                    <span className="text-xs text-brand-400">{cfg.model}</span>
                    {health?.status &&
                      (health.status[op] ? (
                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-400" />
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Agent Activity Log */}
      {activityData?.log && activityData.log.length > 0 && (
        <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
          <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Agent Activity
          </h2>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {activityData.log.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className={statusColors[entry.status] || "text-zinc-400"}>
                    {entry.status === "running" ? "●" : entry.status === "complete" ? "✓" : "✗"}
                  </span>
                  <span className="text-zinc-300">
                    {entry.action_type.replace("_", " ")}
                  </span>
                  {entry.error_message && (
                    <span className="text-red-400 truncate max-w-48">
                      {entry.error_message}
                    </span>
                  )}
                </div>
                <span className="text-zinc-600 shrink-0">
                  {formatDistanceToNow(new Date(entry.started_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Messaging Bridge */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
          <MessageSquare className="w-4 h-4" /> Messaging Bridge
        </h2>

        {/* Platform status indicators */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
          {["telegram", "mattermost"].map((p) => {
            const plat = bridgeStatus?.platforms?.[p];
            const connected = plat?.connected;
            const configured = !!plat;
            return (
              <div
                key={p}
                className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-3"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white capitalize">{p}</span>
                </div>
                <div className="flex items-center gap-2">
                  {!bridgeStatus?.configured || !configured ? (
                    <span className="text-xs text-zinc-500">Not configured</span>
                  ) : connected ? (
                    <>
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                      <span className="text-xs text-emerald-400">Connected</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4 text-red-400" />
                      <span className="text-xs text-red-400">Disconnected</span>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Configuration */}
        {!bridgeEditing ? (
          <div>
            <h3 className="text-xs text-zinc-500 mb-2">Configuration</h3>
            <div className="space-y-2 mb-4">
              {bridgeConfig?.telegram?.bot_token && (
                <div className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                  <span className="text-sm text-zinc-300">Telegram Bot Token</span>
                  <span className="text-xs text-zinc-500">{bridgeConfig.telegram.bot_token}</span>
                </div>
              )}
              {bridgeConfig?.telegram?.user_id && (
                <div className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                  <span className="text-sm text-zinc-300">Telegram User ID</span>
                  <span className="text-xs text-brand-400">{bridgeConfig.telegram.user_id}</span>
                </div>
              )}
              {bridgeConfig?.mattermost?.url && (
                <div className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                  <span className="text-sm text-zinc-300">Mattermost URL</span>
                  <span className="text-xs text-brand-400">{bridgeConfig.mattermost.url}</span>
                </div>
              )}
              {bridgeConfig?.mattermost?.bot_token && (
                <div className="flex items-center justify-between bg-surface-3 rounded-xl px-4 py-2.5">
                  <span className="text-sm text-zinc-300">Mattermost Bot Token</span>
                  <span className="text-xs text-zinc-500">{bridgeConfig.mattermost.bot_token}</span>
                </div>
              )}
              {!bridgeConfig?.telegram?.bot_token && !bridgeConfig?.mattermost?.url && (
                <p className="text-xs text-zinc-500">
                  No platforms configured. Set tokens via environment variables or click Edit to configure.
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={startEditBridge}
                className="px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-zinc-100 border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors"
              >
                Edit Configuration
              </button>
              {bridgeStatus?.platforms?.telegram && (
                <button
                  onClick={() => handleTestBridge("telegram")}
                  disabled={!!bridgeTesting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-zinc-100 border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  {bridgeTesting === "telegram" ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Send className="w-3 h-3" />
                  )}
                  Test Telegram
                </button>
              )}
              {bridgeStatus?.platforms?.mattermost && (
                <button
                  onClick={() => handleTestBridge("mattermost")}
                  disabled={!!bridgeTesting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-zinc-100 border border-border-subtle hover:border-brand-500/30 rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  {bridgeTesting === "mattermost" ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Send className="w-3 h-3" />
                  )}
                  Test Mattermost
                </button>
              )}
            </div>
            {/* Save / test results */}
            {bridgeSaveResult && (
              <p className={`text-xs mt-3 ${bridgeSaveResult.ok ? "text-emerald-400" : "text-amber-400"}`}>
                {bridgeSaveResult.msg}
              </p>
            )}
            {Object.entries(bridgeTestResult).map(([p, r]) => (
              <p key={p} className={`text-xs mt-2 ${r.ok ? "text-emerald-400" : "text-red-400"}`}>
                {p}: {r.msg}
              </p>
            ))}
          </div>
        ) : (
          /* Edit mode */
          <div className="space-y-4">
            <h3 className="text-xs text-zinc-500">Telegram</h3>
            <div className="space-y-2">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Bot Token</label>
                <div className="flex gap-2">
                  <input
                    type={showTokens.tgToken ? "text" : "password"}
                    value={bridgeDraft.telegram?.bot_token || ""}
                    onChange={(e) =>
                      setBridgeDraft((d) => ({
                        ...d,
                        telegram: { ...d.telegram, bot_token: e.target.value },
                      }))
                    }
                    placeholder="123456:ABC-DEF..."
                    className="flex-1 bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                  />
                  <button
                    onClick={() => setShowTokens((s) => ({ ...s, tgToken: !s.tgToken }))}
                    className="p-1.5 text-zinc-500 hover:text-zinc-100"
                  >
                    {showTokens.tgToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">User ID (for notifications)</label>
                <input
                  type="text"
                  value={bridgeDraft.telegram?.user_id || ""}
                  onChange={(e) =>
                    setBridgeDraft((d) => ({
                      ...d,
                      telegram: { ...d.telegram, user_id: e.target.value },
                    }))
                  }
                  placeholder="123456789"
                  className="w-full bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Webhook Base URL (blank for polling)</label>
                <input
                  type="text"
                  value={bridgeDraft.telegram?.webhook_base_url || ""}
                  onChange={(e) =>
                    setBridgeDraft((d) => ({
                      ...d,
                      telegram: { ...d.telegram, webhook_base_url: e.target.value },
                    }))
                  }
                  placeholder="https://your-server.com"
                  className="w-full bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                />
              </div>
            </div>

            <h3 className="text-xs text-zinc-500 pt-2">Mattermost</h3>
            <div className="space-y-2">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Server URL</label>
                <input
                  type="text"
                  value={bridgeDraft.mattermost?.url || ""}
                  onChange={(e) =>
                    setBridgeDraft((d) => ({
                      ...d,
                      mattermost: { ...d.mattermost, url: e.target.value },
                    }))
                  }
                  placeholder="https://mattermost.example.com"
                  className="w-full bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Bot Token</label>
                <div className="flex gap-2">
                  <input
                    type={showTokens.mmToken ? "text" : "password"}
                    value={bridgeDraft.mattermost?.bot_token || ""}
                    onChange={(e) =>
                      setBridgeDraft((d) => ({
                        ...d,
                        mattermost: { ...d.mattermost, bot_token: e.target.value },
                      }))
                    }
                    placeholder="abcdefghijklmnop"
                    className="flex-1 bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                  />
                  <button
                    onClick={() => setShowTokens((s) => ({ ...s, mmToken: !s.mmToken }))}
                    className="p-1.5 text-zinc-500 hover:text-zinc-100"
                  >
                    {showTokens.mmToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Channel ID</label>
                <input
                  type="text"
                  value={bridgeDraft.mattermost?.channel_id || ""}
                  onChange={(e) =>
                    setBridgeDraft((d) => ({
                      ...d,
                      mattermost: { ...d.mattermost, channel_id: e.target.value },
                    }))
                  }
                  placeholder="abc123def456"
                  className="w-full bg-surface-3 text-white px-3 py-2 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] placeholder-zinc-600"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={saveBridgeConfig}
                className="px-4 py-1.5 bg-brand-500 hover:bg-brand-400 text-white rounded-lg text-sm transition-colors"
              >
                Save
              </button>
              <button
                onClick={() => setBridgeEditing(false)}
                className="px-4 py-1.5 bg-surface-3 text-zinc-400 hover:text-zinc-100 border border-border-subtle rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
            <p className="text-xs text-zinc-500">Saving will automatically connect to configured platforms.</p>
          </div>
        )}

        {/* Message Log toggle */}
        {bridgeLog && bridgeLog.length > 0 && (
          <div className="mt-5">
            <button
              onClick={() => setShowBridgeLog(!showBridgeLog)}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              {showBridgeLog ? "Hide" : "Show"} Message Log ({bridgeLog.length})
            </button>
            {showBridgeLog && (
              <div className="space-y-1.5 mt-3 max-h-60 overflow-y-auto">
                {bridgeLog.map((entry: BridgeLogEntry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between bg-surface-3 rounded-lg px-3 py-1.5 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={
                          entry.direction === "inbound"
                            ? "text-blue-400"
                            : "text-emerald-400"
                        }
                      >
                        {entry.direction === "inbound" ? "IN" : "OUT"}
                      </span>
                      <span className="text-zinc-500 uppercase">{entry.platform}</span>
                      {entry.intent && (
                        <span className="text-brand-400">{entry.intent}</span>
                      )}
                      <span className="text-zinc-400 truncate max-w-64">
                        {entry.text || ""}
                      </span>
                    </div>
                    <span className="text-zinc-600 shrink-0 ml-2">
                      {formatDistanceToNow(new Date(entry.created_at), {
                        addSuffix: true,
                      })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Notification Preferences */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
          <BellRing className="w-4 h-4" /> Notification Preferences
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Choose which notifications are delivered to each channel.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-500">
                <th className="text-left pb-2 pr-4">Notification</th>
                <th className="text-center pb-2 px-4">Dashboard</th>
                <th className="text-center pb-2 px-4">Telegram</th>
              </tr>
            </thead>
            <tbody className="text-zinc-300">
              {(["daily_brief", "connection_alert", "resurface"] as const).map((notifType) => (
                <tr key={notifType} className="border-t border-border-subtle">
                  <td className="py-3 pr-4 capitalize">
                    {notifType.replace("_", " ")}
                  </td>
                  {(["dashboard", "telegram"] as const).map((channel) => {
                    const channels = bridgeConfig?.outbound_channels ?? {};
                    const entries = channels[notifType] ?? [];
                    const isEnabled = entries.some(
                      (e) => typeof e === "object" && e.platform === channel,
                    );
                    return (
                      <td key={channel} className="py-3 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={async () => {
                            const current = { ...bridgeConfig } as BridgeConfig;
                            const ch = { ...(current.outbound_channels ?? {}) };
                            let list = [...(ch[notifType] ?? [])];
                            if (isEnabled) {
                              list = list.filter(
                                (e) => !(typeof e === "object" && e.platform === channel),
                              );
                            } else {
                              const recipientId =
                                channel === "telegram"
                                  ? bridgeConfig?.telegram?.user_id ?? ""
                                  : "";
                              list.push({ platform: channel, recipient_id: recipientId });
                            }
                            ch[notifType] = list;
                            current.outbound_channels = ch;
                            try {
                              await updateBridgeConfig(current);
                              queryClient.invalidateQueries({ queryKey: ["bridge-config"] });
                            } catch {
                              // silent — UI will re-fetch
                            }
                          }}
                          className="w-4 h-4 accent-indigo-500 cursor-pointer"
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Import */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
          <Upload className="w-4 h-4" /> Import
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Import notes from other tools. Each file is processed and indexed in the background.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { format: "notion", label: "Notion Export", accept: ".zip", desc: "Markdown zip from Notion" },
            { format: "obsidian", label: "Obsidian Vault", accept: ".zip", desc: "Zipped vault folder" },
            { format: "bookmarks", label: "Browser Bookmarks", accept: ".html,.htm", desc: "HTML bookmark export" },
          ].map(({ format, label, accept, desc }) => (
            <label
              key={format}
              className="flex items-center gap-3 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors cursor-pointer"
            >
              <input
                type="file"
                accept={accept}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleImport(format, file);
                  e.target.value = "";
                }}
              />
              {importLoading === format ? (
                <Loader2 className="w-5 h-5 text-brand-400 animate-spin shrink-0" />
              ) : (
                <Upload className="w-5 h-5 text-zinc-500 shrink-0" />
              )}
              <div className="text-left">
                <span className="text-sm text-white">{label}</span>
                <p className="text-xs text-zinc-500">{desc}</p>
              </div>
            </label>
          ))}
        </div>
        {importResult && (
          <p className={`text-xs mt-3 ${importResult.ok ? "text-emerald-400" : "text-red-400"}`}>
            {importResult.msg}
          </p>
        )}
      </section>

      {/* Export / Backup */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">Export & Backup</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <a
            href="/api/export/json"
            className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors"
          >
            <div className="text-left">
              <span className="text-sm text-white">JSON Backup</span>
              <p className="text-xs text-zinc-500">Full database export</p>
            </div>
          </a>
          <a
            href="/api/export/markdown"
            className="flex items-center gap-2 p-3 bg-surface-3 border border-border-subtle rounded-xl hover:border-brand-500/30 transition-colors"
          >
            <div className="text-left">
              <span className="text-sm text-white">Markdown Archive</span>
              <p className="text-xs text-zinc-500">All notes as .md files (zip)</p>
            </div>
          </a>
        </div>
      </section>

      {/* API Info */}
      <section className="bg-surface-2 rounded-2xl border border-border-subtle p-6">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">API</h2>
        <p className="text-xs text-zinc-500">
          API documentation available at{" "}
          <a
            href="/docs"
            target="_blank"
            className="text-brand-400 hover:text-brand-300"
          >
            /docs
          </a>{" "}
          (Swagger UI)
        </p>
      </section>
    </div>
  );
}
