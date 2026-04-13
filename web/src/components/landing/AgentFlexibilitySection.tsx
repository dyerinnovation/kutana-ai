import { useState, useEffect, useRef, useCallback } from "react";
import GetStartedCTA from "./GetStartedCTA";

/* ------------------------------------------------------------------ */
/*  Tab data                                                           */
/* ------------------------------------------------------------------ */

interface AgentTab {
  label: string;
  icon: React.ReactNode;
  badgeIcon: React.ReactNode;
  title: string;
  description: string;
  features: string[];
}

const tabs: AgentTab[] = [
  {
    label: "Text + TTS",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={20}
        height={20}
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    badgeIcon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={48}
        height={48}
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    title: "Text + Kutana Text-to-Speech (TTS)",
    description:
      "Your agent sends text, Kutana reads it aloud. One toggle gives every agent a voice \u2014 zero voice capability needed.",
    features: [
      "Kutana Text-to-Speech (TTS)",
      "One-toggle setup",
      "No voice SDK needed",
      "Premium voices available",
    ],
  },
  {
    label: "Voice",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={20}
        height={20}
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      </svg>
    ),
    badgeIcon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={48}
        height={48}
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    ),
    title: "Voice Agents",
    description:
      "Full audio stream access. Speaks and listens naturally in the conversation like any human attendee.",
    features: [
      "Full audio stream",
      "Real-time STT",
      "Natural speech",
      "Turn-taking",
    ],
  },
  {
    label: "Text Only",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={20}
        height={20}
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
      </svg>
    ),
    badgeIcon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={48}
        height={48}
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M16 13H8m8 4H8m2-8H8" />
      </svg>
    ),
    title: "Text-Only Agents",
    description:
      "Receives transcripts, summaries, and tasks directly. No voice needed \u2014 full meeting understanding through text.",
    features: [
      "Live transcripts",
      "Task extraction",
      "Chat responses",
      "No audio required",
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AgentFlexibilitySection() {
  const [active, setActive] = useState(0);
  const pausedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startAutoRotate = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      if (!pausedRef.current) {
        setActive((prev) => (prev + 1) % tabs.length);
      }
    }, 8000);
  }, []);

  useEffect(() => {
    startAutoRotate();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [startAutoRotate]);

  const handleTabClick = useCallback(
    (idx: number) => {
      setActive(idx);
      startAutoRotate();
    },
    [startAutoRotate],
  );

  const tab = tabs[active];

  return (
    <section
      className="py-24 px-4"
      onMouseEnter={() => {
        pausedRef.current = true;
      }}
      onMouseLeave={() => {
        pausedRef.current = false;
      }}
    >
      <div className="max-w-4xl mx-auto">
        <h2 className="text-center text-3xl sm:text-4xl font-bold mb-3 text-white">
          Every Agent Gets What It Needs
        </h2>
        <p className="text-center text-gray-400 mb-10 text-lg">
          Kutana meets your agent where it is &mdash; no matter its
          capabilities.
        </p>

        <div className="bg-slate-900/60 border border-white/[0.08] rounded-2xl overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-white/[0.08]">
            {tabs.map((t, i) => (
              <button
                key={i}
                onClick={() => handleTabClick(i)}
                className={`flex-1 flex items-center justify-center gap-2 py-3.5 px-4 text-sm font-semibold transition-all duration-300 border-b-2 cursor-pointer ${
                  i === active
                    ? "text-teal-500 border-teal-500 bg-teal-500/[0.06]"
                    : "text-white/50 border-transparent hover:text-white/70 hover:bg-white/[0.03]"
                }`}
              >
                <span
                  className={
                    i === active ? "text-teal-500" : "text-white/40"
                  }
                >
                  {t.icon}
                </span>
                <span className="max-[500px]:hidden">{t.label}</span>
              </button>
            ))}
          </div>

          {/* Panel */}
          <div className="flex flex-col sm:flex-row items-center gap-8 p-8">
            {/* Visual badge */}
            <div className="flex items-center justify-center w-28 h-28 shrink-0 rounded-2xl bg-teal-500/[0.08] border border-teal-500/20 text-teal-500">
              {tab.badgeIcon}
            </div>

            {/* Info */}
            <div className="flex-1">
              <h3 className="text-xl font-bold text-white mb-2">
                {tab.title}
              </h3>
              <p className="text-gray-400 mb-4 leading-relaxed">
                {tab.description}
              </p>
              <div className="flex flex-wrap gap-2">
                {tab.features.map((feat, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 text-sm bg-green-600/[0.08] text-green-600 border border-green-600/20 rounded-full px-3 py-1"
                  >
                    <span className="text-green-600 font-bold">&#x2713;</span>
                    {feat}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
        <GetStartedCTA />
      </div>
    </section>
  );
}
