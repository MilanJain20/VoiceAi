"use client";

import { useState } from "react";

interface KnowledgeBase {
  id: string;
  name: string;
  agent: string;
  documents: number;
  chunks: number;
  embeddingModel: string;
  chunkSize: number;
  chunkOverlap: number;
  status: "ready" | "processing" | "error";
  lastUpdated: string;
}

interface Document {
  id: string;
  filename: string;
  fileType: string;
  size: string;
  chunks: number;
  status: "ready" | "processing" | "error";
  uploadedAt: string;
}

const MOCK_KBS: KnowledgeBase[] = [
  { id: "1", name: "Product Documentation", agent: "Support Agent", documents: 23, chunks: 1847, embeddingModel: "text-embedding-3-small", chunkSize: 512, chunkOverlap: 50, status: "ready", lastUpdated: "2 hours ago" },
  { id: "2", name: "Company Policies", agent: "HR Assistant", documents: 8, chunks: 642, embeddingModel: "text-embedding-3-small", chunkSize: 256, chunkOverlap: 30, status: "ready", lastUpdated: "1 day ago" },
  { id: "3", name: "Sales Playbook", agent: "Sales Rep", documents: 12, chunks: 984, embeddingModel: "text-embedding-3-large", chunkSize: 1024, chunkOverlap: 100, status: "processing", lastUpdated: "5 min ago" },
];

const MOCK_DOCS: Document[] = [
  { id: "1", filename: "quickstart-guide.pdf", fileType: "PDF", size: "2.4 MB", chunks: 142, status: "ready", uploadedAt: "Jan 15, 2025" },
  { id: "2", filename: "api-reference.md", fileType: "Markdown", size: "890 KB", chunks: 78, status: "ready", uploadedAt: "Jan 14, 2025" },
  { id: "3", filename: "faq-database.csv", fileType: "CSV", size: "1.1 MB", chunks: 312, status: "ready", uploadedAt: "Jan 13, 2025" },
  { id: "4", filename: "release-notes-v3.docx", fileType: "DOCX", size: "456 KB", chunks: 0, status: "processing", uploadedAt: "Just now" },
  { id: "5", filename: "architecture-overview.pdf", fileType: "PDF", size: "5.2 MB", chunks: 287, status: "ready", uploadedAt: "Jan 12, 2025" },
];

export default function KnowledgeHubPage() {
  const [selectedKB, setSelectedKB] = useState<string | null>("1");
  const [showUpload, setShowUpload] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [testQuery, setTestQuery] = useState("");
  const [testResults, setTestResults] = useState<string[]>([]);

  const handleTestSearch = () => {
    if (!testQuery.trim()) return;
    setTestResults([
      "To reset your password, navigate to Settings > Security > Change Password. You will receive a verification email before the change takes effect...",
      "Password requirements: minimum 12 characters, at least one uppercase letter, one number, and one special character. Passwords expire every 90 days...",
      "If you're locked out of your account after 5 failed password attempts, contact support@company.com or use the self-service unlock tool at /account/unlock...",
    ]);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div>
          <h1 className="text-lg font-bold">📚 Knowledge Hub</h1>
          <p className="text-xs text-[var(--color-text-dim)]">RAG-powered knowledge bases — Upload documents, auto-chunk, embed & search</p>
        </div>
        <button className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-lg text-xs font-medium hover:opacity-90">
          + New Knowledge Base
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* KB List */}
        <div className="w-72 border-r border-[var(--color-border)] p-4 overflow-y-auto">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-3">Knowledge Bases</p>
          <div className="space-y-2">
            {MOCK_KBS.map((kb) => (
              <button
                key={kb.id}
                onClick={() => setSelectedKB(kb.id)}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selectedKB === kb.id
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs font-semibold truncate">{kb.name}</p>
                  <span className={`w-2 h-2 rounded-full ${kb.status === "ready" ? "bg-emerald-500" : kb.status === "processing" ? "bg-amber-500 animate-pulse" : "bg-red-500"}`} />
                </div>
                <p className="text-[10px] text-[var(--color-text-dim)]">{kb.agent}</p>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-[9px] text-[var(--color-text-dim)]">📄 {kb.documents} docs</span>
                  <span className="text-[9px] text-[var(--color-text-dim)]">🧩 {kb.chunks} chunks</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        {selectedKB && (() => {
          const kb = MOCK_KBS.find((k) => k.id === selectedKB);
          if (!kb) return null;
          return (
            <div className="flex-1 overflow-y-auto">
              {/* KB Info */}
              <div className="p-6 border-b border-[var(--color-border)]">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold">{kb.name}</h2>
                    <p className="text-[10px] text-[var(--color-text-dim)] mt-0.5">
                      Linked to: {kb.agent} · Updated {kb.lastUpdated}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowUpload(!showUpload)}
                      className="px-3 py-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-lg text-xs font-medium hover:bg-emerald-500/20"
                    >
                      📤 Upload Files
                    </button>
                    <button className="px-3 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs hover:border-[var(--color-border-hover)]">
                      ⚙️ Settings
                    </button>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-4 gap-3 mt-4">
                  {[
                    { label: "Documents", value: kb.documents, icon: "📄" },
                    { label: "Chunks", value: kb.chunks.toLocaleString(), icon: "🧩" },
                    { label: "Chunk Size", value: kb.chunkSize, icon: "📐" },
                    { label: "Overlap", value: kb.chunkOverlap, icon: "🔗" },
                  ].map((stat) => (
                    <div key={stat.label} className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                      <p className="text-[9px] text-[var(--color-text-dim)]">{stat.icon} {stat.label}</p>
                      <p className="text-sm font-bold mt-0.5">{stat.value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Upload Zone */}
              {showUpload && (
                <div className="p-6 border-b border-[var(--color-border)] bg-emerald-500/5">
                  <div className="border-2 border-dashed border-emerald-500/30 rounded-xl p-8 text-center hover:border-emerald-500/50 transition-colors cursor-pointer">
                    <p className="text-2xl mb-2">📤</p>
                    <p className="text-sm font-medium">Drop files here or click to browse</p>
                    <p className="text-[10px] text-[var(--color-text-dim)] mt-1">
                      Supports PDF, DOCX, MD, TXT, CSV, HTML — Max 50MB per file
                    </p>
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[9px]">PDF</span>
                      <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[9px]">DOCX</span>
                      <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[9px]">MD</span>
                      <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[9px]">CSV</span>
                      <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[9px]">URL</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Documents List */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold">Documents ({MOCK_DOCS.length})</p>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search documents..."
                    className="px-2.5 py-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-[10px] w-40 focus:outline-none focus:border-[var(--color-primary)]"
                  />
                </div>
                <div className="space-y-1.5">
                  {MOCK_DOCS.filter((d) => d.filename.includes(searchQuery)).map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-2.5 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] hover:border-[var(--color-border-hover)] transition-colors">
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm">
                          {doc.fileType === "PDF" ? "📕" : doc.fileType === "Markdown" ? "📝" : doc.fileType === "CSV" ? "📊" : "📄"}
                        </span>
                        <div>
                          <p className="text-xs font-medium">{doc.filename}</p>
                          <p className="text-[9px] text-[var(--color-text-dim)]">{doc.size} · {doc.uploadedAt}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[9px] text-[var(--color-text-dim)]">{doc.chunks} chunks</span>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          doc.status === "ready" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                        }`}>
                          {doc.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Test Search */}
                <div className="mt-6 p-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                  <p className="text-xs font-semibold mb-2">🔍 Test RAG Search</p>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={testQuery}
                      onChange={(e) => setTestQuery(e.target.value)}
                      placeholder="Ask a question to test retrieval..."
                      className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-xs focus:outline-none focus:border-[var(--color-primary)]"
                      onKeyDown={(e) => e.key === "Enter" && handleTestSearch()}
                    />
                    <button
                      onClick={handleTestSearch}
                      className="px-3 py-2 bg-[var(--color-primary)] text-white rounded-lg text-xs font-medium"
                    >
                      Search
                    </button>
                  </div>
                  {testResults.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-[9px] font-semibold text-[var(--color-text-dim)]">TOP 3 RESULTS:</p>
                      {testResults.map((r, i) => (
                        <div key={i} className="p-2.5 bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)]">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="text-[9px] font-bold text-[var(--color-primary)]">#{i + 1}</span>
                            <span className="text-[9px] text-[var(--color-text-dim)]">Score: {(0.95 - i * 0.08).toFixed(2)}</span>
                          </div>
                          <p className="text-[10px] text-[var(--color-text-dim)] line-clamp-2">{r}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
