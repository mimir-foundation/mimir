import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search as SearchIcon, Loader2, MessageCircle, Sparkles } from "lucide-react";
import { searchNotes, getConcepts, askQuestion, type SearchResult } from "../lib/api";
import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";

export default function Search() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [mode, setMode] = useState<"search" | "ask">("search");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: concepts } = useQuery({
    queryKey: ["concepts"],
    queryFn: getConcepts,
  });

  const {
    data: results,
    isLoading,
    isFetching,
  } = useQuery({
    queryKey: ["search", debouncedQuery, sourceType],
    queryFn: () =>
      searchNotes(debouncedQuery, {
        source_type: sourceType || undefined,
      }),
    enabled: debouncedQuery.length > 1 && mode === "search",
  });

  const {
    data: askResult,
    isFetching: askFetching,
  } = useQuery({
    queryKey: ["ask", debouncedQuery],
    queryFn: () => askQuestion(debouncedQuery),
    enabled: debouncedQuery.length > 2 && mode === "ask",
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Search</h1>

      {/* Search input */}
      <div className="relative">
        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your knowledge base..."
          className="w-full bg-surface-2 text-white pl-12 pr-4 py-3.5 rounded-xl border border-border-subtle focus:outline-none focus:border-brand-500/50 text-[13px] transition-colors"
          autoFocus
        />
        {(isFetching || askFetching) && (
          <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 animate-spin" />
        )}
      </div>

      {/* Mode toggle + Filters */}
      <div className="flex gap-2 flex-wrap items-center">
        <div className="flex bg-surface-2 border border-border-subtle rounded-lg overflow-hidden">
          <button
            onClick={() => setMode("search")}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              mode === "search"
                ? "bg-brand-500 text-white"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Search
          </button>
          <button
            onClick={() => setMode("ask")}
            className={`px-4 py-2 text-xs font-medium flex items-center gap-1.5 transition-colors ${
              mode === "ask"
                ? "bg-brand-500 text-white"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-3 h-3" /> Ask AI
          </button>
        </div>
        {mode === "search" && (
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="bg-surface-2 text-zinc-300 border border-border-subtle rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-brand-500/50"
          >
            <option value="">All sources</option>
            <option value="manual">Manual</option>
            <option value="url">URL</option>
            <option value="file">File</option>
            <option value="clipboard">Clipboard</option>
            <option value="highlight">Highlight</option>
          </select>
        )}
      </div>

      {/* Ask result */}
      {mode === "ask" && askResult && (
        <div className="space-y-4">
          <div className="bg-gradient-to-br from-brand-950/40 to-surface-2 border border-brand-900/30 rounded-2xl p-6">
            <p className="text-[13px] text-zinc-200 whitespace-pre-line leading-relaxed">
              {askResult.answer}
            </p>
          </div>
          {askResult.sources.length > 0 && (
            <div>
              <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider mb-2">Sources</p>
              <div className="space-y-1.5">
                {askResult.sources.map((s) => (
                  <Link
                    key={s.note_id}
                    to={`/notes/${s.note_id}`}
                    className="flex items-center justify-between bg-surface-2 rounded-xl px-4 py-2.5 border border-border-subtle hover:border-brand-500/30 text-xs transition-colors"
                  >
                    <span className="text-zinc-300">{s.title}</span>
                    <span className="text-zinc-600 tabular-nums">{s.score.toFixed(4)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Search Results */}
      {mode === "search" && results?.results && results.results.length > 0 ? (
        <div className="space-y-3">
          <p className="text-[11px] text-zinc-500 font-medium">
            {results.total} result{results.total !== 1 ? "s" : ""}
          </p>
          {results.results.map((r) => (
            <SearchResultCard key={r.note_id} result={r} />
          ))}
        </div>
      ) : mode === "search" && debouncedQuery.length > 1 && !isLoading ? (
        <p className="text-zinc-500 text-sm">No results found.</p>
      ) : null}

      {/* Concept cloud when idle */}
      {!debouncedQuery && concepts?.concepts && concepts.concepts.length > 0 && (
        <section>
          <h2 className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider mb-3">
            Explore concepts
          </h2>
          <div className="flex flex-wrap gap-2">
            {concepts.concepts.slice(0, 30).map((c) => (
              <button
                key={c.id}
                onClick={() => setQuery(c.name)}
                className="px-3 py-1.5 bg-surface-2 border border-border-subtle text-zinc-300 rounded-full text-xs hover:border-brand-500/40 hover:text-brand-400 transition-colors"
              >
                {c.name}{" "}
                <span className="text-zinc-600">{c.note_count}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <Link
      to={`/notes/${result.note_id}`}
      className="group block bg-surface-2 rounded-xl border border-border-subtle p-4 hover:border-brand-500/30 transition-all duration-150"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-medium text-white text-[13px]">
          {result.title || "Untitled"}
        </h3>
        <span className="text-[11px] text-zinc-600 shrink-0 tabular-nums bg-surface-3 px-2 py-0.5 rounded-md">
          {result.score.toFixed(3)}
        </span>
      </div>
      {result.synthesis && (
        <p className="mt-1.5 text-zinc-500 text-xs line-clamp-2 leading-relaxed">
          {result.synthesis}
        </p>
      )}
      {result.highlights && (
        <p
          className="mt-1 text-zinc-600 text-xs line-clamp-1"
          dangerouslySetInnerHTML={{ __html: result.highlights }}
        />
      )}
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        {result.concepts?.slice(0, 3).map((c) => (
          <span
            key={c}
            className="px-2 py-0.5 bg-brand-500/10 text-brand-400 rounded-md text-[11px] font-medium"
          >
            {c}
          </span>
        ))}
        <span className="ml-auto text-[11px] text-zinc-600">
          {result.created_at &&
            formatDistanceToNow(new Date(result.created_at), {
              addSuffix: true,
            })}
        </span>
      </div>
    </Link>
  );
}
