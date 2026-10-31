"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { agentApi } from "@/lib/api";

const CATEGORIES = [
  { value: "general", label: "General", icon: "🤖", desc: "All-purpose voice assistant" },
  { value: "sales", label: "Sales", icon: "💼", desc: "Lead qualification & pitching" },
  { value: "support", label: "Support", icon: "🎧", desc: "Customer support & troubleshooting" },
  { value: "hr", label: "HR", icon: "👔", desc: "Employee Q&A & onboarding" },
  { value: "interview", label: "Interview", icon: "🎤", desc: "Candidate screening & assessment" },
  { value: "education", label: "Education", icon: "📚", desc: "Teaching & tutoring" },
  { value: "healthcare", label: "Healthcare", icon: "🏥", desc: "Patient intake & triage" },
  { value: "custom", label: "Custom", icon: "⚙️", desc: "Start from scratch" },
];

const TEMPLATES: { name: string; category: string; prompt: string; desc: string }[] = [
  {
    name: "HR Assistant",
    category: "hr",
    desc: "Answer employee questions about policies, benefits, and leave",
    prompt: `You are an HR assistant. Help employees with questions about company policies, benefits, leave requests, and general HR topics.\n\nGuidelines:\n- Be professional and empathetic\n- Keep answers clear and concise (2-3 sentences)\n- If you don't know a specific policy, say so and suggest contacting HR directly\n- No markdown — this is spoken out loud`,
  },
  {
    name: "Interview Screener",
    category: "interview",
    desc: "Screen candidates with structured interview questions",
    prompt: `You are an interview screening agent. Conduct structured phone screens for job candidates.\n\nGuidelines:\n- Ask one question at a time\n- Start with background and experience\n- Move to technical/role-specific questions\n- Be professional but friendly\n- Take note of key answers\n- Keep responses concise — this is a phone call`,
  },
  {
    name: "Sales Agent",
    category: "sales",
    desc: "Qualify leads and pitch products naturally",
    prompt: `You are a friendly sales agent. Your goal is to qualify leads and naturally introduce products.\n\nGuidelines:\n- Ask discovery questions to understand the prospect's needs\n- Be conversational, never pushy\n- Listen actively and respond to pain points\n- Keep pitch natural — 2-3 sentences max\n- If prospect isn't interested, be graceful`,
  },
  {
    name: "Tech Support",
    category: "support",
    desc: "Troubleshoot technical issues step by step",
    prompt: `You are a technical support agent. Help users troubleshoot issues step by step.\n\nGuidelines:\n- Start by understanding the problem\n- Ask clarifying questions if needed\n- Give one step at a time, wait for confirmation\n- Use simple language, avoid jargon\n- If you can't resolve it, escalate properly`,
  },
];

export default function CreateAgentPage() {
  const router = useRouter();
  const [step, setStep] = useState<"category" | "template" | "details">("category");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const filteredTemplates = TEMPLATES.filter(
    (t) => !selectedCategory || t.category === selectedCategory
  );

  function selectTemplate(tmpl: typeof TEMPLATES[0]) {
    setName(tmpl.name);
    setDescription(tmpl.desc);
    setSystemPrompt(tmpl.prompt);
    setStep("details");
  }

  function selectBlank() {
    setName("");
    setDescription("");
    setSystemPrompt("");
    setStep("details");
  }

  async function handleCreate() {
    if (!name.trim()) {
      setError("Agent name is required");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const agent = await agentApi.create({
        name: name.trim(),
        description: description.trim(),
        category: selectedCategory || "general",
        system_prompt: systemPrompt,
      });
      router.push(`/agents/${agent.id}`);
    } catch (e: any) {
      setError(e.message || "Failed to create agent");
    }
    setCreating(false);
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-[var(--color-text-dim)] mb-6">
        <button onClick={() => router.push("/agents")} className="hover:text-[var(--color-text)]">
          Agents
        </button>
        <span>/</span>
        <span className="text-[var(--color-text)]">Create New Agent</span>
      </div>

      <h1 className="text-2xl font-bold mb-1">Create New Agent</h1>
      <p className="text-sm text-[var(--color-text-muted)] mb-8">
        {step === "category"
          ? "Choose what kind of agent you want to build"
          : step === "template"
          ? "Start with a template or from scratch"
          : "Configure your agent's identity"}
      </p>

      {/* Step 1: Category */}
      {step === "category" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => {
                setSelectedCategory(cat.value);
                setStep("template");
              }}
              className="flex flex-col items-center gap-2 p-5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl hover:border-[var(--color-primary)]/50 transition-all text-center group"
            >
              <span className="text-3xl group-hover:scale-110 transition-transform">{cat.icon}</span>
              <span className="text-sm font-medium">{cat.label}</span>
              <span className="text-[10px] text-[var(--color-text-dim)]">{cat.desc}</span>
            </button>
          ))}
        </div>
      )}

      {/* Step 2: Template */}
      {step === "template" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            {filteredTemplates.map((tmpl) => (
              <button
                key={tmpl.name}
                onClick={() => selectTemplate(tmpl)}
                className="text-left p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl hover:border-[var(--color-primary)]/50 transition-all"
              >
                <h3 className="font-medium text-sm mb-1">{tmpl.name}</h3>
                <p className="text-xs text-[var(--color-text-muted)]">{tmpl.desc}</p>
              </button>
            ))}
            <button
              onClick={selectBlank}
              className="text-left p-4 bg-[var(--color-surface)] border border-dashed border-[var(--color-border)] rounded-xl hover:border-[var(--color-primary)]/50 transition-all"
            >
              <h3 className="font-medium text-sm mb-1">✨ Start from Scratch</h3>
              <p className="text-xs text-[var(--color-text-muted)]">
                Build your own agent with a blank canvas
              </p>
            </button>
          </div>
          <button
            onClick={() => setStep("category")}
            className="text-xs text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
          >
            ← Back to categories
          </button>
        </div>
      )}

      {/* Step 3: Details */}
      {step === "details" && (
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
              Agent Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sales Assistant, Support Bot..."
              className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of what this agent does"
              className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
              System Prompt
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Define the agent's personality, instructions, and behavior..."
              rows={8}
              className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm font-mono focus:outline-none focus:border-[var(--color-primary)] resize-y"
            />
            <p className="text-[10px] text-[var(--color-text-dim)] mt-1">
              You can refine this in the prompt editor after creation
            </p>
          </div>

          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleCreate}
              disabled={creating}
              className="px-5 py-2.5 bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create Agent"}
            </button>
            <button
              onClick={() => setStep("template")}
              className="text-xs text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
            >
              ← Back
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
