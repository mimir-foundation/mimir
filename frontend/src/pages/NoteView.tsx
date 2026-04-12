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
    return <div className="text-gray-500">Loading...</div>;
  }
  if (!note) {
    return <div className="text-gray-500">Note not found</div>;
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
    related: "bg-blue-900/40 text-blue-300",
    builds_on: "bg-emerald-900/40 text-emerald-300",
    contradicts: "bg-red-900/40 text-red-300",
    supports: "bg-teal-900/40 text-teal-300",
    inspired_by: "bg-purple-900/40 text-purple-300",
  };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-800 rounded-lg text-gray-400"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h1 className="text-xl font-bold text-white flex-1 truncate">
          {note.title || "Untitled"}
        </h1>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleStar}
            className="p-2 hover:bg-gray-800 rounded-lg"
          >
            <Star
              className={`w-4 h-4 ${
                note.is_starred
                  ? "text-amber-400 fill-amber-400"
                  : "text-gray-500"
              }`}
            />
          </button>
          <button
            onClick={toggleArchive}
            className="p-2 hover:bg-gray-800 rounded-lg text-gray-500"
          >
            <Archive className="w-4 h-4" />
          </button>
          <button
            onClick={handleDelete}
            className="p-2 hover:bg-gray-800 rounded-lg text-gray-500 hover:text-red-400"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
        </span>
        {note.word_count && (
          <span className="flex items-center gap-1">
            <BookOpen className="w-3 h-3" />
            {note.word_count} words
          </span>
        )}
        <span className="px-2 py-0.5 bg-gray-800 rounded text-gray-400">
          {note.source_type}
        </span>
        {note.source_uri && (
          <a
            href={note.source_uri}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300"
          >
            <ExternalLink className="w-3 h-3" /> Source
          </a>
        )}
      </div>

      {/* Synthesis */}
      {note.synthesis && (
        <div className="bg-indigo-950/30 border border-indigo-900/50 rounded-lg p-4">
          <p className="text-sm text-indigo-200">{note.synthesis}</p>
        </div>
      )}

      {/* Concepts & Entities */}
      <div className="flex flex-wrap gap-2">
        {note.concepts?.map((c: any) => (
          <span
            key={c.id || c.name}
            className="px-2 py-1 bg-indigo-900/40 text-indigo-300 rounded text-xs"
          >
            {c.name || c}
          </span>
        ))}
        {note.entities?.map((e) => (
          <span
            key={e.id}
            className="px-2 py-1 bg-gray-800 text-gray-300 rounded text-xs"
          >
            {e.name}
            <span className="text-gray-600 ml-1">{e.entity_type}</span>
          </span>
        ))}
      </div>

      {/* Content */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-6 prose prose-invert prose-sm max-w-none">
        <ReactMarkdown>
          {note.processed_content || note.raw_content}
        </ReactMarkdown>
      </div>

      {/* Actions */}
      {(note as any).actions && (note as any).actions.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
            <CalendarPlus className="w-4 h-4" /> Actions
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
                pending: "text-blue-400",
                pending_confirmation: "text-amber-400",
                failed: "text-red-400",
                skipped: "text-gray-500",
              };
              return (
                <div
                  key={a.id}
                  className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3"
                >
                  <Icon className={`w-4 h-4 ${statusColors[a.status] || "text-gray-400"}`} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-white">{payload.title || a.action_type}</span>
                    {payload.start && (
                      <span className="text-xs text-gray-500 ml-2">{payload.start}</span>
                    )}
                    {payload.location && (
                      <span className="text-xs text-gray-500 ml-2">{payload.location}</span>
                    )}
                    {payload.recurring && (
                      <span className="text-xs text-amber-400 ml-2">Recurring: {payload.recurring}</span>
                    )}
                  </div>
                  <span className={`text-xs ${statusColors[a.status] || "text-gray-500"}`}>
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
          <h2 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
            <Link2 className="w-4 h-4" /> Connections
          </h2>
          <div className="space-y-2">
            {note.connections.map((c) => (
              <Link
                key={c.id}
                to={`/notes/${c.target_note_id}`}
                className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-gray-600 transition-colors"
              >
                <span
                  className={`px-2 py-0.5 rounded text-xs ${
                    connectionTypeColors[c.connection_type] ||
                    "bg-gray-800 text-gray-400"
                  }`}
                >
                  {c.connection_type}
                </span>
                <span className="text-sm text-white flex-1 truncate">
                  {c.target_title || "Untitled"}
                </span>
                <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{ width: `${c.strength * 100}%` }}
                  />
                </div>
                {c.explanation && (
                  <span className="text-xs text-gray-500 max-w-48 truncate">
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
