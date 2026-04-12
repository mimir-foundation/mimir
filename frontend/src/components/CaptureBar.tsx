import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Loader2, Paperclip, X, Check } from "lucide-react";
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
      className="flex items-center gap-2 px-5 py-3 bg-surface-1 border-b border-border-subtle"
    >
      <div className="flex-1 flex items-center gap-2 bg-surface-2 rounded-xl border border-border-subtle focus-within:border-brand-500/50 transition-colors">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            file
              ? `Title for ${file.name} (optional)`
              : "Capture anything... text, URL, idea    \u2318K"
          }
          className="flex-1 bg-transparent text-white pl-4 pr-2 py-2.5 text-[13px] focus:outline-none placeholder-zinc-500"
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
            className="flex items-center gap-1.5 px-2.5 py-1.5 mr-1 bg-brand-500/10 text-brand-400 rounded-lg text-xs border border-brand-500/20 hover:border-brand-500/40 transition-colors"
          >
            {file.name.length > 18 ? file.name.slice(0, 15) + "..." : file.name}
            <X className="w-3 h-3" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="p-2 mr-1 text-zinc-500 hover:text-zinc-300 rounded-lg hover:bg-surface-3 transition-colors"
            title="Attach file"
          >
            <Paperclip className="w-4 h-4" />
          </button>
        )}
      </div>

      <button
        type="submit"
        disabled={loading || (!input.trim() && !file)}
        className="p-2.5 bg-brand-500 hover:bg-brand-400 disabled:opacity-30 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <ArrowUp className="w-4 h-4" />
        )}
      </button>

      {message && (
        <span className={`text-xs font-medium flex items-center gap-1 ${message === "Captured!" ? "text-emerald-400" : "text-red-400"}`}>
          {message === "Captured!" && <Check className="w-3 h-3" />}
          {message}
        </span>
      )}
    </form>
  );
}
