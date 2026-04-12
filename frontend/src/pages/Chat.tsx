import { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { askQuestion, askWithContext, type AskResponse } from "../lib/api";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: AskResponse["sources"];
}

export default function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // Send last 4 messages as conversation context for multi-turn chat
      const history = messages.slice(-4).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const result = history.length > 0
        ? await askWithContext(q, history)
        : await askQuestion(q);
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.answer,
        sources: result.sources,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Sorry, something went wrong. Try again.",
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <h1 className="text-xl font-bold text-white mb-4 flex items-center gap-3">
        <img src="/logo.png" alt="" className="w-7 h-7" />
        Chat with Mimir
      </h1>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center py-20">
            <img src="/logo.png" alt="Mimir" className="w-16 h-16 mx-auto mb-4 opacity-20" />
            <p className="text-zinc-500 text-sm">
              Ask anything about your knowledge base.
            </p>
            <p className="text-zinc-600 text-xs mt-1">
              Mimir answers using only your captured notes.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-brand-600 text-white"
                  : "bg-surface-2 border border-border-subtle text-zinc-200"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-[13px]">{msg.content}</p>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-zinc-700/50">
                  <p className="text-[11px] text-zinc-500 mb-1.5 font-medium">Sources</p>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.sources.map((s) => (
                      <Link
                        key={s.note_id}
                        to={`/notes/${s.note_id}`}
                        className="text-[11px] px-2 py-0.5 bg-surface-3 text-brand-400 hover:text-brand-300 rounded-md border border-border-subtle hover:border-brand-500/30 transition-colors"
                      >
                        {s.title}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-2 border border-border-subtle rounded-2xl px-4 py-3">
              <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 bg-surface-2 border border-border-subtle rounded-xl p-2"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your second brain..."
          className="flex-1 bg-transparent text-white px-3 py-2 text-[13px] focus:outline-none placeholder-zinc-500"
          autoFocus
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="p-2.5 bg-brand-500 hover:bg-brand-400 disabled:opacity-30 text-white rounded-lg transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowUp className="w-4 h-4" />
          )}
        </button>
      </form>
    </div>
  );
}
