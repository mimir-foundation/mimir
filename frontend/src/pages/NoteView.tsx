import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getNote, updateNote, deleteNote } from "../lib/api";
import ReactMarkdown from "react-markdown";
import { formatDistanceToNow } from "date-fns";
import {
  Star,
  Archive,
  Trash2,
  ExternalLink,
  ArrowLeft,
  Link2,
  Clock,
  BookOpen,
  CalendarPlus,
  Bell,
  CheckSquare,
  UserPlus,
  RotateCcw,
  Loader2,
} from "lucide-react";

export default function NoteView() {
  const { noteId } = useParams<{ noteId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: note, isLoading } = useQuery({
    queryKey: ["note", noteId],
    queryFn: () => getNote(noteId!),
    enabled: !!noteId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
      </div>
    );
  }
  if (!note) {
    return <div className="text-zinc-500 py-20 text-center">Note not found</div>;
  }

  async function toggleStar() {
    await updateNote(noteId!, { is_starred: !note!.is_starred });
    queryClient.invalidateQueries({ queryKey: ["note", noteId] });
  }

  async function toggleArchive() {
    await updateNote(noteId!, { is_archived: !note!.is_archived });
    queryClient.invalidateQueries({ queryKey: ["note", noteId] });
  }

  async function handleDelete() {
    if (!confirm("Delete this note permanently?")) return;
    await deleteNote(noteId!);
    navigate("/");
  }

  const connectionTypeColors: Record<string, string> = {
    related: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    builds_on: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    contradicts: "bg-red-500/10 text-red-400 border-red-500/20",
    supports: "bg-teal-500/10 text-teal-400 border-teal-500/20",
    inspired_by: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-surface-3 rounded-lg text-zinc-400 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h1 className="text-lg font-bold text-white flex-1 truncate">
          {note.title || "Untitled"}
        </h1>
        <div className="flex items-center gap-0.5">
          <button
            onClick={toggleStar}
            className="p-2 hover:bg-surface-3 rounded-lg transition-colors"
          >
            <Star
              className={`w-4 h-4 ${
                note.is_starred
                  ? "text-amber-400 fill-amber-400"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            />
          </button>
          <button
            onClick={toggleArchive}
            className="p-2 hover:bg-surface-3 rounded-lg text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <Archive className="w-4 h-4" />
          </button>
          <button
            onClick={handleDelete}
            className="p-2 hover:bg-surface-3 rounded-lg text-zinc-500 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-zinc-500 flex-wrap">
        <span className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" />
          {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
        </span>
        {note.word_count && (
          <span className="flex items-center gap-1.5">
            <BookOpen className="w-3 h-3" />
            {note.word_count} words
          </span>
        )}
        <span className="px-2 py-0.5 bg-surface-3 rounded-md text-zinc-400 border border-border-subtle text-[11px]">
          {note.source_type}
        </span>
        {note.source_uri && (
          <a
            href={note.source_uri}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-brand-400 hover:text-brand-300 transition-colors"
          >
            <ExternalLink className="w-3 h-3" /> Source
          </a>
        )}
      </div>

      {/* Synthesis */}
      {note.synthesis && (
        <div className="bg-gradient-to-br from-brand-950/40 to-surface-2 border border-brand-900/30 rounded-2xl p-5">
          <p className="text-[13px] text-brand-200 leading-relaxed">{note.synthesis}</p>
        </div>
      )}

      {/* Concepts & Entities */}
      {((note.concepts && note.concepts.length > 0) || (note.entities && note.entities.length > 0)) && (
        <div className="flex flex-wrap gap-2">
          {note.concepts?.map((c: any) => (
            <Link
              key={c.id || c.name}
              to={c.id ? `/concepts/${c.id}` : "#"}
              className="px-2.5 py-1 bg-brand-500/10 text-brand-400 rounded-lg text-[11px] font-medium border border-brand-500/10 hover:border-brand-500/30 transition-colors"
            >
              {c.name || c}
            </Link>
          ))}
          {note.entities?.map((e) => (
            <Link
              key={e.id}
              to={`/entities/${e.id}`}
              className="px-2.5 py-1 bg-surface-3 text-zinc-300 rounded-lg text-[11px] font-medium border border-border-subtle hover:border-border-hover transition-colors"
            >
              {e.name}
              <span className="text-zinc-600 ml-1">{e.entity_type}</span>
            </Link>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="bg-surface-2 rounded-2xl border border-border-subtle p-6 prose prose-invert prose-sm max-w-none">
        <ReactMarkdown>
          {note.processed_content || note.raw_content}
        </ReactMarkdown>
      </div>

      {/* Actions */}
      {(note as any).actions && (note as any).actions.length > 0 && (
        <section>
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <CalendarPlus className="w-3.5 h-3.5" /> Actions
          </h2>
          <div className="space-y-2">
            {(note as any).actions.map((a: any) => {
              const payload = typeof a.payload === "string" ? JSON.parse(a.payload) : a.payload;
              const icons: Record<string, typeof CalendarPlus> = {
                calendar_event: CalendarPlus,
                reminder: Bell,
                task: CheckSquare,
                contact: UserPlus,
                follow_up: RotateCcw,
              };
              const Icon = icons[a.action_type] || CalendarPlus;
              const statusColors: Record<string, string> = {
                dispatched: "text-emerald-400",
                pending: "text-brand-400",
                pending_confirmation: "text-amber-400",
                failed: "text-red-400",
                skipped: "text-zinc-500",
              };
              return (
                <div
                  key={a.id}
                  className="flex items-center gap-3 bg-surface-2 border border-border-subtle rounded-xl p-3.5"
                >
                  <Icon className={`w-4 h-4 ${statusColors[a.status] || "text-zinc-400"}`} />
                  <div className="flex-1 min-w-0">
                    <span className="text-[13px] text-white">{payload.title || a.action_type}</span>
                    {payload.start && (
                      <span className="text-xs text-zinc-500 ml-2">{payload.start}</span>
                    )}
                  </div>
                  <span className={`text-[11px] ${statusColors[a.status] || "text-zinc-500"}`}>
                    {a.status.replace("_", " ")}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Connections */}
      {note.connections && note.connections.length > 0 && (
        <section>
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Link2 className="w-3.5 h-3.5" /> Connections ({note.connections.length})
          </h2>
          <div className="space-y-2">
            {note.connections.map((c) => (
              <Link
                key={c.id}
                to={`/notes/${c.target_note_id}`}
                className="flex items-center gap-3 bg-surface-2 border border-border-subtle rounded-xl p-3.5 hover:border-brand-500/30 transition-colors group"
              >
                <span
                  className={`px-2 py-0.5 rounded-md text-[11px] font-medium border ${
                    connectionTypeColors[c.connection_type] ||
                    "bg-surface-3 text-zinc-400 border-border-subtle"
                  }`}
                >
                  {c.connection_type}
                </span>
                <span className="text-[13px] text-white flex-1 truncate">
                  {c.target_title || "Untitled"}
                </span>
                <div className="w-16 h-1.5 bg-surface-4 rounded-full overflow-hidden shrink-0">
                  <div
                    className="h-full bg-brand-500 rounded-full"
                    style={{ width: `${c.strength * 100}%` }}
                  />
                </div>
                {c.explanation && (
                  <span className="text-[11px] text-zinc-500 max-w-48 truncate hidden sm:block">
                    {c.explanation}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
