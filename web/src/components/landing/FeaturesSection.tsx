import { useState } from "react";

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const customFeatures: Feature[] = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
    ),
    title: "MCP & Agent Skills",
    description: "Connect with MCP \u2014 the open standard for agent interoperability",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
    title: "OpenClaw Skills & CLI",
    description: "Connect your OpenClaw Agent with official Kutana skills and CLI",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
    title: "Agent & Model Agnostic",
    description: "Just plug in your agents via MCP, Skills, or CLI and they\u2019re connected",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
    title: "Full Capabilities",
    description: "Listen, speak, chat, extract tasks \u2014 your agent chooses what it uses",
  },
];

const managedFeatures: Feature[] = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M16 13H8m8 4H8m2-8H8" />
      </svg>
    ),
    title: "Meeting Summarizer",
    description: "Instant actionable summaries after every meeting",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
    title: "Action Tracker",
    description: "Auto-extract tasks, assign owners, track deadlines",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    ),
    title: "Productivity Suite",
    description: "Standup facilitators, note-takers, decision loggers",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
        <line x1="14" y1="4" x2="10" y2="20" />
      </svg>
    ),
    title: "Engineering Suite",
    description: "Sprint planners, code context agents, retrospective bots",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
    title: "Growing Library",
    description: "New Kutana Managed Agents added regularly across categories",
  },
];

export function FeaturesSection() {
  const [activeTab, setActiveTab] = useState<"custom" | "managed">("custom");
  const features = activeTab === "custom" ? customFeatures : managedFeatures;

  return (
    <section
      id="features"
      className="relative py-24 bg-gradient-to-br from-emerald-950/20 to-teal-950/10"
    >
      <div className="max-w-7xl mx-auto px-6">
        {/* Section heading */}
        <h2 className="text-3xl md:text-4xl font-bold text-center text-white mb-4">
          Agents: Your Agents or Kutana Agents
        </h2>
        <p className="text-center text-white/60 max-w-2xl mx-auto mb-10">
          Bring your own agents or activate one of ours. Either way, they&rsquo;re in the meeting in seconds.
        </p>

        {/* Toggle switch */}
        <div className="flex justify-center mb-12">
          <div className="inline-flex rounded-full bg-white/5 border border-white/10 p-1 gap-1">
            <button
              onClick={() => setActiveTab("custom")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                activeTab === "custom"
                  ? "bg-green-600 text-white shadow-lg shadow-green-600/25"
                  : "text-white/60 hover:text-white"
              }`}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="w-4 h-4"
              >
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
              </svg>
              Your Agents
            </button>
            <button
              onClick={() => setActiveTab("managed")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                activeTab === "managed"
                  ? "bg-green-600 text-white shadow-lg shadow-green-600/25"
                  : "text-white/60 hover:text-white"
              }`}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="w-4 h-4"
              >
                <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
                <line x1="16" y1="8" x2="2" y2="22" />
                <line x1="17.5" y1="15" x2="9" y2="15" />
              </svg>
              Kutana Managed Agents
            </button>
          </div>
        </div>

        {/* Feature card */}
        <div className="max-w-3xl mx-auto rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm p-8">
          <h3 className="text-xl font-semibold text-white mb-2 flex items-center gap-3">
            {activeTab === "custom" ? (
              <>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="w-6 h-6 text-green-500"
                >
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
                Your Agents
              </>
            ) : (
              <>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="w-6 h-6 text-green-500"
                >
                  <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
                  <line x1="16" y1="8" x2="2" y2="22" />
                  <line x1="17.5" y1="15" x2="9" y2="15" />
                </svg>
                Kutana Managed Agents
              </>
            )}
          </h3>
          <p className="text-white/60 mb-8">
            {activeTab === "custom"
              ? "Bring any agent. Kutana meets it where it is."
              : "Pre-built, production-ready agents. One click to activate."}
          </p>

          {/* Feature list */}
          <div className="space-y-5">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="flex items-start gap-4 group"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-600/15 border border-green-500/20 flex items-center justify-center text-green-500 group-hover:bg-green-600/25 transition-colors duration-300">
                  {feature.icon}
                </div>
                <div>
                  <p className="text-white font-medium">{feature.title}</p>
                  <p className="text-white/50 text-sm mt-0.5">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
