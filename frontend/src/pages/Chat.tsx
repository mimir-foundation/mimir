import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Brain } from "lucide-react";
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
    <div className="flex flex-col h-full max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
        <Brain className="w-6 h-6 text-indigo-400" /> Chat with Mimir
      </h1>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center py-20">
            <Brain className="w-12 h-12 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-500 text-sm">
              Ask anything about your knowledge base.
            </p>
            <p className="text-gray-600 text-xs mt-1">
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
              className={`max-w-[85%] rounded-lg px-4 py-3 ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-900 border border-gray-800 text-gray-200"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm">{msg.content}</p>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-700">
                  <p className="text-xs text-gray-500 mb-1">Sources</p>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.sources.map((s) => (
                      <Link
                        key={s.note_id}
                        to={`/notes/${s.note_id}`}
                        className="text-xs px-2 py-0.5 bg-gray-800 text-indigo-400 hover:text-indigo-300 rounded border border-gray-700 hover:border-gray-600 transition-colors"
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
            <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 bg-gray-900 border border-gray-800 rounded-lg p-2"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your second brain..."
          className="flex-1 bg-transparent text-white px-3 py-2 text-sm focus:outline-none placeholder-gray-500"
          autoFocus
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>
    </div>
  );
}
