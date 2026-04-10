import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Loader2 } from "lucide-react";
import { captureNote, captureUrl } from "../lib/api";

export default function CaptureBar() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // Ctrl+K / Cmd+K to focus
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    setLoading(true);
    setMessage("");

    try {
      const isUrl = /^https?:\/\//i.test(input.trim());
      if (isUrl) {
        await captureUrl(input.trim());
      } else {
        await captureNote(input.trim());
      }
      setInput("");
      setMessage("Captured!");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      setTimeout(() => setMessage(""), 2000);
    } catch (err) {
      setMessage("Failed to capture");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-2 px-4 py-3 bg-gray-900 border-b border-gray-800"
    >
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type or paste anything... (Ctrl+K)"
        className="flex-1 bg-gray-800 text-white px-4 py-2 rounded-lg border border-gray-700 focus:outline-none focus:border-indigo-500 placeholder-gray-500 text-sm"
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Send className="w-4 h-4" />
        )}
        Capture
      </button>
      {message && (
        <span className="text-sm text-emerald-400 animate-pulse">
          {message}
        </span>
      )}
    </form>
  );
}
