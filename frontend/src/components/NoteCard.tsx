import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { Star, Globe, FileText, Clipboard, MessageSquare, Highlighter } from "lucide-react";
import { updateNote, type Note } from "../lib/api";
import { useQueryClient } from "@tanstack/react-query";

const SOURCE_ICONS: Record<string, typeof Globe> = {
  url: Globe,
  file: FileText,
  clipboard: Clipboard,
  manual: MessageSquare,
  highlight: Highlighter,
};

export default function NoteCard({ note }: { note: Note }) {
  const queryClient = useQueryClient();
  const Icon = SOURCE_ICONS[note.source_type] || MessageSquare;

  const title =
    note.title || note.raw_content?.slice(0, 80) || "Untitled";
  const preview = note.synthesis || note.processed_content?.slice(0, 160) || note.raw_content?.slice(0, 160) || "";

  async function toggleStar(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    await updateNote(note.id, { is_starred: !note.is_starred });
    queryClient.invalidateQueries({ queryKey: ["notes"] });
  }

  const statusColor =
    note.processing_status === "complete"
      ? "text-emerald-400"
      : note.processing_status === "error"
        ? "text-red-400"
        : "text-amber-400";

  return (
    <Link
      to={`/notes/${note.id}`}
      className="block bg-gray-900 rounded-lg border border-gray-800 p-4 hover:border-gray-600 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-4 h-4 text-gray-500 shrink-0" />
          <h3 className="font-medium text-white truncate text-sm">{title}</h3>
        </div>
        <button
          onClick={toggleStar}
          className="shrink-0 p-1 hover:bg-gray-800 rounded"
        >
          <Star
            className={`w-4 h-4 ${
              note.is_starred
                ? "text-amber-400 fill-amber-400"
                : "text-gray-600"
            }`}
          />
        </button>
      </div>

      {preview && (
        <p className="mt-1 text-gray-400 text-xs line-clamp-2">{preview}</p>
      )}

      <div className="mt-2 flex items-center gap-2 flex-wrap">
        {note.concepts?.slice(0, 3).map((c) => (
          <span
            key={c}
            className="px-2 py-0.5 bg-indigo-900/40 text-indigo-300 rounded text-xs"
          >
            {c}
          </span>
        ))}
        <span className="ml-auto text-xs text-gray-600">
          {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
        </span>
        {note.processing_status !== "complete" && (
          <span className={`text-xs ${statusColor}`}>
            {note.processing_status}
          </span>
        )}
      </div>
    </Link>
  );
}
