import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getConcept } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, ChevronRight, Lightbulb, Loader2 } from "lucide-react";

export default function ConceptPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const { data: concept, isLoading } = useQuery({
    queryKey: ["concept", conceptId],
    queryFn: () => getConcept(conceptId!),
    enabled: !!conceptId,
  });

  if (isLoading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-5 h-5 text-zinc-500 animate-spin" /></div>;
  if (!concept) return <div className="text-zinc-500 py-20 text-center">Concept not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/browse" className="p-2 hover:bg-surface-3 rounded-lg text-zinc-400 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="p-2 bg-violet-500/10 rounded-xl">
          <Lightbulb className="w-5 h-5 text-violet-400" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            {concept.parents.map((p) => (
              <span key={p.id} className="flex items-center gap-1">
                <Link to={`/concepts/${p.id}`} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                  {p.name}
                </Link>
                <ChevronRight className="w-3 h-3 text-zinc-700" />
              </span>
            ))}
          </div>
          <h1 className="text-lg font-bold text-white">{concept.name}</h1>
          <span className="text-xs text-zinc-500">{concept.note_count} notes</span>
        </div>
      </div>

      {concept.description && (
        <p className="text-[13px] text-zinc-400">{concept.description}</p>
      )}

      {concept.children.length > 0 && (
        <section>
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">Sub-concepts</h2>
          <div className="flex flex-wrap gap-2">
            {concept.children.map((c) => (
              <Link
                key={c.id}
                to={`/concepts/${c.id}`}
                className="px-3 py-1.5 bg-brand-500/10 text-brand-400 rounded-lg text-xs font-medium border border-brand-500/10 hover:border-brand-500/30 transition-colors"
              >
                {c.name} <span className="text-brand-600">{c.note_count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-3">Notes ({concept.notes.length})</h2>
        <div className="space-y-2">
          {concept.notes.map((n) => (
            <Link
              key={n.id}
              to={`/notes/${n.id}`}
              className="flex items-center gap-3 bg-surface-2 border border-border-subtle rounded-xl p-4 hover:border-brand-500/30 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <h3 className="text-[13px] font-medium text-white truncate">{n.title || "Untitled"}</h3>
                {n.synthesis && <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{n.synthesis}</p>}
              </div>
              <div className="text-right shrink-0">
                <span className="text-[11px] text-zinc-600">
                  {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                </span>
                <div className="w-14 h-1.5 bg-surface-4 rounded-full mt-1.5 overflow-hidden">
                  <div
                    className="h-full bg-brand-500 rounded-full"
                    style={{ width: `${n.relevance_score * 100}%` }}
                  />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
