import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { captureNote, captureUrl, getNotes } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowUp,
  Loader2,
  Check,
  Globe,
  MessageSquare,
  Paperclip,
  Mic,
  Camera,
  Square,
} from "lucide-react";
import { Link } from "react-router-dom";

export default function Capture() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"" | "success" | "error">("");
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const { data: recent } = useQuery({
    queryKey: ["notes", "recent-mobile"],
    queryFn: () => getNotes({ sort: "recent", limit: 5 }),
    refetchInterval: 5_000,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    setLoading(true);
    setStatus("");

    try {
      const isUrl = /^https?:\/\//i.test(input.trim());
      if (isUrl) {
        await captureUrl(input.trim());
      } else {
        await captureNote(input.trim());
      }
      setInput("");
      setStatus("success");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      setTimeout(() => setStatus(""), 3000);
    } catch {
      setStatus("error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <img src="/logo.png" alt="Mimir" className="w-8 h-8" />
          <span className="font-bold text-[15px]">Mimir</span>
        </div>
        <Link
          to="/"
          className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          Dashboard
        </Link>
      </header>

      {/* Capture form */}
      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type or paste anything..."
          rows={4}
          autoFocus
          className="w-full bg-zinc-900 text-white px-4 py-3 rounded-2xl border border-zinc-700 focus:outline-none focus:border-cyan-500 placeholder-zinc-500 text-[15px] resize-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="w-full py-3.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-30 disabled:cursor-not-allowed text-white rounded-2xl text-[15px] font-medium flex items-center justify-center gap-2 transition-colors"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : status === "success" ? (
            <Check className="w-5 h-5" />
          ) : (
            <ArrowUp className="w-5 h-5" />
          )}
          {loading
            ? "Capturing..."
            : status === "success"
              ? "Captured!"
              : "Capture"}
        </button>
        {status === "error" && (
          <p className="text-red-400 text-sm text-center">
            Failed to capture. Check your connection.
          </p>
        )}
      </form>

      {/* Extra capture modes */}
      <div className="px-4 grid grid-cols-3 gap-3">
        {/* File upload */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setLoading(true);
            setStatus("");
            try {
              const form = new FormData();
              form.append("file", file);
              const res = await fetch("/api/capture/file", { method: "POST", body: form });
              if (!res.ok) throw new Error("Upload failed");
              setStatus("success");
              queryClient.invalidateQueries({ queryKey: ["notes"] });
              setTimeout(() => setStatus(""), 3000);
            } catch {
              setStatus("error");
            } finally {
              setLoading(false);
              e.target.value = "";
            }
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          className="flex flex-col items-center gap-2 py-4 bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-300 hover:border-cyan-600 transition-colors disabled:opacity-30"
        >
          <Paperclip className="w-5 h-5" />
          <span className="text-xs font-medium">File</span>
        </button>

        {/* Voice recording */}
        <button
          onClick={async () => {
            if (recording && mediaRecorderRef.current) {
              mediaRecorderRef.current.stop();
              setRecording(false);
              return;
            }
            try {
              const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
              const mr = new MediaRecorder(stream);
              const chunks: Blob[] = [];
              mr.ondataavailable = (e) => chunks.push(e.data);
              mr.onstop = async () => {
                stream.getTracks().forEach((t) => t.stop());
                const blob = new Blob(chunks, { type: "audio/webm" });
                const form = new FormData();
                form.append("file", blob, "voice.webm");
                setLoading(true);
                try {
                  const res = await fetch("/api/capture/voice", { method: "POST", body: form });
                  if (!res.ok) throw new Error("Upload failed");
                  setStatus("success");
                  queryClient.invalidateQueries({ queryKey: ["notes"] });
                  setTimeout(() => setStatus(""), 3000);
                } catch {
                  setStatus("error");
                } finally {
                  setLoading(false);
                }
              };
              mediaRecorderRef.current = mr;
              mr.start();
              setRecording(true);
            } catch {
              setStatus("error");
            }
          }}
          disabled={loading}
          className={`flex flex-col items-center gap-2 py-4 border rounded-2xl transition-colors disabled:opacity-30 ${
            recording
              ? "bg-red-950/50 border-red-500/50 text-red-300"
              : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-cyan-600"
          }`}
        >
          {recording ? <Square className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          <span className="text-xs font-medium">{recording ? "Stop" : "Voice"}</span>
        </button>

        {/* Camera capture */}
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setLoading(true);
            setStatus("");
            try {
              const form = new FormData();
              form.append("file", file);
              const res = await fetch("/api/capture/file", { method: "POST", body: form });
              if (!res.ok) throw new Error("Upload failed");
              setStatus("success");
              queryClient.invalidateQueries({ queryKey: ["notes"] });
              setTimeout(() => setStatus(""), 3000);
            } catch {
              setStatus("error");
            } finally {
              setLoading(false);
              e.target.value = "";
            }
          }}
        />
        <button
          onClick={() => cameraInputRef.current?.click()}
          disabled={loading}
          className="flex flex-col items-center gap-2 py-4 bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-300 hover:border-cyan-600 transition-colors disabled:opacity-30"
        >
          <Camera className="w-5 h-5" />
          <span className="text-xs font-medium">Camera</span>
        </button>
      </div>

      {/* Recent captures */}
      <div className="flex-1 px-4 pb-4 pt-4">
        <h2 className="text-[11px] text-zinc-500 mb-2 uppercase tracking-wider font-medium">
          Recent
        </h2>
        {recent?.notes && recent.notes.length > 0 ? (
          <div className="space-y-2">
            {recent.notes.map((n) => (
              <Link
                key={n.id}
                to={`/notes/${n.id}`}
                className="flex items-center gap-3 bg-zinc-900 rounded-2xl p-3.5 border border-zinc-800"
              >
                {n.source_type === "url" ? (
                  <Globe className="w-4 h-4 text-zinc-600 shrink-0" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-zinc-600 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-white truncate">
                    {n.title || n.raw_content?.slice(0, 60) || "Untitled"}
                  </p>
                  <p className="text-[11px] text-zinc-600">
                    {formatDistanceToNow(new Date(n.created_at), {
                      addSuffix: true,
                    })}
                    {n.processing_status !== "complete" && (
                      <span className="ml-2 text-amber-500">
                        {n.processing_status}
                      </span>
                    )}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-zinc-600 text-sm">No notes yet.</p>
        )}
      </div>
    </div>
  );
}
