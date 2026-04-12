import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import {
  Star,
  Globe,
  FileText,
  Clipboard,
  MessageSquare,
  Highlighter,
  Mail,
  Smartphone,
  Import,
} from "lucide-react";
import { updateNote, type Note } from "../lib/api";
import { useQueryClient } from "@tanstack/react-query";

const SOURCE_ICONS: Record<string, typeof Globe> = {
  url: Globe,
  file: FileText,
  clipboard: Clipboard,
  manual: MessageSquare,
  highlight: Highlighter,
  email: Mail,
  telegram: Smartphone,
  mattermost: MessageSquare,
  import: Import,
};

export default function NoteCard({ note }: { note: Note }) {
  const queryClient = useQueryClient();
  const Icon = SOURCE_ICONS[note.source_type] || MessageSquare;

  const title = note.title || note.raw_content?.slice(0, 80) || "Untitled";
  const preview =
    note.synthesis ||
    note.processed_content?.slice(0, 160) ||
    note.raw_content?.slice(0, 160) ||
    "";

  async function toggleStar(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    await updateNote(note.id, { is_starred: !note.is_starred });
    queryClient.invalidateQueries({ queryKey: ["notes"] });
  }

  const statusBadge =
    note.processing_status === "error"
      ? "bg-red-500/10 text-red-400 border-red-500/20"
      : note.processing_status === "pending" || note.processing_status === "processing"
        ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
        : null;

  return (
    <Link
      to={`/notes/${note.id}`}
      className="group block bg-surface-2 rounded-xl border border-border-subtle p-4 hover:border-brand-500/30 hover:bg-surface-3 transition-all duration-150"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="mt-0.5 p-1.5 bg-surface-3 rounded-lg shrink-0 group-hover:bg-surface-4 transition-colors">
            <Icon className="w-3.5 h-3.5 text-zinc-400" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-medium text-white text-[13px] truncate leading-snug">
              {title}
            </h3>
            {preview && (
              <p className="mt-1 text-zinc-500 text-xs line-clamp-2 leading-relaxed">
                {preview}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={toggleStar}
          className="shrink-0 p-1 rounded-md hover:bg-surface-4 transition-colors"
        >
          <Star
            className={`w-3.5 h-3.5 ${
              note.is_starred
                ? "text-amber-400 fill-amber-400"
                : "text-zinc-600 group-hover:text-zinc-500"
            }`}
          />
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        {note.concepts?.slice(0, 3).map((c) => (
          <span
            key={c}
            className="px-2 py-0.5 bg-brand-500/10 text-brand-400 rounded-md text-[11px] font-medium border border-brand-500/10"
          >
            {c}
          </span>
        ))}
        <div className="flex-1" />
        {statusBadge && (
          <span className={`text-[11px] px-2 py-0.5 rounded-md border ${statusBadge}`}>
            {note.processing_status}
          </span>
        )}
        <span className="text-[11px] text-zinc-600">
          {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
        </span>
      </div>
    </Link>
  );
}
