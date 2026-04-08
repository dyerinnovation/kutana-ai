import { useState, useEffect, useCallback, useRef, useMemo } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ContextTag {
  text: string;
  teal: boolean;
}

interface BubbleText {
  target: "claude" | "human3";
  html: string;
}

interface StageData {
  num: string;
  label: string;
  feeds: number[];
  agents: number[];
  flowIn: number[];
  flowOut: number[];
  humanFlow: boolean;
  speaking: string | null;
  meetingActive: boolean;
  managedFlowing: boolean;
  humansHighlight: boolean;
  contextTags: ContextTag[];
  bubbleText?: BubbleText;
}

/* ------------------------------------------------------------------ */
/*  SVG Icons                                                          */
/* ------------------------------------------------------------------ */

const SlackIcon = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A" />
    <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0" />
    <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.522 2.521 2.528 2.528 0 0 1-2.52-2.521V2.522A2.528 2.528 0 0 1 15.165 0a2.528 2.528 0 0 1 2.521 2.522v6.312z" fill="#2EB67D" />
    <path d="M15.165 18.956a2.528 2.528 0 0 1 2.521 2.522A2.528 2.528 0 0 1 15.165 24a2.528 2.528 0 0 1-2.521-2.522v-2.522h2.521zm0-1.27a2.528 2.528 0 0 1-2.521-2.522 2.528 2.528 0 0 1 2.521-2.52h6.313A2.528 2.528 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.521h-6.313z" fill="#ECB22E" />
  </svg>
);

const NotionIcon = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className="text-white/80">
    <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.887l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.279v-6.44l-1.215-.139c-.093-.514.28-.887.747-.933zM1.936 1.035l13.31-.98c1.634-.14 2.055-.047 3.082.7l4.249 2.986c.7.513.934.653.934 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.839.374-1.54 1.447-1.632z" />
  </svg>
);

const GitHubIcon = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className="text-white/80">
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
  </svg>
);

const DiscordIcon = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="#5865F2">
    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
  </svg>
);

const ClaudeLogoIcon = ({ size = 24 }: { size?: number }) => (
  <svg viewBox="0 0 1200 1200" width={size} height={size} aria-label="Claude">
    <path fill="#d97757" d="M 233.959793 800.214905 L 468.644287 668.536987 L 472.590637 657.100647 L 468.644287 650.738403 L 457.208069 650.738403 L 417.986633 648.322144 L 283.892639 644.69812 L 167.597321 639.865845 L 54.926208 633.825623 L 26.577238 627.785339 L 3.3e-05 592.751709 L 2.73832 575.27533 L 26.577238 559.248352 L 60.724873 562.228149 L 136.187973 567.382629 L 249.422867 575.194763 L 331.570496 580.026978 L 453.261841 592.671082 L 472.590637 592.671082 L 475.328857 584.859009 L 468.724915 580.026978 L 463.570557 575.194763 L 346.389313 495.785217 L 219.543671 411.865906 L 153.100723 363.543762 L 117.181267 339.060425 L 99.060455 316.107361 L 91.248367 266.01355 L 123.865784 230.093994 L 167.677887 233.073853 L 178.872513 236.053772 L 223.248367 270.201477 L 318.040283 343.570496 L 441.825592 434.738342 L 459.946411 449.798706 L 467.194672 444.64447 L 468.080597 441.020203 L 459.946411 427.409485 L 392.617493 305.718323 L 320.778564 181.932983 L 288.80542 130.630859 L 280.348999 99.865845 C 277.369171 87.221436 275.194641 76.590698 275.194641 63.624268 L 312.322174 13.20813 L 332.8591 6.604126 L 382.389313 13.20813 L 403.248352 31.328979 L 434.013519 101.71814 L 483.865753 212.537048 L 561.181274 363.221497 L 583.812134 407.919434 L 595.892639 449.315491 L 600.40271 461.959839 L 608.214783 461.959839 L 608.214783 454.711609 L 614.577271 369.825623 L 626.335632 265.61084 L 637.771851 131.516846 L 641.718201 93.745117 L 660.402832 48.483276 L 697.530334 24.000122 L 726.52356 37.852417 L 750.362549 72 L 747.060486 94.067139 L 732.886047 186.201416 L 705.100708 330.52356 L 686.979919 427.167847 L 697.530334 427.167847 L 709.61084 415.087341 L 758.496704 350.174561 L 840.644348 247.490051 L 876.885925 206.738342 L 919.167847 161.71814 L 946.308838 140.29541 L 997.61084 140.29541 L 1035.38269 196.429626 L 1018.469849 254.416199 L 965.637634 321.422852 L 921.825562 378.201538 L 859.006714 462.765259 L 819.785278 530.41626 L 823.409424 535.812073 L 832.75177 534.92627 L 974.657776 504.724915 L 1051.328979 490.872559 L 1142.818848 475.167786 L 1184.214844 494.496582 L 1188.724854 514.147644 L 1172.456421 554.335693 L 1074.604126 578.496765 L 959.838989 601.449829 L 788.939636 641.879272 L 786.845764 643.409485 L 789.261841 646.389343 L 866.255127 653.637634 L 899.194702 655.409424 L 979.812134 655.409424 L 1129.932861 666.604187 L 1169.154419 692.537109 L 1192.671265 724.268677 L 1188.724854 748.429688 L 1128.322144 779.194641 L 1046.818848 759.865845 L 856.590759 714.604126 L 791.355774 698.335754 L 782.335693 698.335754 L 782.335693 703.731567 L 836.69812 756.885986 L 936.322205 846.845581 L 1061.073975 962.81897 L 1067.436279 991.490112 L 1051.409424 1014.120911 L 1034.496704 1011.704712 L 924.885986 929.234924 L 882.604126 892.107544 L 786.845764 811.48999 L 780.483276 811.48999 L 780.483276 819.946289 L 802.550415 852.241699 L 919.087341 1027.409424 L 925.127625 1081.127686 L 916.671204 1098.604126 L 886.469849 1109.154419 L 853.288696 1103.114136 L 785.073914 1007.355835 L 714.684631 899.516785 L 657.906067 802.872498 L 650.979858 806.81897 L 617.476624 1167.704834 L 601.771851 1186.147705 L 565.530212 1200 L 535.328857 1177.046997 L 519.302124 1139.919556 L 535.328857 1066.550537 L 554.657776 970.792053 L 570.362488 894.68457 L 584.536926 800.134277 L 592.993347 768.724976 L 592.429626 766.630859 L 585.503479 767.516968 L 514.22821 865.369263 L 405.825531 1011.865906 L 320.053711 1103.677979 L 299.516815 1111.812256 L 263.919525 1093.369263 L 267.221497 1060.429688 L 287.114136 1031.114136 L 405.825531 880.107361 L 477.422913 786.52356 L 523.651062 732.483276 L 523.328918 724.671265 L 520.590698 724.671265 L 205.288605 929.395935 L 149.154434 936.644409 L 124.993355 914.01355 L 127.973183 876.885986 L 139.409409 864.80542 L 234.201385 799.570435 L 233.879227 799.8927 Z" />
  </svg>
);

const OpenClawIcon = ({ size = 26 }: { size?: number }) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" width={size} height={size} aria-label="OpenClaw" role="img">
    <defs>
      <linearGradient id="oc-lobster-md" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#ff4d4d" />
        <stop offset="100%" stopColor="#991b1b" />
      </linearGradient>
    </defs>
    <path d="M60 10 C30 10 15 35 15 55 C15 75 30 95 45 100 L45 110 L55 110 L55 100 C55 100 60 102 65 100 L65 110 L75 110 L75 100 C90 95 105 75 105 55 C105 35 90 10 60 10Z" fill="url(#oc-lobster-md)" />
    <path d="M20 45 C5 40 0 50 5 60 C10 70 20 65 25 55 C28 48 25 45 20 45Z" fill="url(#oc-lobster-md)" />
    <path d="M100 45 C115 40 120 50 115 60 C110 70 100 65 95 55 C92 48 95 45 100 45Z" fill="url(#oc-lobster-md)" />
    <path d="M45 15 Q35 5 30 8" stroke="#ff4d4d" strokeWidth="3" strokeLinecap="round" />
    <path d="M75 15 Q85 5 90 8" stroke="#ff4d4d" strokeWidth="3" strokeLinecap="round" />
    <circle cx="45" cy="35" r="6" fill="#050810" />
    <circle cx="75" cy="35" r="6" fill="#050810" />
    <circle cx="46" cy="34" r="2.5" fill="#00e5cc" />
    <circle cx="76" cy="34" r="2.5" fill="#00e5cc" />
  </svg>
);

const PersonIcon = ({ size = 24 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={size} height={size}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const PersonIconSmall = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={20} height={20}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const BotIcon = ({ size = 24 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={size} height={size} style={{ color: "rgba(167,139,250,0.85)" }}>
    <rect x="3" y="8" width="18" height="12" rx="2" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    <circle cx="9" cy="14" r="1.5" fill="currentColor" />
    <circle cx="15" cy="14" r="1.5" fill="currentColor" />
    <path d="M9 18h6" />
  </svg>
);

const BotIconAgent = ({ size = 26 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={size} height={size} style={{ color: "rgba(20,184,166,0.85)" }}>
    <rect x="3" y="8" width="18" height="12" rx="2" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    <circle cx="9" cy="14" r="1.5" fill="currentColor" />
    <circle cx="15" cy="14" r="1.5" fill="currentColor" />
    <path d="M9 18h6" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Render label with markdown-style bold                              */
/* ------------------------------------------------------------------ */

function renderLabel(label: string): React.ReactNode {
  // **G:text** => green bold, **T:text** => teal bold, **text** => lime bold
  const parts: React.ReactNode[] = [];
  let remaining = label;
  let key = 0;

  const regex = /\*\*(?:([GT]):)?([^*]+)\*\*/;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(remaining)) !== null) {
    const before = remaining.slice(0, match.index);
    if (before) parts.push(<span key={key++}>{before}</span>);

    const prefix = match[1];
    const text = match[2];
    let colorClass = "text-lime-400"; // default
    if (prefix === "G") colorClass = "text-green-500";
    if (prefix === "T") colorClass = "text-teal-500";

    parts.push(
      <strong key={key++} className={`${colorClass} font-extrabold`}>
        {text}
      </strong>
    );

    remaining = remaining.slice(match.index + match[0].length);
  }

  if (remaining) parts.push(<span key={key++}>{remaining}</span>);
  return parts;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MeetingDiagramSection() {
  /* ---------- Stage data ---------- */
  const stages = useMemo<StageData[]>(
    () => [
      {
        label: "First, **G:Feeds** Push Background Context into the **T:Meeting**",
        num: "1",
        feeds: [0, 1, 2, 3],
        agents: [],
        flowIn: [0, 1, 2, 3],
        flowOut: [],
        humanFlow: false,
        speaking: null,
        meetingActive: false,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Both** Join the Meeting",
        num: "2",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [0, 1, 2],
        humanFlow: true,
        speaking: null,
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: true,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "human1",
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "human3",
        bubbleText: { target: "human3", html: "\u201CAlexClaw can you\ngive an update?\u201D" },
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "claude",
        bubbleText: { target: "claude", html: "\u201CAlmost completed,\nJust the API and Auth Remain\u201D" },
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "human2",
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "managed",
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "human3",
        bubbleText: { target: "human3", html: "\u201CGot it, AlexClaw let\u2019s\ngo right into execution\u201D" },
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Humans and Agents **Message and Speak** As Usual",
        num: "3",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: "claude",
        bubbleText: { target: "claude", html: "\u201COn it, starting the API\nwhen done here\u201D" },
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
        ],
      },
      {
        label: "Kutana Agents Transcribe, Extract Action Items, etc.",
        num: "4",
        feeds: [],
        agents: [0, 1, 2],
        flowIn: [],
        flowOut: [],
        humanFlow: false,
        speaking: null,
        meetingActive: true,
        managedFlowing: true,
        humansHighlight: false,
        contextTags: [
          { text: "Slack: 14 msgs", teal: false },
          { text: "Notion: Sprint doc", teal: false },
          { text: "GitHub: 7 PRs", teal: false },
          { text: "Tracking\u2026", teal: true },
        ],
      },
      {
        label: "Enriched Meeting Context is Delivered to Feeds, Agents, and Humans",
        num: "5",
        feeds: [0, 1, 2, 3],
        agents: [0, 1, 2],
        flowIn: [0, 1, 2, 3],
        flowOut: [0, 1, 2],
        humanFlow: true,
        speaking: null,
        meetingActive: true,
        managedFlowing: false,
        humansHighlight: true,
        contextTags: [
          { text: "Actions: 5 items", teal: true },
          { text: "Decisions: 3", teal: true },
          { text: "Summary ready", teal: true },
        ],
      },
    ],
    []
  );

  /* ---------- State ---------- */
  const [current, setCurrent] = useState(0);
  const [claudeBubbleText, setClaudeBubbleText] = useState("\u201CAlmost completed,\nJust the API and Auth Remain\u201D");
  const [human3BubbleText, setHuman3BubbleText] = useState("\u201CAlexClaw can you\ngive an update?\u201D");
  const pausedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inViewRef = useRef(false);
  const startedRef = useRef(false);

  const stage = stages[current];

  /* ---------- Flow line alignment refs ---------- */
  const feedColRef = useRef<HTMLDivElement>(null);
  const flowInColRef = useRef<HTMLDivElement>(null);
  const agentColRef = useRef<HTMLDivElement>(null);
  const flowOutColRef = useRef<HTMLDivElement>(null);

  const alignFlowLines = useCallback(() => {
    const feedNodes = feedColRef.current?.querySelectorAll<HTMLElement>("[data-feed-node]");
    const flowInCol = flowInColRef.current;
    const feedLines = flowInCol?.querySelectorAll<HTMLElement>("[data-flow-in]");
    if (flowInCol && feedNodes && feedLines && feedNodes.length > 0) {
      const first = feedNodes[0].getBoundingClientRect();
      const last = feedNodes[feedNodes.length - 1].getBoundingClientRect();
      flowInCol.style.height = `${last.bottom - first.top}px`;
      const colRect = flowInCol.getBoundingClientRect();
      feedLines.forEach((line, i) => {
        if (feedNodes[i]) {
          const nodeRect = feedNodes[i].getBoundingClientRect();
          const centerY = nodeRect.top + nodeRect.height / 2;
          line.style.top = `${centerY - colRect.top - 1.5}px`;
        }
      });
    }
    const agentNodes = agentColRef.current?.querySelectorAll<HTMLElement>("[data-agent-node]");
    const flowOutCol = flowOutColRef.current;
    const agentWraps = flowOutCol?.querySelectorAll<HTMLElement>("[data-flow-out]");
    if (flowOutCol && agentNodes && agentWraps && agentNodes.length > 0) {
      const first = agentNodes[0].getBoundingClientRect();
      const last = agentNodes[agentNodes.length - 1].getBoundingClientRect();
      flowOutCol.style.height = `${last.bottom - first.top}px`;
      const colRect = flowOutCol.getBoundingClientRect();
      agentWraps.forEach((wrap, i) => {
        if (agentNodes[i]) {
          const nodeRect = agentNodes[i].getBoundingClientRect();
          const centerY = nodeRect.top + nodeRect.height / 2;
          const wrapH = wrap.getBoundingClientRect().height;
          wrap.style.top = `${centerY - colRect.top - wrapH / 2}px`;
        }
      });
    }
  }, []);

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(alignFlowLines);
    });
    window.addEventListener("resize", alignFlowLines);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", alignFlowLines);
    };
  }, [alignFlowLines, current]);

  /* ---------- Update dynamic bubble text ---------- */
  useEffect(() => {
    if (stage.bubbleText) {
      if (stage.bubbleText.target === "claude") {
        setClaudeBubbleText(stage.bubbleText.html);
      } else if (stage.bubbleText.target === "human3") {
        setHuman3BubbleText(stage.bubbleText.html);
      }
    }
  }, [stage]);

  /* ---------- Auto-advance with IntersectionObserver ---------- */
  const startAuto = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      if (!pausedRef.current && inViewRef.current) {
        setCurrent((prev) => (prev + 1) % stages.length);
      }
    }, 4000);
  }, [stages.length]);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && e.intersectionRatio >= 0.1) {
            inViewRef.current = true;
            if (!startedRef.current) {
              startedRef.current = true;
              startAuto();
            }
          } else {
            inViewRef.current = false;
          }
        });
      },
      { threshold: [0, 0.1, 0.35] }
    );
    io.observe(wrapper);

    return () => {
      io.disconnect();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [startAuto]);

  /* ---------- Navigation callbacks ---------- */
  const goTo = useCallback(
    (idx: number) => {
      setCurrent(idx);
      if (timerRef.current) clearInterval(timerRef.current);
      if (inViewRef.current) startAuto();
    },
    [startAuto]
  );

  const handleClickFeed = useCallback(
    (idx: number) => {
      if (timerRef.current) clearInterval(timerRef.current);
      // Find a stage where this feed is active
      const feedStage = stages.findIndex((s) => s.feeds.includes(idx));
      if (feedStage !== -1) setCurrent(feedStage);
      setTimeout(() => startAuto(), 2500);
    },
    [stages, startAuto]
  );

  const handleClickAgent = useCallback(
    (idx: number) => {
      if (timerRef.current) clearInterval(timerRef.current);
      // Find a stage where this agent is active
      const agentStage = stages.findIndex((s) => s.agents.includes(idx));
      if (agentStage !== -1) setCurrent(agentStage);
      setTimeout(() => startAuto(), 2500);
    },
    [stages, startAuto]
  );

  const handleClickHuman = useCallback(
    (humanKey: string) => {
      if (timerRef.current) clearInterval(timerRef.current);
      const humanStage = stages.findIndex((s) => s.speaking === humanKey);
      if (humanStage !== -1) setCurrent(humanStage);
      setTimeout(() => startAuto(), 2500);
    },
    [stages, startAuto]
  );

  const handleClickPurpleAgent = useCallback(
    (agentKey: string) => {
      if (timerRef.current) clearInterval(timerRef.current);
      const agentStage = stages.findIndex((s) => s.speaking === agentKey);
      if (agentStage !== -1) setCurrent(agentStage);
      setTimeout(() => startAuto(), 2500);
    },
    [stages, startAuto]
  );

  /* ---------- Feed/Agent data ---------- */
  const feedItems = useMemo(
    () => [
      { icon: <SlackIcon />, label: "Slack" },
      { icon: <NotionIcon />, label: "Notion" },
      { icon: <GitHubIcon />, label: "GitHub" },
      { icon: <DiscordIcon />, label: "Discord" },
    ],
    []
  );

  const agentConnItems = useMemo(
    () => [
      { icon: <ClaudeLogoIcon size={26} />, label: "Claude\nCode" },
      { icon: <OpenClawIcon size={28} />, label: "OpenClaw\nAgents" },
      { icon: <BotIconAgent />, label: "Other\nAgents" },
    ],
    []
  );

  const protocolLabels = ["Channel", "Skills", "MCP / CLI"];

  const isReverse = stage.num === "5";

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
        @keyframes md-vflow-down {
          0%   { top: -100%; }
          100% { top: 100%; }
        }
        @keyframes md-vflow-up {
          0%   { top: 100%; }
          100% { top: -100%; }
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
        /* Reversed direction on final stage */
        .md-flow-in.md-flowing.md-flow-reverse::after {
          animation: md-flow-left 1.2s linear infinite;
          left: auto;
          right: -100%;
          background: linear-gradient(90deg, transparent 0%, transparent 30%, #16a34a 50%, transparent 70%, transparent 100%);
        }
        .md-flow-out.md-flowing.md-flow-reverse::after {
          animation: md-flow-right 1.2s linear infinite;
          right: auto;
          left: -100%;
          background: linear-gradient(90deg, transparent 0%, transparent 30%, #14b8a6 50%, transparent 70%, transparent 100%);
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

        /* Human flow vertical lines */
        .md-human-flow-line {
          position: relative;
          overflow: hidden;
        }
        .md-human-flow-line::after {
          content: '';
          position: absolute;
          top: -100%;
          left: 0;
          width: 100%;
          height: 100%;
          background: linear-gradient(180deg, transparent 0%, rgba(148,163,184,0.9) 50%, transparent 100%);
          opacity: 0;
        }
        .md-human-flow-line.md-flowing {
          background: rgba(148, 163, 184, 0.22);
        }
        .md-human-flow-line.md-flowing::after {
          opacity: 1;
          animation: md-vflow-down 1.1s linear infinite;
        }
        .md-human-flow-line.md-flowing.md-flow-reverse::after {
          animation: md-vflow-up 1.1s linear infinite;
        }

        /* Managed agent vertical lines */
        .md-managed-vline {
          position: relative;
          overflow: hidden;
        }
        .md-managed-vline::after {
          content: '';
          position: absolute;
          top: -100%;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(124, 58, 237, 0.8);
          opacity: 0;
        }
        .md-managed-vline.md-flowing {
          background: rgba(124, 58, 237, 0.15);
        }
        .md-managed-vline.md-flowing::after {
          opacity: 1;
          animation: md-vflow-down 1s linear infinite;
        }
      `}</style>

      <section className="py-24 px-4" id="how-it-works">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-center text-3xl sm:text-4xl font-bold mb-4 text-white">
            How a Kutana Meeting Works
          </h2>
          <p className="text-center text-gray-400 mb-10 text-lg">
            Feeds push context in.{" "}
            <span className="whitespace-nowrap">AI&nbsp;Agents</span> connect and
            participate. Enriched context flows back out.
          </p>

          <div
            ref={wrapperRef}
            className="max-w-[1280px] mx-auto scroll-mt-20"
            onMouseEnter={() => {
              pausedRef.current = true;
            }}
            onMouseLeave={() => {
              pausedRef.current = false;
            }}
          >
            {/* Stage label */}
            <div className="flex justify-center mb-8 min-h-[72px] items-center">
              <div className="flex items-center gap-4 bg-teal-500/[0.08] border border-teal-500/20 px-7 py-4 rounded-2xl max-w-[900px] w-full transition-all duration-[400ms] relative z-30">
                <span className="inline-flex items-center justify-center w-10 h-10 bg-teal-500/25 rounded-full text-lg font-extrabold shrink-0 text-teal-500">
                  {stage.num}
                </span>
                <span className="text-[clamp(1.1rem,2.5vw,2rem)] font-semibold text-white/[0.92] leading-tight">
                  {renderLabel(stage.label)}
                </span>
              </div>
            </div>

            {/* Humans joining block (above meeting) */}
            <div className="grid grid-cols-[108px_92px_1fr_92px_108px] gap-0 mb-1.5 max-[900px]:grid-cols-[96px_40px_1fr_40px_96px] max-[700px]:grid-cols-[90px_36px_1fr_36px_90px] max-[540px]:hidden">
              <div />
              <div />
              <div className="px-2">
                <div
                  className={`rounded-lg p-[6px_10px_8px] transition-all duration-[600ms] overflow-hidden ${
                    stage.humansHighlight
                      ? "border border-slate-400/55 bg-slate-400/10 shadow-[0_0_20px_rgba(148,163,184,0.18)]"
                      : "border border-slate-400/15 bg-slate-800/50"
                  }`}
                >
                  <span className="text-[0.8rem] font-bold uppercase tracking-[0.1em] text-slate-400/50 text-center block mb-1.5 pb-1 border-b border-slate-400/[0.08]">
                    Humans
                  </span>
                  <div className="grid grid-cols-3 gap-1.5">
                    {(["Jordan", "Sarah", "Alex"] as const).map((name, i) => (
                      <div
                        key={name}
                        className={`text-center py-[5px] px-[3px] rounded-md border transition-all duration-300 cursor-pointer ${
                          stage.num === "2"
                            ? "border-slate-400/40 bg-slate-400/[0.12] shadow-[0_0_10px_rgba(148,163,184,0.15)]"
                            : "border-slate-400/[0.12] bg-slate-400/[0.06]"
                        }`}
                        onClick={() => handleClickHuman(`human${i + 1}`)}
                      >
                        <div className="text-slate-400/60 flex justify-center mb-0.5">
                          <PersonIconSmall />
                        </div>
                        <div className="text-[0.72rem] text-slate-400/50 font-semibold">
                          {name}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Human flow lines */}
                <div className="grid grid-cols-3 gap-1.5 mt-1 justify-items-center relative z-[3]">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className={`md-human-flow-line w-[3px] h-10 rounded-sm transition-colors duration-[400ms] ${
                        stage.humanFlow ? "md-flowing" : "bg-slate-400/[0.12]"
                      } ${isReverse ? "md-flow-reverse" : ""}`}
                    />
                  ))}
                </div>
              </div>
              <div />
              <div />
            </div>

            {/* Main 5-column grid */}
            <div className="grid grid-cols-[108px_92px_1fr_92px_108px] items-start gap-0 max-[900px]:grid-cols-[96px_64px_1fr_64px_96px] max-[700px]:grid-cols-[90px_36px_1fr_36px_90px] max-[540px]:flex max-[540px]:flex-col max-[540px]:items-stretch max-[540px]:gap-4">
              {/* LEFT: Feeds group */}
              <div className="border border-green-600/25 bg-green-600/[0.04] rounded-2xl p-[10px_8px_10px] flex flex-col relative self-center">
                <div className="text-[0.8rem] font-bold uppercase tracking-[0.12em] text-center mb-1.5 pb-1.5 border-b border-white/[0.06] text-green-600/70">
                  Feeds
                </div>
                <div ref={feedColRef} className="grid grid-rows-4 gap-2 flex-1 max-[540px]:grid-rows-none max-[540px]:grid-cols-4 max-[540px]:justify-center max-[540px]:flex-wrap">
                  {feedItems.map((feed, i) => (
                    <div
                      key={i}
                      data-feed-node
                      onClick={() => handleClickFeed(i)}
                      className={`bg-slate-800/70 border rounded-lg p-[6px_6px_4px] text-center cursor-pointer transition-all duration-[350ms] ${
                        stage.feeds.includes(i)
                          ? "border-green-600 bg-green-600/[0.12] shadow-[0_0_14px_rgba(22,163,74,0.25)]"
                          : "border-white/[0.08] hover:border-green-600/50 hover:bg-green-600/[0.08]"
                      } max-[540px]:min-w-[60px]`}
                    >
                      <div className="flex justify-center items-center mb-0 text-green-600">
                        {feed.icon}
                      </div>
                      <div className="text-[0.75rem] leading-tight text-white/50 text-center break-words max-[700px]:hidden">
                        {feed.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Feed flow lines — positioned by JS alignFlowLines */}
              <div ref={flowInColRef} className="flex flex-col px-0.5 self-center relative max-[540px]:hidden">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    data-flow-in
                    className={`md-flow-line md-flow-in h-[3px] rounded-sm bg-white/[0.06] absolute left-0.5 right-0.5 ${
                      stage.flowIn.includes(i) ? "md-flowing" : ""
                    } ${isReverse ? "md-flow-reverse" : ""}`}
                  />
                ))}
              </div>

              {/* CENTER: Meeting box */}
              <div className="px-2">
                <div
                  className={`bg-slate-950/95 border rounded-2xl overflow-hidden transition-all duration-[400ms] ${
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
                    <span className="text-[1.05rem] text-white/75 font-semibold flex-1 text-center">
                      Sprint Planning &middot; Kutana AI
                    </span>
                    <span
                      className="text-[0.88rem] font-bold text-green-600"
                      style={{ animation: "md-live-blink 2s ease-in-out infinite" }}
                    >
                      &#x25CF; LIVE
                    </span>
                  </div>

                  {/* Body */}
                  <div className="p-[20px_14px_18px] min-h-[340px]">
                    <div className="flex flex-col gap-5 mb-2">
                      {/* Humans row */}
                      <div>
                        <div className="text-[0.8rem] font-bold uppercase tracking-[0.08em] text-white/40 text-left p-[2px_2px_4px]">
                          Humans
                        </div>
                        <div className="flex gap-1 justify-center py-2">
                          <Participant
                            name="Jordan"
                            icon={<PersonIcon />}
                            speaking={stage.speaking === "human1"}
                            speakingClass="md-speaking-human"
                            bubbleContent={"\u201CWhere are we\non the refactor?\u201D"}
                            bubbleStyle="human"
                            isEdge
                            onClick={() => handleClickHuman("human1")}
                          />
                          <Participant
                            name="Sarah"
                            icon={<PersonIcon />}
                            speaking={stage.speaking === "human2"}
                            speakingClass="md-speaking-human"
                            bubbleContent={"\u201CI\u2019ll take the API\nif Alex picks up the auth layer.\u201D"}
                            bubbleStyle="human"
                            onClick={() => handleClickHuman("human2")}
                          />
                          <Participant
                            name="Alex"
                            icon={<PersonIcon />}
                            speaking={stage.speaking === "human3"}
                            speakingClass="md-speaking-human"
                            bubbleContent={human3BubbleText}
                            bubbleStyle="human"
                            isEdge
                            onClick={() => handleClickHuman("human3")}
                          />
                        </div>
                      </div>

                      {/* Agents row */}
                      <div>
                        <div className="text-[0.8rem] font-bold uppercase tracking-[0.08em] text-white/40 text-left p-[2px_2px_4px] mt-1.5">
                          Agents
                        </div>
                        <div className="flex gap-1 justify-center py-2">
                          <Participant
                            name={<>Jordan&apos;s<br />Claude Code</>}
                            icon={<ClaudeLogoIcon />}
                            speaking={false}
                            speakingClass=""
                            isPurple
                            onClick={() => handleClickPurpleAgent("claude")}
                          />
                          <Participant
                            name={<>Sarah&apos;s<br />Scribe Agent</>}
                            icon={<BotIcon />}
                            speaking={stage.speaking === "managed"}
                            speakingClass="md-speaking-agent-purple"
                            bubbleContent={"\u201CLogging \u2014 Sarah: API Layer\nAlex: auth refactor\u201D"}
                            bubbleStyle="purple"
                            isPurple
                            onClick={() => handleClickPurpleAgent("managed")}
                          />
                          <Participant
                            name={<>Alex&apos;s<br />OpenClaw</>}
                            icon={<OpenClawIcon />}
                            speaking={stage.speaking === "claude"}
                            speakingClass="md-speaking-agent-purple"
                            bubbleContent={claudeBubbleText}
                            bubbleStyle="purple"
                            isEdge
                            isPurple
                            onClick={() => handleClickPurpleAgent("claude")}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Context strip */}
                    {stage.contextTags.length > 0 && (
                      <div className="bg-green-600/[0.05] border-t border-green-600/10 rounded-b-lg px-2.5 py-2 flex flex-wrap gap-1.5 items-center justify-center min-h-[32px]">
                        {stage.contextTags.map((tag, i) => (
                          <span
                            key={i}
                            className={`text-[0.72rem] px-1.5 py-0.5 rounded-[3px] ${
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

              {/* Agent flow lines (with protocol labels) — positioned by JS alignFlowLines */}
              <div ref={flowOutColRef} className="flex flex-col px-0.5 self-center relative max-[540px]:hidden">
                {[0, 1, 2].map((i) => (
                  <div key={i} data-flow-out className="relative flex flex-col items-stretch gap-[3px]" style={{ position: "absolute", left: "2px", right: "2px" }}>
                    <div className="text-[0.6rem] font-bold uppercase tracking-[0.07em] text-teal-500/75 text-center whitespace-nowrap leading-none max-[700px]:hidden">
                      {protocolLabels[i]}
                    </div>
                    <div
                      className={`md-flow-line md-flow-out h-[3px] rounded-sm bg-white/[0.06] ${
                        stage.flowOut.includes(i) ? "md-flowing" : ""
                      } ${isReverse ? "md-flow-reverse" : ""}`}
                    />
                  </div>
                ))}
              </div>

              {/* RIGHT: Your Agents group */}
              <div className="border border-violet-600/25 bg-violet-600/[0.04] rounded-2xl p-[10px_0_10px] flex flex-col relative self-center">
                <div className="text-[0.8rem] font-bold uppercase tracking-[0.12em] text-center mb-1.5 pb-1.5 border-b border-white/[0.06] text-violet-400/70 px-2">
                  Your Agents
                </div>
                <div ref={agentColRef} className="grid grid-rows-3 gap-2 flex-1 px-2 max-[540px]:grid-rows-none max-[540px]:grid-cols-3 max-[540px]:justify-center max-[540px]:flex-wrap">
                  {agentConnItems.map((agent, i) => (
                    <div
                      key={i}
                      data-agent-node
                      onClick={() => handleClickAgent(i)}
                      className={`bg-slate-800/70 border rounded-lg p-[6px_6px_4px] text-center cursor-pointer transition-all duration-[350ms] ${
                        stage.agents.includes(i)
                          ? "border-violet-600/90 bg-violet-600/[0.12] shadow-[0_0_14px_rgba(124,58,237,0.25)]"
                          : "border-white/[0.08] hover:border-violet-600/50 hover:bg-violet-600/[0.08]"
                      } max-[540px]:min-w-[60px]`}
                    >
                      <div className="flex justify-center items-center mb-0 text-teal-500">
                        {agent.icon}
                      </div>
                      <div className="text-[0.75rem] leading-tight text-white/50 text-center break-words whitespace-pre-line max-[700px]:hidden">
                        {agent.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Kutana Agents row (below diagram) */}
            <div className="grid grid-cols-[108px_92px_1fr_92px_108px] gap-0 mt-2 max-[900px]:grid-cols-[96px_64px_1fr_64px_96px] max-[700px]:grid-cols-[90px_36px_1fr_36px_90px] max-[540px]:block max-[540px]:mt-0">
              <div />
              <div />
              <div className="px-2">
                {/* Managed agent connector lines */}
                <div className="grid grid-cols-3 gap-1.5 mb-1 justify-items-center relative z-[3]">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className={`md-managed-vline w-[3px] h-10 rounded-sm transition-colors duration-[400ms] ${
                        stage.managedFlowing ? "md-flowing" : "bg-violet-600/20"
                      }`}
                    />
                  ))}
                </div>
                {/* Managed agents box */}
                <div className="bg-violet-600/[0.06] border border-violet-600/20 rounded-lg p-[8px_10px_10px]">
                  <span className="text-[0.8rem] font-bold uppercase tracking-[0.1em] text-violet-400/70 text-center block mb-2 pb-1.5 border-b border-violet-600/[0.12]">
                    Kutana Agents
                  </span>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      {
                        name: "Meeting Scribe",
                        icon: (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={22} height={22}>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <path d="M14 2v6h6" />
                            <path d="M16 13H8m8 4H8" />
                          </svg>
                        ),
                      },
                      {
                        name: "Action Tracker",
                        icon: (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={22} height={22}>
                            <path d="M9 11l3 3L22 4" />
                            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                          </svg>
                        ),
                      },
                      {
                        name: "Context Builder",
                        icon: (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={22} height={22}>
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                          </svg>
                        ),
                      },
                    ].map((ma, i) => (
                      <div
                        key={i}
                        className="text-center p-[6px_4px] bg-violet-600/[0.08] rounded-md border border-violet-600/15"
                      >
                        <div className="text-violet-400/75 flex justify-center mb-[3px]">
                          {ma.icon}
                        </div>
                        <div className="text-[0.72rem] text-violet-400/65 font-semibold leading-tight max-[700px]:hidden">
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
                  onClick={() => goTo(i)}
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
  name: React.ReactNode;
  icon: React.ReactNode;
  speaking: boolean;
  speakingClass: string;
  bubbleContent?: string;
  bubbleStyle?: "human" | "purple";
  isEdge?: boolean;
  isPurple?: boolean;
  onClick?: () => void;
}

function Participant({
  name,
  icon,
  speaking,
  speakingClass,
  bubbleContent,
  bubbleStyle,
  isEdge,
  isPurple,
  onClick,
}: ParticipantProps) {
  const borderClass =
    bubbleStyle === "purple"
      ? "border-violet-600/45"
      : "border-slate-400/35";

  const tailBorderClass =
    bubbleStyle === "purple"
      ? "border-r border-b border-violet-600/45"
      : "border-r border-b border-slate-400/35";

  return (
    <div
      className="flex-1 flex flex-col items-center gap-1 relative p-[8px_4px] rounded-md cursor-pointer transition-colors duration-300 hover:bg-white/[0.03]"
      onClick={onClick}
    >
      {/* Bubble */}
      {bubbleContent && (
        <div
          className={`absolute bottom-[calc(100%+6px)] left-1/2 bg-slate-950/[0.98] border rounded-[10px] py-[7px] px-[11px] text-[0.75rem] text-white/95 text-center leading-tight z-[200] transition-all duration-[400ms] pointer-events-none ${borderClass} ${
            isEdge ? "w-[150px] max-w-[150px] px-[7px]" : "w-[240px] max-w-[240px]"
          } ${
            speaking
              ? "opacity-100 -translate-x-1/2 translate-y-0"
              : "opacity-0 -translate-x-1/2 translate-y-1.5"
          } max-[700px]:text-[0.6rem] max-[700px]:w-[160px] max-[700px]:max-w-[160px]`}
        >
          <span className="whitespace-pre-line">{bubbleContent}</span>
          <div
            className={`absolute bottom-[-5px] left-1/2 -ml-1 w-2 h-2 rotate-45 bg-slate-950/[0.98] ${tailBorderClass}`}
          />
        </div>
      )}

      {/* Orb */}
      <div className="relative w-[52px] h-[52px]">
        <div
          className={`absolute inset-[-5px] rounded-full border-2 border-transparent z-[2] pointer-events-none transition-all duration-[400ms] ${
            speaking ? speakingClass : ""
          }`}
        />
        <div
          className={`absolute inset-0 rounded-full flex items-center justify-center transition-all duration-[400ms] ${
            isPurple
              ? "bg-violet-600/10 border border-violet-600/35 text-violet-400/90"
              : "bg-slate-800/90 border border-white/10 text-slate-400/80"
          }`}
        >
          {icon}
        </div>
      </div>

      <div className="text-[0.72rem] text-white/60 text-center font-medium leading-tight whitespace-normal">
        {name}
      </div>
    </div>
  );
}
