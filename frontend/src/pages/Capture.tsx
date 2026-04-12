import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { captureNote, captureUrl, getNotes } from "../lib/api";
import { formatDistanceToNow } from "date-fns";
import {
  Send,
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

/**
 * Mobile-friendly capture page — minimal, responsive, optimized for phones.
 * Accessible at /capture without the sidebar layout.
 */
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
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-sm font-bold">
            M
          </div>
          <span className="font-semibold">Mimir</span>
        </div>
        <Link
          to="/"
          className="text-xs text-gray-500 hover:text-gray-300"
        >
          Dashboard →
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
          className="w-full bg-gray-900 text-white px-4 py-3 rounded-xl border border-gray-700 focus:outline-none focus:border-indigo-500 placeholder-gray-500 text-base resize-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-base font-medium flex items-center justify-center gap-2 transition-colors"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : status === "success" ? (
            <Check className="w-5 h-5" />
          ) : (
            <Send className="w-5 h-5" />
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
          className="flex flex-col items-center gap-1.5 py-3 bg-gray-900 border border-gray-700 rounded-xl text-gray-300 hover:border-indigo-500 transition-colors disabled:opacity-50"
        >
          <Paperclip className="w-5 h-5" />
          <span className="text-xs">File</span>
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
          className={`flex flex-col items-center gap-1.5 py-3 border rounded-xl transition-colors disabled:opacity-50 ${
            recording
              ? "bg-red-950 border-red-500 text-red-300"
              : "bg-gray-900 border-gray-700 text-gray-300 hover:border-indigo-500"
          }`}
        >
          {recording ? <Square className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          <span className="text-xs">{recording ? "Stop" : "Voice"}</span>
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
          className="flex flex-col items-center gap-1.5 py-3 bg-gray-900 border border-gray-700 rounded-xl text-gray-300 hover:border-indigo-500 transition-colors disabled:opacity-50"
        >
          <Camera className="w-5 h-5" />
          <span className="text-xs">Camera</span>
        </button>
      </div>

      {/* Recent captures */}
      <div className="flex-1 px-4 pb-4">
        <h2 className="text-xs text-gray-500 mb-2 uppercase tracking-wider">
          Recent
        </h2>
        {recent?.notes && recent.notes.length > 0 ? (
          <div className="space-y-2">
            {recent.notes.map((n) => (
              <Link
                key={n.id}
                to={`/notes/${n.id}`}
                className="flex items-center gap-3 bg-gray-900 rounded-xl p-3 border border-gray-800"
              >
                {n.source_type === "url" ? (
                  <Globe className="w-4 h-4 text-gray-600 shrink-0" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-gray-600 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">
                    {n.title || n.raw_content?.slice(0, 60) || "Untitled"}
                  </p>
                  <p className="text-xs text-gray-600">
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
          <p className="text-gray-600 text-sm">No notes yet.</p>
        )}
      </div>
    </div>
  );
}
