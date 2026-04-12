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
    <div className="space-y-8 max-w-4xl">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard icon={BookOpen} label="Notes" value={stats.notes} />
          <StatCard icon={Lightbulb} label="Concepts" value={stats.concepts} />
          <StatCard icon={Link2} label="Connections" value={stats.connections} />
          <StatCard icon={Activity} label="Entities" value={stats.entities} />
        </div>
      )}

      {/* Daily Brief */}
      {brief && (
        <section className="bg-indigo-950/30 border border-indigo-900/50 rounded-lg p-5">
          <h2 className="text-sm font-medium text-indigo-300 mb-3 flex items-center gap-2">
            <Newspaper className="w-4 h-4" />
            Daily Brief — {brief.brief_date}
          </h2>
          <div className="text-sm text-gray-300 whitespace-pre-line leading-relaxed">
            {brief.content}
          </div>
        </section>
      )}

      {/* Resurface Items */}
      {resurface && resurface.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
            <Bell className="w-4 h-4 text-amber-400" />
            Resurface
            <span className="bg-amber-900/40 text-amber-300 text-xs px-2 py-0.5 rounded-full">
              {resurface.length}
            </span>
          </h2>
          <div className="space-y-2">
            {resurface.map((item) => (
              <Link
                key={item.id}
                to={`/notes/${item.note_id}`}
                onClick={() => handleResurfaceClick(item.id)}
                className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-amber-800/50 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium truncate">
                    {item.note_title || "Untitled"}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                    {item.reason}
                  </p>
                </div>
                <span className="text-xs text-gray-600 shrink-0 px-2 py-0.5 bg-gray-800 rounded">
                  {item.queue_type.replace("_", " ")}
                </span>
                <button
                  onClick={(e) => handleResurfaceDismiss(item.id, e)}
                  className="p-1 text-gray-600 hover:text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Dismiss"
                >
                  <X className="w-3 h-3" />
                </button>
                <ChevronRight className="w-4 h-4 text-gray-700" />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Processing status */}
      {stats && (stats.pending > 0 || stats.processing > 0 || stats.errored > 0) && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h2 className="text-sm font-medium text-gray-400 mb-2">
            Processing Queue
          </h2>
          <div className="flex gap-4 text-sm">
            {stats.pending > 0 && (
              <span className="text-amber-400">{stats.pending} pending</span>
            )}
            {stats.processing > 0 && (
              <span className="text-blue-400">
                {stats.processing} processing
              </span>
            )}
            {stats.errored > 0 && (
              <span className="text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> {stats.errored} errored
              </span>
            )}
          </div>
        </div>
      )}

      {/* Errored Notes */}
      {erroredData?.notes && erroredData.notes.length > 0 && (
        <section className="bg-red-950/20 border border-red-900/40 rounded-lg p-5">
          <h2 className="text-sm font-medium text-red-300 mb-3 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            Errored Notes
            <span className="bg-red-900/40 text-red-300 text-xs px-2 py-0.5 rounded-full">
              {erroredData.notes.length}
            </span>
          </h2>
          <div className="space-y-2">
            {erroredData.notes.map((note) => (
              <div
                key={note.id}
                className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium truncate">
                    {note.title || "Untitled"}
                  </p>
                  <p className="text-xs text-red-400 mt-0.5 line-clamp-1">
                    {note.error_message}
                  </p>
                  {note.retry_count > 0 && (
                    <p className="text-xs text-gray-600 mt-0.5">
                      Retried {note.retry_count}x
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleRetry(note.id)}
                  disabled={retrying === note.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 text-gray-300 hover:text-white border border-gray-700 hover:border-red-500 rounded-lg text-xs transition-colors disabled:opacity-50"
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
          <h2 className="text-lg font-semibold text-white mb-3">Starred</h2>
          <div className="space-y-2">
            {starred.notes.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </div>
        </section>
      )}

      {/* Recent */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-3">
          Recent Captures
        </h2>
        {recent?.notes && recent.notes.length > 0 ? (
          <div className="space-y-2">
            {recent.notes.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">
            No notes yet. Use the capture bar above to add your first note.
          </p>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
}) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
      <div className="flex items-center gap-2 text-gray-400 mb-1">
        <Icon className="w-4 h-4" />
        <span className="text-xs">{label}</span>
      </div>
      <span className="text-2xl font-bold text-white">{value}</span>
    </div>
  );
}
