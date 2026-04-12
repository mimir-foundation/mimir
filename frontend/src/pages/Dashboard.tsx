import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getNotes,
  getStats,
  getBrief,
  getResurfaceItems,
  clickResurface,
  dismissResurface,
  getErroredNotes,
  retryNote,
} from "../lib/api";
import NoteCard from "../components/NoteCard";
import { Link } from "react-router-dom";
import {
  Activity,
  BookOpen,
  Link2,
  Lightbulb,
  AlertCircle,
  Newspaper,
  Bell,
  X,
  ChevronRight,
  RefreshCw,
  Loader2,
  Star,
} from "lucide-react";
import { useState } from "react";

export default function Dashboard() {
  const queryClient = useQueryClient();

  const { data: recent } = useQuery({
    queryKey: ["notes", "recent"],
    queryFn: () => getNotes({ sort: "recent", limit: 10 }),
    refetchInterval: 10_000,
  });

  const { data: starred } = useQuery({
    queryKey: ["notes", "starred"],
    queryFn: () => getNotes({ is_starred: true, limit: 5 }),
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 10_000,
  });

  const { data: briefData } = useQuery({
    queryKey: ["brief"],
    queryFn: () => getBrief(),
    refetchInterval: 60_000,
  });

  const { data: resurfaceData } = useQuery({
    queryKey: ["resurface"],
    queryFn: () => getResurfaceItems(5),
    refetchInterval: 30_000,
  });

  const { data: erroredData } = useQuery({
    queryKey: ["errored-notes"],
    queryFn: getErroredNotes,
    refetchInterval: 30_000,
    enabled: (stats?.errored ?? 0) > 0,
  });

  const [retrying, setRetrying] = useState<string>("");

  async function handleRetry(noteId: string) {
    setRetrying(noteId);
    try {
      await retryNote(noteId);
      queryClient.invalidateQueries({ queryKey: ["errored-notes"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    } finally {
      setRetrying("");
    }
  }

  async function handleResurfaceClick(id: string) {
    await clickResurface(id);
    queryClient.invalidateQueries({ queryKey: ["resurface"] });
  }

  async function handleResurfaceDismiss(id: string, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    await dismissResurface(id);
    queryClient.invalidateQueries({ queryKey: ["resurface"] });
  }

  const brief = briefData?.brief;
  const resurface = resurfaceData?.items;

  return (
    <div className="space-y-8">
      {/* Header with logo */}
      <div className="flex items-center gap-4">
        <img src="/logo.png" alt="Mimir" className="w-10 h-10" />
        <div>
          <h1 className="text-xl font-bold text-white">Good to see you</h1>
          <p className="text-sm text-zinc-500">Here's what's happening in your second brain.</p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard icon={BookOpen} label="Notes" value={stats.notes} color="text-brand-400" />
          <StatCard icon={Lightbulb} label="Concepts" value={stats.concepts} color="text-violet-400" />
          <StatCard icon={Link2} label="Connections" value={stats.connections} color="text-emerald-400" />
          <StatCard icon={Activity} label="Entities" value={stats.entities} color="text-amber-400" />
        </div>
      )}

      {/* Two-column layout for brief + resurface */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Daily Brief */}
        {brief && (
          <section className="lg:col-span-3 bg-gradient-to-br from-brand-950/40 to-surface-2 border border-brand-900/30 rounded-2xl p-6">
            <h2 className="text-xs font-semibold text-brand-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Newspaper className="w-3.5 h-3.5" />
              Daily Brief — {brief.brief_date}
            </h2>
            <div className="text-[13px] text-zinc-300 whitespace-pre-line leading-relaxed">
              {brief.content}
            </div>
          </section>
        )}

        {/* Resurface Items */}
        {resurface && resurface.length > 0 && (
          <section className={brief ? "lg:col-span-2" : "lg:col-span-5"}>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Bell className="w-3.5 h-3.5 text-amber-400" />
              Resurface
              <span className="bg-amber-500/10 text-amber-400 text-[10px] px-2 py-0.5 rounded-full border border-amber-500/20">
                {resurface.length}
              </span>
            </h2>
            <div className="space-y-2">
              {resurface.map((item) => (
                <Link
                  key={item.id}
                  to={`/notes/${item.note_id}`}
                  onClick={() => handleResurfaceClick(item.id)}
                  className="flex items-center gap-3 bg-surface-2 border border-border-subtle rounded-xl p-3 hover:border-amber-500/30 transition-all duration-150 group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] text-white font-medium truncate">
                      {item.note_title || "Untitled"}
                    </p>
                    <p className="text-[11px] text-zinc-500 mt-0.5 line-clamp-1">
                      {item.reason}
                    </p>
                  </div>
                  <span className="text-[10px] text-zinc-600 shrink-0 px-2 py-0.5 bg-surface-3 rounded-md">
                    {item.queue_type.replace("_", " ")}
                  </span>
                  <button
                    onClick={(e) => handleResurfaceDismiss(item.id, e)}
                    className="p-1 text-zinc-600 hover:text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Dismiss"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* Processing status */}
      {stats && (stats.pending > 0 || stats.processing > 0 || stats.errored > 0) && (
        <div className="bg-surface-2 rounded-xl border border-border-subtle p-4">
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
            Processing Queue
          </h2>
          <div className="flex gap-4 text-[13px]">
            {stats.pending > 0 && (
              <span className="text-amber-400 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
                {stats.pending} pending
              </span>
            )}
            {stats.processing > 0 && (
              <span className="text-brand-400 flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" />
                {stats.processing} processing
              </span>
            )}
            {stats.errored > 0 && (
              <span className="text-red-400 flex items-center gap-1.5">
                <AlertCircle className="w-3 h-3" /> {stats.errored} errored
              </span>
            )}
          </div>
        </div>
      )}

      {/* Errored Notes */}
      {erroredData?.notes && erroredData.notes.length > 0 && (
        <section className="bg-red-950/10 border border-red-500/20 rounded-2xl p-5">
          <h2 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5" />
            Errored Notes
            <span className="bg-red-500/10 text-red-400 text-[10px] px-2 py-0.5 rounded-full border border-red-500/20">
              {erroredData.notes.length}
            </span>
          </h2>
          <div className="space-y-2">
            {erroredData.notes.map((note) => (
              <div
                key={note.id}
                className="flex items-center gap-3 bg-surface-2 border border-border-subtle rounded-xl p-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-white font-medium truncate">
                    {note.title || "Untitled"}
                  </p>
                  <p className="text-[11px] text-red-400/80 mt-0.5 line-clamp-1">
                    {note.error_message}
                  </p>
                  {note.retry_count > 0 && (
                    <p className="text-[11px] text-zinc-600 mt-0.5">
                      Retried {note.retry_count}x
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleRetry(note.id)}
                  disabled={retrying === note.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-zinc-300 hover:text-white border border-border-subtle hover:border-red-500/30 rounded-lg text-xs transition-all disabled:opacity-50"
                >
                  {retrying === note.id ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3 h-3" />
                  )}
                  Retry
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Starred */}
      {starred?.notes && starred.notes.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Star className="w-3.5 h-3.5 text-amber-400" /> Starred
          </h2>
          <div className="space-y-2">
            {starred.notes.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </div>
        </section>
      )}

      {/* Recent */}
      <section>
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
          Recent Captures
        </h2>
        {recent?.notes && recent.notes.length > 0 ? (
          <div className="space-y-2">
            {recent.notes.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </div>
        ) : (
          <div className="bg-surface-2 rounded-2xl border border-border-subtle p-8 text-center">
            <img src="/logo.png" alt="Mimir" className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="text-zinc-500 text-sm">
              No notes yet. Use the capture bar above to add your first note.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-surface-2 rounded-xl border border-border-subtle p-4 hover:border-border-hover transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg bg-surface-3`}>
          <Icon className={`w-3.5 h-3.5 ${color}`} />
        </div>
        <span className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">{label}</span>
      </div>
      <span className="text-2xl font-bold text-white tabular-nums">{value.toLocaleString()}</span>
    </div>
  );
}
