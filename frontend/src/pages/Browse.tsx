import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getNotes, getConcepts, getEntities } from "../lib/api";
import NoteCard from "../components/NoteCard";
import { Link } from "react-router-dom";
import { BookOpen, Lightbulb, Users, ChevronRight } from "lucide-react";

type Tab = "notes" | "concepts" | "entities";

export default function Browse() {
  const [tab, setTab] = useState<Tab>("notes");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(0);
  const [entityType, setEntityType] = useState("");
  const limit = 20;

  const { data } = useQuery({
    queryKey: ["notes", "browse", sort, page],
    queryFn: () => getNotes({ sort, limit, offset: page * limit }),
    enabled: tab === "notes",
  });

  const { data: concepts } = useQuery({
    queryKey: ["concepts"],
    queryFn: getConcepts,
  });

  const { data: entities } = useQuery({
    queryKey: ["entities", entityType],
    queryFn: () => getEntities(entityType || undefined),
    enabled: tab === "entities",
  });

  const tabs: { key: Tab; icon: typeof BookOpen; label: string }[] = [
    { key: "notes", icon: BookOpen, label: "Notes" },
    { key: "concepts", icon: Lightbulb, label: "Concepts" },
    { key: "entities", icon: Users, label: "Entities" },
  ];

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Browse</h1>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800 w-fit">
        {tabs.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs transition-colors ${
              tab === key
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {/* Notes tab */}
      {tab === "notes" && (
        <>
          <div className="flex gap-2">
            {["recent", "starred", "most_connected"].map((s) => (
              <button
                key={s}
                onClick={() => { setSort(s); setPage(0); }}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  sort === s
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-900 text-gray-400 hover:text-white border border-gray-700"
                }`}
              >
                {s.replace("_", " ")}
              </button>
            ))}
          </div>

          {data?.notes && data.notes.length > 0 ? (
            <div className="space-y-2">
              {data.notes.map((n) => <NoteCard key={n.id} note={n} />)}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No notes found.</p>
          )}

          {data && data.total > limit && (
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 bg-gray-900 text-gray-400 rounded-lg text-xs disabled:opacity-50 border border-gray-700"
              >
                Previous
              </button>
              <span className="text-xs text-gray-500">
                Page {page + 1} of {Math.ceil(data.total / limit)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * limit >= data.total}
                className="px-3 py-1.5 bg-gray-900 text-gray-400 rounded-lg text-xs disabled:opacity-50 border border-gray-700"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Concepts tab — taxonomy tree */}
      {tab === "concepts" && concepts?.concepts && (
        <div className="space-y-4">
          {/* Top-level concepts (no parent) */}
          {(() => {
            const topLevel = concepts.concepts.filter(
              (c) => !concepts.concepts.some((p) => p.id === (c as any).parent_id)
            );
            const withChildren = concepts.concepts.reduce<Record<string, typeof concepts.concepts>>((acc, c) => {
              const pid = (c as any).parent_id;
              if (pid) {
                if (!acc[pid]) acc[pid] = [];
                acc[pid].push(c);
              }
              return acc;
            }, {});

            return topLevel.length > 0 ? (
              <div className="space-y-1">
                {topLevel.map((c) => (
                  <ConceptTreeNode
                    key={c.id}
                    concept={c}
                    children={withChildren[c.id] || []}
                    allChildren={withChildren}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {concepts.concepts.map((c) => (
                  <Link
                    key={c.id}
                    to={`/concepts/${c.id}`}
                    className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg hover:border-indigo-500 transition-colors"
                  >
                    <span className="text-sm text-white">{c.name}</span>
                    <span className="text-xs text-gray-600 ml-2">{c.note_count}</span>
                  </Link>
                ))}
              </div>
            );
          })()}
        </div>
      )}

      {/* Entities tab */}
      {tab === "entities" && (
        <>
          <div className="flex gap-2 flex-wrap">
            {["", "person", "company", "project", "tool", "book", "place", "event"].map((t) => (
              <button
                key={t}
                onClick={() => setEntityType(t)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  entityType === t
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-900 text-gray-400 hover:text-white border border-gray-700"
                }`}
              >
                {t || "all"}
              </button>
            ))}
          </div>

          {entities?.entities && entities.entities.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {entities.entities.map((e) => (
                <Link
                  key={e.id}
                  to={`/entities/${e.id}`}
                  className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-gray-600 transition-colors"
                >
                  <div className="flex-1">
                    <span className="text-sm text-white">{e.name}</span>
                    <span className="text-xs text-gray-600 ml-2">{e.entity_type}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-700" />
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No entities found.</p>
          )}
        </>
      )}
    </div>
  );
}

function ConceptTreeNode({
  concept,
  children,
  allChildren,
  depth = 0,
}: {
  concept: { id: string; name: string; note_count: number };
  children: { id: string; name: string; note_count: number }[];
  allChildren: Record<string, { id: string; name: string; note_count: number }[]>;
  depth?: number;
}) {
  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <Link
        to={`/concepts/${concept.id}`}
        className="flex items-center gap-2 py-1.5 px-3 rounded-lg hover:bg-gray-800 transition-colors group"
      >
        {children.length > 0 && (
          <ChevronRight className="w-3 h-3 text-gray-600 group-hover:text-gray-400" />
        )}
        <span className="text-sm text-gray-300 group-hover:text-white">
          {concept.name}
        </span>
        <span className="text-xs text-gray-600">{concept.note_count}</span>
      </Link>
      {children.map((child) => (
        <ConceptTreeNode
          key={child.id}
          concept={child}
          children={allChildren[child.id] || []}
          allChildren={allChildren}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}
