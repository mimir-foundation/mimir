import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getEntity } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, User, Building2, Briefcase, MapPin, BookOpen, Wrench, Calendar, Loader2 } from "lucide-react";

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

  if (isLoading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-5 h-5 text-zinc-500 animate-spin" /></div>;
  if (!entity) return <div className="text-zinc-500 py-20 text-center">Entity not found</div>;

  const Icon = TYPE_ICONS[entity.entity_type] || User;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/browse" className="p-2 hover:bg-surface-3 rounded-lg text-zinc-400 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="p-2 bg-brand-500/10 rounded-xl">
          <Icon className="w-5 h-5 text-brand-400" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white">{entity.name}</h1>
          <span className="text-xs text-zinc-500">{entity.entity_type} · {entity.note_count} notes</span>
        </div>
      </div>

      {entity.description && (
        <p className="text-[13px] text-zinc-400">{entity.description}</p>
      )}

      {entity.concepts.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {entity.concepts.map((c) => (
            <Link
              key={c.id}
              to={`/concepts/${c.id}`}
              className="px-2.5 py-1 bg-brand-500/10 text-brand-400 rounded-lg text-[11px] font-medium border border-brand-500/10 hover:border-brand-500/30 transition-colors"
            >
              {c.name} <span className="text-brand-600">{c.note_count}</span>
            </Link>
          ))}
        </div>
      )}

      {entity.co_entities.length > 0 && (
        <section>
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">Often appears with</h2>
          <div className="flex flex-wrap gap-2">
            {entity.co_entities.map((e) => (
              <Link
                key={e.id}
                to={`/entities/${e.id}`}
                className="px-2.5 py-1 bg-surface-3 text-zinc-300 rounded-lg text-[11px] border border-border-subtle hover:border-border-hover transition-colors"
              >
                {e.name} <span className="text-zinc-600">{e.entity_type}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-3">Notes ({entity.notes.length})</h2>
        <div className="space-y-2">
          {entity.notes.map((n) => (
            <Link
              key={n.id}
              to={`/notes/${n.id}`}
              className="block bg-surface-2 border border-border-subtle rounded-xl p-4 hover:border-brand-500/30 transition-colors"
            >
              <h3 className="text-[13px] font-medium text-white">{n.title || "Untitled"}</h3>
              {n.synthesis && <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{n.synthesis}</p>}
              {n.context && <p className="text-xs text-zinc-600 mt-1 italic">"{n.context}"</p>}
              <span className="text-[11px] text-zinc-600 mt-2 block">
                {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
