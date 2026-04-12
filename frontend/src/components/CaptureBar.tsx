import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Loader2, Paperclip, X } from "lucide-react";
import { captureNote, captureUrl } from "../lib/api";

export default function CaptureBar() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
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
    if ((!input.trim() && !file) || loading) return;

    setLoading(true);
    setMessage("");

    try {
      if (file) {
        // File upload
        const formData = new FormData();
        formData.append("file", file);
        if (input.trim()) formData.append("title", input.trim());

        const res = await fetch("/api/capture/file", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error("Upload failed");
        setFile(null);
      } else {
        const isUrl = /^https?:\/\//i.test(input.trim());
        if (isUrl) {
          await captureUrl(input.trim());
        } else {
          await captureNote(input.trim());
        }
      }
      setInput("");
      setMessage("Captured!");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      setTimeout(() => setMessage(""), 2000);
    } catch {
      setMessage("Failed to capture");
    } finally {
      setLoading(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
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
        placeholder={file ? `Title for ${file.name} (optional)` : "Type or paste anything... (Ctrl+K)"}
        className="flex-1 bg-gray-800 text-white px-4 py-2 rounded-lg border border-gray-700 focus:outline-none focus:border-indigo-500 placeholder-gray-500 text-sm"
      />

      {/* File attachment */}
      <input
        ref={fileRef}
        type="file"
        onChange={handleFileSelect}
        className="hidden"
        accept="image/*,audio/*,.pdf,.txt,.md,.csv,.json,.xml,.html,.docx"
      />
      {file ? (
        <button
          type="button"
          onClick={() => setFile(null)}
          className="flex items-center gap-1 px-3 py-2 bg-indigo-900/50 text-indigo-300 rounded-lg text-xs border border-indigo-700 hover:border-indigo-500 transition-colors"
        >
          {file.name.length > 20 ? file.name.slice(0, 17) + "..." : file.name}
          <X className="w-3 h-3" />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="p-2 text-gray-500 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
          title="Attach file"
        >
          <Paperclip className="w-4 h-4" />
        </button>
      )}

      <button
        type="submit"
        disabled={loading || (!input.trim() && !file)}
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
