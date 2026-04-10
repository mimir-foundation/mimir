import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getConcept } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, ChevronRight, Lightbulb } from "lucide-react";

export default function ConceptPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const { data: concept, isLoading } = useQuery({
    queryKey: ["concept", conceptId],
    queryFn: () => getConcept(conceptId!),
    enabled: !!conceptId,
  });

  if (isLoading) return <div className="text-gray-500">Loading...</div>;
  if (!concept) return <div className="text-gray-500">Concept not found</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/browse" className="p-2 hover:bg-gray-800 rounded-lg text-gray-400">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <Lightbulb className="w-5 h-5 text-indigo-400" />
        <div>
          <div className="flex items-center gap-2">
            {/* Breadcrumb parents */}
            {concept.parents.map((p) => (
              <span key={p.id} className="flex items-center gap-1">
                <Link to={`/concepts/${p.id}`} className="text-xs text-gray-500 hover:text-gray-300">
                  {p.name}
                </Link>
                <ChevronRight className="w-3 h-3 text-gray-700" />
              </span>
            ))}
          </div>
          <h1 className="text-xl font-bold text-white">{concept.name}</h1>
          <span className="text-xs text-gray-500">{concept.note_count} notes</span>
        </div>
      </div>

      {concept.description && (
        <p className="text-sm text-gray-400">{concept.description}</p>
      )}

      {/* Child concepts */}
      {concept.children.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-2">Sub-concepts</h2>
          <div className="flex flex-wrap gap-2">
            {concept.children.map((c) => (
              <Link
                key={c.id}
                to={`/concepts/${c.id}`}
                className="px-3 py-1.5 bg-indigo-900/30 text-indigo-300 rounded-lg text-xs hover:bg-indigo-900/50 transition-colors"
              >
                {c.name} <span className="text-indigo-500">{c.note_count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Notes */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">Notes ({concept.notes.length})</h2>
        <div className="space-y-2">
          {concept.notes.map((n) => (
            <Link
              key={n.id}
              to={`/notes/${n.id}`}
              className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-white truncate">{n.title || "Untitled"}</h3>
                {n.synthesis && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{n.synthesis}</p>}
              </div>
              <div className="text-right shrink-0">
                <span className="text-xs text-gray-600">
                  {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                </span>
                <div className="w-12 h-1 bg-gray-800 rounded-full mt-1 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
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
