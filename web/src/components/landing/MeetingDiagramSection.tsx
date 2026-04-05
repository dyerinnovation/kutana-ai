import { useState, useEffect, useCallback, useRef } from "react";

/* ------------------------------------------------------------------ */
/*  Stage data                                                         */
/* ------------------------------------------------------------------ */

interface ContextTag {
  text: string;
  teal: boolean;
}

interface StageData {
  num: string;
  label: string;
  feeds: number[];
  agents: number[];
  flowIn: number[];
  flowOut: number[];
  speaking: string | null;
  meetingActive: boolean;
  contextTags: ContextTag[];
}

const stages: StageData[] = [
  {
    num: "1",
    label:
      "First, Feeds Push Meeting Context (e.g. Relevant Background, Tickets, Planning Notes) into the Meeting Platform",
    feeds: [0, 1, 2, 3],
    agents: [],
    flowIn: [0, 1, 2, 3],
    flowOut: [],
    speaking: null,
    meetingActive: false,
    contextTags: [],
  },
  {
    num: "2",
    label: "Humans and Agents Join the Meeting",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [],
    speaking: null,
    meetingActive: true,
    contextTags: [
      { text: "Slack: 14 msgs", teal: false },
      { text: "Notion: Sprint doc", teal: false },
      { text: "GitHub: 7 PRs", teal: false },
    ],
  },
  {
    num: "3",
    label:
      "Humans and Agents Interact in the Meeting as Usual \u2014 Messaging and Speaking",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [],
    speaking: "claude",
    meetingActive: true,
    contextTags: [
      { text: "Slack: 14 msgs", teal: false },
      { text: "Notion: Sprint doc", teal: false },
      { text: "GitHub: 7 PRs", teal: false },
    ],
  },
  {
    num: "3",
    label:
      "Humans and Agents Interact in the Meeting as Usual \u2014 Messaging and Speaking",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [],
    speaking: "human1",
    meetingActive: true,
    contextTags: [
      { text: "Slack: 14 msgs", teal: false },
      { text: "Notion: Sprint doc", teal: false },
      { text: "GitHub: 7 PRs", teal: false },
    ],
  },
  {
    num: "3",
    label:
      "Humans and Agents Interact in the Meeting as Usual \u2014 Messaging and Speaking",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [],
    speaking: "managed",
    meetingActive: true,
    contextTags: [
      { text: "Slack: 14 msgs", teal: false },
      { text: "Notion: Sprint doc", teal: false },
      { text: "GitHub: 7 PRs", teal: false },
    ],
  },
  {
    num: "3",
    label:
      "Humans and Agents Interact in the Meeting as Usual \u2014 Messaging and Speaking",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [],
    speaking: "human2",
    meetingActive: true,
    contextTags: [
      { text: "Slack: 14 msgs", teal: false },
      { text: "Notion: Sprint doc", teal: false },
      { text: "GitHub: 7 PRs", teal: false },
    ],
  },
  {
    num: "4",
    label:
      "The Outcomes of the Meeting are Enriched by Kutana Agents and Sent to Feeds, Humans, and Agents Alike",
    feeds: [],
    agents: [0, 1, 2],
    flowIn: [],
    flowOut: [0, 1, 2],
    speaking: null,
    meetingActive: true,
    contextTags: [
      { text: "Actions: 5 items", teal: true },
      { text: "Decisions: 3", teal: true },
      { text: "Summary ready", teal: true },
      { text: "Pushed to Feeds", teal: true },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  SVG Icons                                                          */
/* ------------------------------------------------------------------ */

const SlackIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <path
      d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"
      fill="#E01E5A"
    />
    <path
      d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z"
      fill="#36C5F0"
    />
    <path
      d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.522 2.521 2.528 2.528 0 0 1-2.52-2.521V2.522A2.528 2.528 0 0 1 15.165 0a2.528 2.528 0 0 1 2.521 2.522v6.312z"
      fill="#2EB67D"
    />
    <path
      d="M15.165 18.956a2.528 2.528 0 0 1 2.521 2.522A2.528 2.528 0 0 1 15.165 24a2.528 2.528 0 0 1-2.521-2.522v-2.522h2.521zm0-1.27a2.528 2.528 0 0 1-2.521-2.522 2.528 2.528 0 0 1 2.521-2.52h6.313A2.528 2.528 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.521h-6.313z"
      fill="#ECB22E"
    />
  </svg>
);

const NotionIcon = () => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="text-white/80"
  >
    <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.887l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.279v-6.44l-1.215-.139c-.093-.514.28-.887.747-.933zM1.936 1.035l13.31-.98c1.634-.14 2.055-.047 3.082.7l4.249 2.986c.7.513.934.653.934 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.839.374-1.54 1.447-1.632z" />
  </svg>
);

const GitHubIcon = () => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="text-white/80"
  >
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
  </svg>
);

const DiscordIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="#5865F2">
    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
  </svg>
);

const AnthropicIcon = ({
  size = 18,
  className = "",
}: {
  size?: number;
  className?: string;
}) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    width={size}
    height={size}
    className={className}
  >
    <path d="M14.18 3h-4.36L4 21h3.82l1.27-3.56h5.82L16.18 21H20L14.18 3zm-4.07 11.44 1.89-5.3 1.89 5.3H10.11z" />
  </svg>
);

const OpenClawIcon = ({
  size = 18,
  className = "",
}: {
  size?: number;
  className?: string;
}) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    width={size}
    height={size}
    className={className}
  >
    <circle cx="12" cy="12" r="8" />
    <path d="M12 4 C8 4 6 8 6 12" />
    <path d="M12 4 C16 4 18 8 18 12" />
    <path d="M9 16 L12 20 L15 16" />
  </svg>
);

const PersonIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    width={18}
    height={18}
  >
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const LayersIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    width={18}
    height={18}
  >
    <path d="M12 2L2 7l10 5 10-5-10-5z" />
    <path d="M2 17l10 5 10-5" />
    <path d="M2 12l10 5 10-5" />
  </svg>
);

const BotIcon = ({
  size = 20,
  className = "",
}: {
  size?: number;
  className?: string;
}) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    width={size}
    height={size}
    className={className}
  >
    <rect x="3" y="8" width="18" height="12" rx="2" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    <circle cx="9" cy="14" r="1.5" fill="currentColor" />
    <circle cx="15" cy="14" r="1.5" fill="currentColor" />
    <path d="M9 18h6" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

const feedItems = [
  { icon: <SlackIcon />, label: "Slack" },
  { icon: <NotionIcon />, label: "Notion" },
  { icon: <GitHubIcon />, label: "GitHub" },
  { icon: <DiscordIcon />, label: "Discord" },
];

const agentItems = [
  {
    icon: <AnthropicIcon size={20} className="text-teal-500/85" />,
    label: "Claude Code",
  },
  {
    icon: <OpenClawIcon size={20} className="text-teal-500/85" />,
    label: "OpenClaw Agents",
  },
  {
    icon: <BotIcon size={20} className="text-teal-500/85" />,
    label: "Other Agents",
  },
];

const protocolLabels = ["Channel", "OpenClaw Skills", "MCP / API / CLI"];

const managedAgents = [
  {
    name: "Meeting Scribe",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={16}
        height={16}
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M16 13H8m8 4H8" />
      </svg>
    ),
  },
  {
    name: "Action Tracker",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={16}
        height={16}
      >
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    name: "Context Builder",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        width={16}
        height={16}
      >
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    ),
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MeetingDiagramSection() {
  const [current, setCurrent] = useState(0);
  const pausedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const goTo = useCallback((idx: number) => {
    setCurrent(idx);
  }, []);

  // Auto-rotation
  useEffect(() => {
    timerRef.current = setInterval(() => {
      if (!pausedRef.current) {
        setCurrent((prev) => (prev + 1) % stages.length);
      }
    }, 4000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const handleDotClick = useCallback(
    (idx: number) => {
      goTo(idx);
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        if (!pausedRef.current) {
          setCurrent((prev) => (prev + 1) % stages.length);
        }
      }, 4000);
    },
    [goTo],
  );

  const stage = stages[current];

  return (
    <>
      <style>{`
        @keyframes md-flow-right {
          0%   { left: -100%; }
          100% { left: 100%; }
        }
        @keyframes md-flow-left {
          0%   { right: -100%; }
          100% { right: 100%; }
        }
        @keyframes md-live-blink {
          0%, 100% { opacity: 1; }
          50%      { opacity: 0.35; }
        }
        @keyframes md-orb-human {
          0%, 100% { box-shadow: 0 0 6px rgba(148,163,184,0.3); }
          50%      { box-shadow: 0 0 18px rgba(148,163,184,0.7), 0 0 30px rgba(148,163,184,0.2); }
        }
        @keyframes md-orb-purple {
          0%, 100% { box-shadow: 0 0 8px rgba(124,58,237,0.4); }
          50%      { box-shadow: 0 0 22px rgba(124,58,237,0.9), 0 0 40px rgba(124,58,237,0.3); }
        }

        .md-flow-line {
          position: relative;
          overflow: hidden;
        }
        .md-flow-line::after {
          content: '';
          position: absolute;
          top: 0;
          width: 100%;
          height: 100%;
          opacity: 0;
          transition: opacity 0.4s ease;
        }
        .md-flow-in::after {
          left: -100%;
          background: linear-gradient(90deg, transparent 0%, transparent 30%, #16a34a 50%, transparent 70%, transparent 100%);
        }
        .md-flow-out::after {
          right: -100%;
          left: auto;
          background: linear-gradient(90deg, transparent 0%, transparent 30%, #14b8a6 50%, transparent 70%, transparent 100%);
        }
        .md-flow-line.md-flowing::after {
          opacity: 1;
        }
        .md-flow-in.md-flowing::after {
          animation: md-flow-right 1.2s linear infinite;
        }
        .md-flow-out.md-flowing::after {
          animation: md-flow-left 1.2s linear infinite;
        }
        .md-flow-line.md-flowing {
          background: repeating-linear-gradient(
            90deg,
            rgba(255,255,255,0.05) 0px,
            rgba(255,255,255,0.05) 4px,
            transparent 4px,
            transparent 10px
          );
        }
        .md-speaking-human {
          border-color: rgba(148, 163, 184, 0.7) !important;
          animation: md-orb-human 1.5s ease-in-out infinite;
        }
        .md-speaking-agent-purple {
          border-color: rgba(124, 58, 237, 0.9) !important;
          animation: md-orb-purple 1.2s ease-in-out infinite;
        }
      `}</style>

      <section className="py-24 px-4" id="how-it-works">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-center text-3xl sm:text-4xl font-bold mb-4 text-white">
            How a Kutana Meeting Works
          </h2>
          <p className="text-center text-gray-400 mb-10 text-lg">
            Feeds push context in.{" "}
            <span className="whitespace-nowrap">AI&nbsp;Agents</span> connect
            and participate. Enriched context flows back out.
          </p>

          <div
            className="max-w-[1280px] mx-auto"
            onMouseEnter={() => {
              pausedRef.current = true;
            }}
            onMouseLeave={() => {
              pausedRef.current = false;
            }}
          >
            {/* Stage label */}
            <div className="flex justify-center mb-8 min-h-[72px] items-center">
              <div className="flex items-center gap-4 bg-teal-500/[0.08] border border-teal-500/20 px-7 py-4 rounded-2xl max-w-[900px] w-full transition-all duration-400">
                <span className="inline-flex items-center justify-center w-10 h-10 bg-teal-500/25 rounded-full text-lg font-extrabold shrink-0 text-teal-500">
                  {stage.num}
                </span>
                <span className="text-[clamp(1.1rem,2.5vw,2rem)] font-semibold text-white/[0.92] leading-tight">
                  {stage.label}
                </span>
              </div>
            </div>

            {/* Main 5-column grid */}
            <div className="md-main-grid grid grid-cols-[200px_72px_1fr_72px_200px] items-center min-h-[380px] max-[900px]:grid-cols-[150px_52px_1fr_52px_150px] max-[700px]:grid-cols-[100px_40px_1fr_40px_100px] max-[540px]:flex max-[540px]:flex-col max-[540px]:items-stretch max-[540px]:gap-4">
              {/* LEFT: Feeds group */}
              <div className="border border-green-600/25 bg-green-600/[0.04] rounded-2xl p-[10px_8px_12px] flex flex-col relative">
                <div className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-center mb-2.5 pb-2 border-b border-white/[0.06] text-green-600/70">
                  Feeds
                </div>
                <div className="flex flex-col gap-2 max-[540px]:flex-row max-[540px]:justify-center max-[540px]:flex-wrap">
                  {feedItems.map((feed, i) => (
                    <div
                      key={i}
                      className={`bg-slate-800/70 border rounded-lg p-[8px_6px] text-center cursor-pointer transition-all duration-300 ${
                        stage.feeds.includes(i)
                          ? "border-green-600 bg-green-600/[0.12] shadow-[0_0_14px_rgba(22,163,74,0.25)]"
                          : "border-white/[0.08] hover:border-green-600/50 hover:bg-green-600/[0.08]"
                      } max-[540px]:min-w-[60px]`}
                    >
                      <div className="flex justify-center items-center mb-1 text-green-600">
                        {feed.icon}
                      </div>
                      <div className="text-[0.65rem] text-white/50 whitespace-nowrap overflow-hidden text-ellipsis max-[700px]:hidden">
                        {feed.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Feed flow lines */}
              <div className="flex flex-col gap-2.5 px-0.5 self-stretch justify-around max-[540px]:hidden">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={`md-flow-line md-flow-in h-[3px] rounded-sm bg-white/[0.06] ${
                      stage.flowIn.includes(i) ? "md-flowing" : ""
                    }`}
                  />
                ))}
              </div>

              {/* CENTER: Meeting box */}
              <div className="px-2">
                <div
                  className={`bg-slate-950/95 border rounded-2xl overflow-hidden transition-all duration-400 ${
                    stage.meetingActive
                      ? "border-green-600 shadow-[0_0_30px_rgba(22,163,74,0.15)]"
                      : "border-green-600/25"
                  }`}
                >
                  {/* Header bar */}
                  <div className="flex items-center gap-[5px] py-2 px-3 bg-slate-800/80 border-b border-white/[0.07]">
                    <div className="w-2 h-2 rounded-full bg-[#ff5f57]" />
                    <div className="w-2 h-2 rounded-full bg-[#febc2e]" />
                    <div className="w-2 h-2 rounded-full bg-[#28c840]" />
                    <span className="text-[0.65rem] text-white/50 flex-1 text-center">
                      Sprint Planning &middot; Kutana AI
                    </span>
                    <span
                      className="text-[0.6rem] font-bold text-green-600"
                      style={{ animation: "md-live-blink 2s ease-in-out infinite" }}
                    >
                      &#x25CF; LIVE
                    </span>
                  </div>

                  {/* Body */}
                  <div className="p-2.5">
                    {/* Participants grid */}
                    <div className="flex flex-col gap-1 mb-2">
                      <div className="text-[0.52rem] font-bold uppercase tracking-[0.08em] text-white/25 text-left px-0.5 pb-0.5">
                        Humans
                      </div>
                      <div className="flex gap-1 justify-center">
                        <Participant
                          name="Jordan"
                          icon={<PersonIcon />}
                          speaking={stage.speaking === "human1"}
                          speakingClass="md-speaking-human"
                          bubble="\u201CWhat\u2019s the Sprint 42 status?\u201D"
                          bubbleClass="border-slate-400/35"
                          isAgent={false}
                        />
                        <Participant
                          name="Sarah"
                          icon={<PersonIcon />}
                          speaking={stage.speaking === "human2"}
                          speakingClass="md-speaking-human"
                          bubble="\u201CI can take the API layer.\u201D"
                          bubbleClass="border-slate-400/35"
                          isAgent={false}
                        />
                        <Participant
                          name="Alex"
                          icon={<PersonIcon />}
                          speaking={false}
                          speakingClass=""
                          isAgent={false}
                        />
                      </div>

                      <div className="text-[0.52rem] font-bold uppercase tracking-[0.08em] text-white/25 text-left px-0.5 pb-0.5 mt-1.5">
                        Agents
                      </div>
                      <div className="flex gap-1 justify-center">
                        <Participant
                          name="Claude Code"
                          icon={<AnthropicIcon />}
                          speaking={stage.speaking === "claude"}
                          speakingClass="md-speaking-agent-purple"
                          bubble="\u201CAuth refactor = 5 pts based on velocity\u201D"
                          bubbleClass="border-violet-600/45"
                          isAgent
                        />
                        <Participant
                          name="Scribe"
                          icon={<LayersIcon />}
                          speaking={stage.speaking === "managed"}
                          speakingClass="md-speaking-agent-purple"
                          bubble="\u201CLogging 3 action items so far\u201D"
                          bubbleClass="border-violet-600/45"
                          isAgent
                        />
                        <Participant
                          name="OpenClaw"
                          icon={<OpenClawIcon />}
                          speaking={false}
                          speakingClass=""
                          isAgent
                        />
                      </div>
                    </div>

                    {/* Context strip */}
                    {stage.contextTags.length > 0 && (
                      <div className="bg-green-600/[0.05] border-t border-green-600/10 rounded-b-lg px-2.5 py-1.5 flex flex-wrap gap-1 items-center min-h-[26px]">
                        {stage.contextTags.map((tag, i) => (
                          <span
                            key={i}
                            className={`text-[0.58rem] px-1.5 py-0.5 rounded-[3px] ${
                              tag.teal
                                ? "bg-teal-500/[0.12] text-teal-500/85"
                                : "bg-green-600/[0.12] text-lime-400/85"
                            }`}
                          >
                            {tag.text}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent flow lines (with protocol labels) */}
              <div className="flex flex-col gap-2.5 px-0.5 self-stretch justify-around max-[540px]:hidden">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="relative flex flex-col items-stretch gap-[3px]">
                    <div className="text-[0.5rem] font-bold uppercase tracking-[0.07em] text-teal-500/75 text-center whitespace-nowrap leading-none max-[700px]:hidden">
                      {protocolLabels[i]}
                    </div>
                    <div
                      className={`md-flow-line md-flow-out h-[3px] rounded-sm bg-white/[0.06] ${
                        stage.flowOut.includes(i) ? "md-flowing" : ""
                      }`}
                    />
                  </div>
                ))}
              </div>

              {/* RIGHT: Custom Agents group */}
              <div className="border border-teal-500/25 bg-teal-500/[0.04] rounded-2xl p-[10px_8px_12px] flex flex-col relative">
                <div className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-center mb-2.5 pb-2 border-b border-white/[0.06] text-teal-500/70">
                  Custom Agents
                </div>
                <div className="flex flex-col gap-2 max-[540px]:flex-row max-[540px]:justify-center max-[540px]:flex-wrap">
                  {agentItems.map((agent, i) => (
                    <div
                      key={i}
                      className={`bg-slate-800/70 border rounded-lg p-[8px_6px] text-center cursor-pointer transition-all duration-300 ${
                        stage.agents.includes(i)
                          ? "border-teal-500 bg-teal-500/[0.12] shadow-[0_0_14px_rgba(20,184,166,0.25)]"
                          : "border-white/[0.08] hover:border-teal-500/50 hover:bg-teal-500/[0.08]"
                      } max-[540px]:min-w-[60px]`}
                    >
                      <div className="flex justify-center items-center mb-1 text-teal-500">
                        {agent.icon}
                      </div>
                      <div className="text-[0.65rem] text-white/50 whitespace-nowrap overflow-hidden text-ellipsis max-[700px]:hidden">
                        {agent.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Kutana Managed Agents row (below diagram) */}
            <div className="grid grid-cols-[200px_72px_1fr_72px_200px] gap-0 mt-2.5 max-[900px]:grid-cols-[150px_52px_1fr_52px_150px] max-[700px]:grid-cols-[100px_40px_1fr_40px_100px] max-[540px]:block max-[540px]:mt-0">
              <div />
              <div />
              <div className="px-2">
                <div className="bg-violet-600/[0.06] border border-violet-600/20 rounded-lg py-2 px-2.5">
                  <div className="flex justify-center mb-1 text-violet-600/50 text-base leading-none">
                    &#x2503;
                  </div>
                  <span className="text-[0.62rem] font-bold uppercase tracking-[0.1em] text-violet-400/70 text-center block mb-2 pb-1.5 border-b border-violet-600/[0.12]">
                    Kutana Managed Agents
                  </span>
                  <div className="flex gap-1.5 justify-center">
                    {managedAgents.map((ma, i) => (
                      <div
                        key={i}
                        className="flex-1 text-center py-1.5 px-1 bg-violet-600/[0.08] rounded-md border border-violet-600/15"
                      >
                        <div className="text-violet-400/75 flex justify-center mb-[3px]">
                          {ma.icon}
                        </div>
                        <div className="text-[0.55rem] text-violet-400/65 font-semibold leading-tight max-[700px]:hidden">
                          {ma.name}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div />
              <div />
            </div>

            {/* Stage navigation dots */}
            <div className="flex justify-center gap-2 mt-8">
              {stages.map((_, i) => (
                <button
                  key={i}
                  aria-label={`Stage ${i + 1}`}
                  onClick={() => handleDotClick(i)}
                  className={`w-2.5 h-2.5 rounded-full border-none p-0 cursor-pointer transition-all duration-300 ${
                    i === current
                      ? "bg-teal-500 shadow-[0_0_10px_rgba(20,184,166,0.5)] scale-[1.2]"
                      : "bg-white/15 hover:bg-white/30"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Participant tile                                                   */
/* ------------------------------------------------------------------ */

interface ParticipantProps {
  name: string;
  icon: React.ReactNode;
  speaking: boolean;
  speakingClass: string;
  bubble?: string;
  bubbleClass?: string;
  isAgent: boolean;
}

function Participant({
  name,
  icon,
  speaking,
  speakingClass,
  bubble,
  bubbleClass,
  isAgent,
}: ParticipantProps) {
  return (
    <div className="flex-1 flex flex-col items-center gap-1 relative p-[8px_4px] rounded-md cursor-pointer transition-colors duration-300 hover:bg-white/[0.03]">
      {/* Bubble */}
      {bubble && (
        <div
          className={`absolute bottom-[calc(100%+6px)] left-1/2 bg-slate-950/[0.98] border rounded-[10px] px-2.5 py-1.5 text-[0.65rem] text-white/90 whitespace-nowrap z-20 transition-all duration-400 max-[700px]:whitespace-normal max-[700px]:max-w-[110px] max-[700px]:text-center max-[700px]:text-[0.6rem] ${bubbleClass ?? ""} ${
            speaking
              ? "opacity-100 -translate-x-1/2 translate-y-0"
              : "opacity-0 -translate-x-1/2 translate-y-1.5 pointer-events-none"
          }`}
        >
          <span>{bubble}</span>
          <div
            className={`absolute bottom-[-5px] w-2 h-2 rotate-45 bg-slate-950/[0.98] ${
              isAgent
                ? "left-3.5 border-r border-b border-violet-600/45"
                : "right-3.5 border-r border-b border-slate-400/35"
            }`}
          />
        </div>
      )}

      {/* Orb */}
      <div className="relative w-[42px] h-[42px]">
        <div
          className={`absolute inset-[-5px] rounded-full border-2 border-transparent z-[2] pointer-events-none transition-all duration-400 ${
            speaking ? speakingClass : ""
          }`}
        />
        <div
          className={`absolute inset-0 rounded-full flex items-center justify-center transition-all duration-400 ${
            isAgent
              ? "bg-violet-600/10 border border-violet-600/35 text-violet-400/90"
              : "bg-slate-800/90 border border-white/10 text-slate-400/80"
          }`}
        >
          {icon}
        </div>
      </div>

      <div className="text-[0.6rem] text-white/45 text-center whitespace-nowrap">
        {name}
      </div>
    </div>
  );
}
