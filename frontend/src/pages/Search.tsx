import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search as SearchIcon, Loader2, MessageCircle } from "lucide-react";
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
    isLoading: askLoading,
    isFetching: askFetching,
  } = useQuery({
    queryKey: ["ask", debouncedQuery],
    queryFn: () => askQuestion(debouncedQuery),
    enabled: debouncedQuery.length > 2 && mode === "ask",
  });

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-white">Search</h1>

      {/* Search input */}
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your knowledge base..."
          className="w-full bg-gray-900 text-white pl-10 pr-4 py-3 rounded-lg border border-gray-700 focus:outline-none focus:border-indigo-500 text-sm"
          autoFocus
        />
        {(isFetching || askFetching) && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 animate-spin" />
        )}
      </div>

      {/* Mode toggle + Filters */}
      <div className="flex gap-2 flex-wrap items-center">
        <div className="flex bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
          <button
            onClick={() => setMode("search")}
            className={`px-3 py-1.5 text-xs transition-colors ${mode === "search" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}
          >
            Search
          </button>
          <button
            onClick={() => setMode("ask")}
            className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-colors ${mode === "ask" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}
          >
            <MessageCircle className="w-3 h-3" /> Ask
          </button>
        </div>
        {mode === "search" && (
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="bg-gray-900 text-gray-300 border border-gray-700 rounded-lg px-3 py-1.5 text-xs"
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
          <div className="bg-indigo-950/30 border border-indigo-900/50 rounded-lg p-5">
            <p className="text-sm text-gray-200 whitespace-pre-line leading-relaxed">
              {askResult.answer}
            </p>
          </div>
          {askResult.sources.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">Sources</p>
              <div className="space-y-1">
                {askResult.sources.map((s) => (
                  <Link
                    key={s.note_id}
                    to={`/notes/${s.note_id}`}
                    className="flex items-center justify-between bg-gray-900 rounded-lg px-3 py-2 border border-gray-800 hover:border-gray-600 text-xs"
                  >
                    <span className="text-gray-300">{s.title}</span>
                    <span className="text-gray-600">{s.score.toFixed(4)}</span>
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
          <p className="text-xs text-gray-500">
            {results.total} result{results.total !== 1 ? "s" : ""}
          </p>
          {results.results.map((r) => (
            <SearchResultCard key={r.note_id} result={r} />
          ))}
        </div>
      ) : mode === "search" && debouncedQuery.length > 1 && !isLoading ? (
        <p className="text-gray-500 text-sm">No results found.</p>
      ) : null}

      {/* Concept cloud when idle */}
      {!debouncedQuery && concepts?.concepts && concepts.concepts.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">
            Concepts in your knowledge base
          </h2>
          <div className="flex flex-wrap gap-2">
            {concepts.concepts.slice(0, 30).map((c) => (
              <button
                key={c.id}
                onClick={() => setQuery(c.name)}
                className="px-3 py-1 bg-gray-900 border border-gray-700 text-gray-300 rounded-full text-xs hover:border-indigo-500 hover:text-indigo-300 transition-colors"
              >
                {c.name}{" "}
                <span className="text-gray-600">{c.note_count}</span>
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
      className="block bg-gray-900 rounded-lg border border-gray-800 p-4 hover:border-gray-600 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium text-white text-sm">
          {result.title || "Untitled"}
        </h3>
        <span className="text-xs text-gray-600 shrink-0">
          {result.score.toFixed(4)}
        </span>
      </div>
      {result.synthesis && (
        <p className="mt-1 text-gray-400 text-xs line-clamp-2">
          {result.synthesis}
        </p>
      )}
      {result.highlights && (
        <p
          className="mt-1 text-gray-500 text-xs line-clamp-1"
          dangerouslySetInnerHTML={{ __html: result.highlights }}
        />
      )}
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        {result.concepts?.slice(0, 3).map((c) => (
          <span
            key={c}
            className="px-2 py-0.5 bg-indigo-900/40 text-indigo-300 rounded text-xs"
          >
            {c}
          </span>
        ))}
        <span className="ml-auto text-xs text-gray-600">
          {result.created_at &&
            formatDistanceToNow(new Date(result.created_at), {
              addSuffix: true,
            })}
        </span>
      </div>
    </Link>
  );
}
