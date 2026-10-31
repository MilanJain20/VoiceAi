"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// ── Node type definitions ────────────────────────────────────────

interface WorkflowNode {
  id: string;
  type: string;
  label: string;
  icon: string;
  x: number;
  y: number;
  config: Record<string, any>;
}

interface WorkflowEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
}

const NODE_CATALOG = [
  { type: "trigger", label: "Trigger", icon: "⚡", color: "#f59e0b", desc: "Start the workflow" },
  { type: "llm", label: "LLM", icon: "🧠", color: "#6366f1", desc: "Process with AI" },
  { type: "tool", label: "Tool", icon: "🔧", color: "#22c55e", desc: "Call an external tool" },
  { type: "condition", label: "Condition", icon: "🔀", color: "#3b82f6", desc: "Branch on condition" },
  { type: "action", label: "Action", icon: "⚙️", color: "#8b5cf6", desc: "Execute an action" },
  { type: "delay", label: "Delay", icon: "⏱️", color: "#71717a", desc: "Wait for duration" },
  { type: "human_handoff", label: "Handoff", icon: "🙋", color: "#ef4444", desc: "Transfer to human" },
  { type: "end", label: "End", icon: "🏁", color: "#71717a", desc: "End the workflow" },
];

const NODE_COLORS: Record<string, string> = {};
NODE_CATALOG.forEach((n) => (NODE_COLORS[n.type] = n.color));

// ── Default template workflow ────────────────────────────────────

const DEFAULT_NODES: WorkflowNode[] = [
  { id: "1", type: "trigger", label: "User Request", icon: "⚡", x: 80, y: 200, config: { event: "user_speech" } },
  { id: "2", type: "llm", label: "Planner", icon: "🧠", x: 340, y: 120, config: { model: "gpt-4o", prompt: "Plan the next steps" } },
  { id: "3", type: "tool", label: "Calendar", icon: "🔧", x: 600, y: 60, config: { tool: "calendar_check" } },
  { id: "4", type: "tool", label: "Email", icon: "🔧", x: 600, y: 200, config: { tool: "send_email" } },
  { id: "5", type: "condition", label: "Confirmed?", icon: "🔀", x: 600, y: 340, config: { condition: "user_confirmed" } },
  { id: "6", type: "action", label: "Confirm", icon: "⚙️", x: 860, y: 200, config: { action: "send_confirmation" } },
  { id: "7", type: "end", label: "Done", icon: "🏁", x: 1100, y: 200, config: {} },
];

const DEFAULT_EDGES: WorkflowEdge[] = [
  { id: "e1", from: "1", to: "2" },
  { id: "e2", from: "2", to: "3", label: "schedule" },
  { id: "e3", from: "2", to: "4", label: "notify" },
  { id: "e4", from: "2", to: "5", label: "check" },
  { id: "e5", from: "3", to: "6" },
  { id: "e6", from: "4", to: "6" },
  { id: "e7", from: "5", to: "6", label: "yes" },
  { id: "e8", from: "6", to: "7" },
];

// ── Main Component ───────────────────────────────────────────────

export default function WorkflowBuilderPage() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<WorkflowNode[]>(DEFAULT_NODES);
  const [edges, setEdges] = useState<WorkflowEdge[]>(DEFAULT_EDGES);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ id: string; ox: number; oy: number } | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  // ── Drag handling ──
  const handleMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return;
    setDragging({ id: nodeId, ox: e.clientX - node.x * zoom, oy: e.clientY - node.y * zoom });
    setSelectedNode(nodeId);
  }, [nodes, zoom]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    setNodes((prev) =>
      prev.map((n) =>
        n.id === dragging.id
          ? { ...n, x: (e.clientX - dragging.ox) / zoom, y: (e.clientY - dragging.oy) / zoom }
          : n
      )
    );
  }, [dragging, zoom]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  // ── Connection ──
  const startConnection = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    if (connecting) {
      if (connecting !== nodeId) {
        setEdges((prev) => [
          ...prev,
          { id: `e${Date.now()}`, from: connecting, to: nodeId },
        ]);
      }
      setConnecting(null);
    } else {
      setConnecting(nodeId);
    }
  }, [connecting]);

  // ── Add node ──
  const addNode = useCallback((type: string) => {
    const cat = NODE_CATALOG.find((n) => n.type === type);
    if (!cat) return;
    const id = `n${Date.now()}`;
    setNodes((prev) => [
      ...prev,
      { id, type, label: cat.label, icon: cat.icon, x: 400 + Math.random() * 200, y: 150 + Math.random() * 200, config: {} },
    ]);
  }, []);

  // ── Delete node ──
  const deleteSelected = useCallback(() => {
    if (!selectedNode) return;
    setNodes((prev) => prev.filter((n) => n.id !== selectedNode));
    setEdges((prev) => prev.filter((e) => e.from !== selectedNode && e.to !== selectedNode));
    setSelectedNode(null);
  }, [selectedNode]);

  // ── Draw edges as SVG ──
  function renderEdges() {
    return edges.map((edge) => {
      const from = nodeMap.get(edge.from);
      const to = nodeMap.get(edge.to);
      if (!from || !to) return null;
      const x1 = from.x + 90;
      const y1 = from.y + 28;
      const x2 = to.x;
      const y2 = to.y + 28;
      const mx = (x1 + x2) / 2;
      return (
        <g key={edge.id}>
          <path
            d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
            fill="none"
            stroke={connecting ? "#6366f144" : "#6366f1"}
            strokeWidth={2}
            strokeDasharray={edge.label ? "6,3" : "none"}
            opacity={0.6}
          />
          {edge.label && (
            <text x={mx} y={(y1 + y2) / 2 - 6} textAnchor="middle" fill="#a1a1aa" fontSize={10}>
              {edge.label}
            </text>
          )}
          {/* Arrow */}
          <circle cx={x2} cy={y2} r={3} fill="#6366f1" opacity={0.8} />
        </g>
      );
    });
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--color-border)]">
        <div>
          <h1 className="text-sm font-bold">Workflow Builder</h1>
          <p className="text-[10px] text-[var(--color-text-dim)]">Visual automation — drag nodes, connect edges</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--color-text-dim)]">{nodes.length} nodes · {edges.length} edges</span>
          {selectedNode && (
            <button onClick={deleteSelected} className="px-2 py-1 text-[10px] text-red-400 hover:bg-red-500/10 rounded">Delete Node</button>
          )}
          {connecting && (
            <span className="text-[10px] text-amber-400 animate-pulse">Click a node to connect →</span>
          )}
          <button className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-lg text-xs font-medium">
            Save Workflow
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Node palette */}
        <div className="w-48 border-r border-[var(--color-border)] p-3 overflow-y-auto">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-2">
            Nodes
          </p>
          <div className="space-y-1.5">
            {NODE_CATALOG.map((cat) => (
              <button
                key={cat.type}
                onClick={() => addNode(cat.type)}
                className="w-full flex items-center gap-2 px-2.5 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg hover:border-[var(--color-primary)]/40 transition-colors text-left"
              >
                <span className="text-sm" style={{ filter: `drop-shadow(0 0 4px ${cat.color}44)` }}>{cat.icon}</span>
                <div>
                  <p className="text-xs font-medium">{cat.label}</p>
                  <p className="text-[9px] text-[var(--color-text-dim)]">{cat.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Canvas */}
        <div
          ref={canvasRef}
          className="flex-1 relative bg-[#0a0a12] overflow-hidden cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onClick={() => { setSelectedNode(null); setConnecting(null); }}
          style={{ backgroundImage: "radial-gradient(circle, #1a1a2e 1px, transparent 1px)", backgroundSize: "24px 24px" }}
        >
          {/* Edges SVG layer */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ transform: `scale(${zoom})`, transformOrigin: "0 0" }}>
            {renderEdges()}
          </svg>

          {/* Nodes */}
          <div style={{ transform: `scale(${zoom})`, transformOrigin: "0 0" }}>
            {nodes.map((node) => {
              const isSelected = selectedNode === node.id;
              const isConnecting = connecting === node.id;
              const color = NODE_COLORS[node.type] || "#6366f1";
              return (
                <div
                  key={node.id}
                  className={`absolute select-none cursor-grab active:cursor-grabbing`}
                  style={{ left: node.x, top: node.y }}
                  onMouseDown={(e) => handleMouseDown(e, node.id)}
                >
                  <div
                    className={`flex items-center gap-2 px-3 py-2 rounded-xl border-2 transition-all min-w-[140px] ${
                      isSelected
                        ? "border-[var(--color-primary)] shadow-lg shadow-[var(--color-primary)]/20"
                        : isConnecting
                        ? "border-amber-500 shadow-amber-500/20"
                        : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                    }`}
                    style={{ background: `linear-gradient(135deg, ${color}15, #111118)` }}
                  >
                    <span className="text-lg" style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}>{node.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold truncate">{node.label}</p>
                      <p className="text-[9px] text-[var(--color-text-dim)] capitalize">{node.type}</p>
                    </div>
                    {/* Connection port */}
                    <button
                      onClick={(e) => startConnection(e, node.id)}
                      className={`w-3.5 h-3.5 rounded-full border-2 flex-shrink-0 transition-colors ${
                        connecting && connecting !== node.id
                          ? "border-emerald-500 bg-emerald-500/30 animate-pulse"
                          : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]"
                      }`}
                      title={connecting ? "Click to connect" : "Start connection"}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Properties panel */}
        {selectedNode && (() => {
          const node = nodes.find((n) => n.id === selectedNode);
          if (!node) return null;
          return (
            <div className="w-64 border-l border-[var(--color-border)] p-4 overflow-y-auto">
              <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-3">
                Node Properties
              </p>
              <div className="space-y-3">
                <div>
                  <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Label</label>
                  <input
                    type="text"
                    value={node.label}
                    onChange={(e) => setNodes((prev) => prev.map((n) => n.id === node.id ? { ...n, label: e.target.value } : n))}
                    className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs focus:outline-none focus:border-[var(--color-primary)]"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Type</label>
                  <p className="text-xs font-mono capitalize px-2 py-1.5 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                    {node.type}
                  </p>
                </div>
                {node.type === "llm" && (
                  <>
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Model</label>
                      <select className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs">
                        <option>gpt-4o</option>
                        <option>gpt-4o-mini</option>
                        <option>gpt-3.5-turbo</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Prompt</label>
                      <textarea
                        rows={4}
                        className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs resize-y focus:outline-none focus:border-[var(--color-primary)]"
                        defaultValue={node.config.prompt || ""}
                        placeholder="Instructions for this LLM step..."
                      />
                    </div>
                  </>
                )}
                {node.type === "tool" && (
                  <div>
                    <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Tool</label>
                    <select className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs">
                      <option>calendar_check</option>
                      <option>send_email</option>
                      <option>get_weather</option>
                      <option>calculator</option>
                      <option>crm_lookup</option>
                      <option>http_request</option>
                    </select>
                  </div>
                )}
                {node.type === "condition" && (
                  <div>
                    <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Condition</label>
                    <input
                      type="text"
                      className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs focus:outline-none focus:border-[var(--color-primary)]"
                      defaultValue={node.config.condition || ""}
                      placeholder="e.g. user_confirmed == true"
                    />
                  </div>
                )}
                {node.type === "delay" && (
                  <div>
                    <label className="block text-[10px] text-[var(--color-text-dim)] mb-1">Duration (seconds)</label>
                    <input
                      type="number"
                      className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs"
                      defaultValue={5}
                    />
                  </div>
                )}
                <div className="pt-2 border-t border-[var(--color-border)]">
                  <p className="text-[9px] text-[var(--color-text-dim)]">
                    ID: {node.id} · Position: ({Math.round(node.x)}, {Math.round(node.y)})
                  </p>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
