import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getEntity } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, User, Building2, Briefcase, MapPin, BookOpen, Wrench, Calendar } from "lucide-react";

const TYPE_ICONS: Record<string, typeof User> = {
  person: User,
  company: Building2,
  project: Briefcase,
  place: MapPin,
  book: BookOpen,
  tool: Wrench,
  event: Calendar,
};

export default function EntityPage() {
  const { entityId } = useParams<{ entityId: string }>();
  const { data: entity, isLoading } = useQuery({
    queryKey: ["entity", entityId],
    queryFn: () => getEntity(entityId!),
    enabled: !!entityId,
  });

  if (isLoading) return <div className="text-gray-500">Loading...</div>;
  if (!entity) return <div className="text-gray-500">Entity not found</div>;

  const Icon = TYPE_ICONS[entity.entity_type] || User;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/browse" className="p-2 hover:bg-gray-800 rounded-lg text-gray-400">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <Icon className="w-6 h-6 text-indigo-400" />
        <div>
          <h1 className="text-xl font-bold text-white">{entity.name}</h1>
          <span className="text-xs text-gray-500">{entity.entity_type} · {entity.note_count} notes</span>
        </div>
      </div>

      {entity.description && (
        <p className="text-sm text-gray-400">{entity.description}</p>
      )}

      {/* Associated concepts */}
      {entity.concepts.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {entity.concepts.map((c) => (
            <Link
              key={c.id}
              to={`/concepts/${c.id}`}
              className="px-2 py-1 bg-indigo-900/40 text-indigo-300 rounded text-xs hover:bg-indigo-900/60"
            >
              {c.name} <span className="text-indigo-500">{c.note_count}</span>
            </Link>
          ))}
        </div>
      )}

      {/* Co-occurring entities */}
      {entity.co_entities.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-2">Often appears with</h2>
          <div className="flex flex-wrap gap-2">
            {entity.co_entities.map((e) => (
              <Link
                key={e.id}
                to={`/entities/${e.id}`}
                className="px-2 py-1 bg-gray-800 text-gray-300 rounded text-xs hover:bg-gray-700"
              >
                {e.name} <span className="text-gray-600">{e.entity_type}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Notes */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">Notes ({entity.notes.length})</h2>
        <div className="space-y-2">
          {entity.notes.map((n) => (
            <Link
              key={n.id}
              to={`/notes/${n.id}`}
              className="block bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors"
            >
              <h3 className="text-sm font-medium text-white">{n.title || "Untitled"}</h3>
              {n.synthesis && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{n.synthesis}</p>}
              {n.context && <p className="text-xs text-gray-500 mt-1 italic">"{n.context}"</p>}
              <span className="text-xs text-gray-600 mt-2 block">
                {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
