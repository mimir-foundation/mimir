import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getGraph, getConcepts } from "../lib/api";
import type { GraphNode, GraphEdge } from "../lib/api";
import { Filter } from "lucide-react";

const TYPE_COLORS: Record<string, string> = {
  related: "#06b6d4",
  builds_on: "#10b981",
  contradicts: "#ef4444",
  supports: "#14b8a6",
  inspired_by: "#a855f7",
};

const SOURCE_COLORS: Record<string, string> = {
  manual: "#818cf8",
  url: "#38bdf8",
  file: "#f59e0b",
  clipboard: "#a78bfa",
  highlight: "#fb923c",
  email: "#34d399",
  voice: "#f472b6",
};

export default function Connections() {
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement>(null);
  const [concept, setConcept] = useState("");
  const [minStrength, setMinStrength] = useState(0.3);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  const { data: conceptsData } = useQuery({
    queryKey: ["concepts"],
    queryFn: getConcepts,
  });

  const { data: graph } = useQuery({
    queryKey: ["graph", concept, minStrength],
    queryFn: () =>
      getGraph({
        concept: concept || undefined,
        min_strength: minStrength,
      }),
  });

  useEffect(() => {
    if (!graph || !svgRef.current) return;
    renderGraph(graph.nodes, graph.edges, svgRef.current, navigate, setHoveredNode);
  }, [graph, navigate]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-white">Connections</h1>
        <div className="flex items-center gap-3">
          <Filter className="w-4 h-4 text-zinc-500" />
          <select
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            className="bg-surface-2 text-zinc-300 border border-border-subtle rounded-lg px-3 py-1.5 text-xs"
          >
            <option value="">All concepts</option>
            {conceptsData?.concepts?.slice(0, 30).map((c) => (
              <option key={c.id} value={c.name}>
                {c.name} ({c.note_count})
              </option>
            ))}
          </select>
          <label className="text-xs text-zinc-500 flex items-center gap-2">
            Min strength
            <input
              type="range"
              min={0.1}
              max={0.9}
              step={0.1}
              value={minStrength}
              onChange={(e) => setMinStrength(parseFloat(e.target.value))}
              className="w-20"
            />
            <span className="text-zinc-400 w-6">{minStrength}</span>
          </label>
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-3 flex-wrap">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1 text-xs text-zinc-500">
            <span
              className="w-3 h-0.5 rounded inline-block"
              style={{ backgroundColor: color }}
            />
            {type.replace("_", " ")}
          </span>
        ))}
      </div>

      {/* Tooltip */}
      {hoveredNode && (
        <div className="absolute z-10 bg-surface-2 border border-border-subtle rounded-lg p-3 shadow-xl max-w-xs pointer-events-none"
             style={{ top: 180, right: 24 }}>
          <p className="text-sm text-white font-medium">{hoveredNode.title}</p>
          <p className="text-xs text-zinc-500 mt-1">
            {hoveredNode.source_type} · {hoveredNode.connection_count} connections
          </p>
          {hoveredNode.concepts.length > 0 && (
            <div className="flex gap-1 mt-2 flex-wrap">
              {hoveredNode.concepts.map((c) => (
                <span key={c} className="px-1.5 py-0.5 bg-indigo-900/40 text-indigo-300 rounded text-xs">
                  {c}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Graph */}
      <div className="flex-1 bg-surface-2 rounded-lg border border-border-subtle overflow-hidden relative">
        {graph && graph.nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
            No connections found. Capture more notes and they'll start connecting.
          </div>
        ) : (
          <svg ref={svgRef} className="w-full h-full" />
        )}
      </div>
    </div>
  );
}

function renderGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  svg: SVGSVGElement,
  navigate: (path: string) => void,
  setHovered: (node: GraphNode | null) => void,
) {
  // Clear previous
  svg.innerHTML = "";

  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 600;

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  // Simple force simulation (no D3 dependency — vanilla JS)
  const nodeMap = new Map<string, GraphNode & { x: number; y: number; vx: number; vy: number }>();

  nodes.forEach((n, i) => {
    const angle = (i / nodes.length) * Math.PI * 2;
    const r = Math.min(width, height) * 0.35;
    nodeMap.set(n.id, {
      ...n,
      x: width / 2 + Math.cos(angle) * r * (0.5 + Math.random() * 0.5),
      y: height / 2 + Math.sin(angle) * r * (0.5 + Math.random() * 0.5),
      vx: 0,
      vy: 0,
    });
  });

  const simNodes = Array.from(nodeMap.values());

  // Run simulation steps
  for (let tick = 0; tick < 150; tick++) {
    const alpha = 1 - tick / 150;

    // Repulsion between all nodes
    for (let i = 0; i < simNodes.length; i++) {
      for (let j = i + 1; j < simNodes.length; j++) {
        const a = simNodes[i], b = simNodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = -300 * alpha / (dist * dist);
        dx *= force / dist;
        dy *= force / dist;
        a.vx -= dx; a.vy -= dy;
        b.vx += dx; b.vy += dy;
      }
    }

    // Attraction along edges
    for (const edge of edges) {
      const a = nodeMap.get(edge.source);
      const b = nodeMap.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 120) * 0.01 * alpha * edge.strength;
      a.vx += (dx / dist) * force;
      a.vy += (dy / dist) * force;
      b.vx -= (dx / dist) * force;
      b.vy -= (dy / dist) * force;
    }

    // Center gravity
    for (const n of simNodes) {
      n.vx += (width / 2 - n.x) * 0.001 * alpha;
      n.vy += (height / 2 - n.y) * 0.001 * alpha;
    }

    // Apply velocity with damping
    for (const n of simNodes) {
      n.vx *= 0.6;
      n.vy *= 0.6;
      n.x += n.vx;
      n.y += n.vy;
      // Bounds
      n.x = Math.max(30, Math.min(width - 30, n.x));
      n.y = Math.max(30, Math.min(height - 30, n.y));
    }
  }

  // Render edges
  const edgeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  for (const edge of edges) {
    const a = nodeMap.get(edge.source);
    const b = nodeMap.get(edge.target);
    if (!a || !b) continue;

    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", String(a.x));
    line.setAttribute("y1", String(a.y));
    line.setAttribute("x2", String(b.x));
    line.setAttribute("y2", String(b.y));
    line.setAttribute("stroke", TYPE_COLORS[edge.type] || "#374151");
    line.setAttribute("stroke-width", String(Math.max(1, edge.strength * 3)));
    line.setAttribute("stroke-opacity", String(0.3 + edge.strength * 0.5));
    edgeGroup.appendChild(line);
  }
  svg.appendChild(edgeGroup);

  // Render nodes
  const nodeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  for (const n of simNodes) {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.style.cursor = "pointer";

    const radius = Math.max(5, Math.min(16, 4 + n.connection_count * 2));
    const color = SOURCE_COLORS[n.source_type] || "#6b7280";

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", String(n.x));
    circle.setAttribute("cy", String(n.y));
    circle.setAttribute("r", String(radius));
    circle.setAttribute("fill", color);
    circle.setAttribute("stroke", n.is_starred ? "#fbbf24" : "#1f2937");
    circle.setAttribute("stroke-width", n.is_starred ? "2" : "1");

    // Label
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", String(n.x));
    text.setAttribute("y", String(n.y + radius + 12));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#9ca3af");
    text.setAttribute("font-size", "10");
    text.textContent = (n.title || "").slice(0, 20) + ((n.title || "").length > 20 ? "…" : "");

    g.appendChild(circle);
    g.appendChild(text);

    g.addEventListener("click", () => navigate(`/notes/${n.id}`));
    g.addEventListener("mouseenter", () => setHovered(n));
    g.addEventListener("mouseleave", () => setHovered(null));

    nodeGroup.appendChild(g);
  }
  svg.appendChild(nodeGroup);
}
