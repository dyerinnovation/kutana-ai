/**
 * VoiceAgentOrb — Animated violet orb for AI agent participants.
 *
 * Renders layered CSS glow rings around a core circle. Idle state breathes
 * slowly (3 s cycle); speaking state pulses faster (1 s) with increased
 * intensity and a slight scale bump. All animation is pure CSS — no JS
 * requestAnimationFrame loops.
 */

interface VoiceAgentOrbProps {
  isSpeaking: boolean;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: {
    core: "h-16 w-16",
    glow1: "h-20 w-20",
    glow2: "h-24 w-24",
    text: "text-[10px]",
    icon: "h-6 w-6",
  },
  md: {
    core: "h-20 w-20",
    glow1: "h-24 w-24",
    glow2: "h-28 w-28",
    text: "text-xs",
    icon: "h-8 w-8",
  },
  lg: {
    core: "h-28 w-28",
    glow1: "h-32 w-32",
    glow2: "h-36 w-36",
    text: "text-sm",
    icon: "h-10 w-10",
  },
} as const;

export function VoiceAgentOrb({
  isSpeaking,
  size = "md",
}: VoiceAgentOrbProps) {
  const s = sizeMap[size];

  // Pick animation class based on state
  const breatheClass = isSpeaking
    ? "animate-orb-speak"
    : "animate-orb-breathe";

  return (
    <div className="relative flex items-center justify-center">
      {/* Outer glow ring */}
      <div
        className={`absolute ${s.glow2} rounded-full ${breatheClass}`}
        style={{
          background:
            "radial-gradient(circle, rgba(139,92,246,0.12) 0%, rgba(139,92,246,0) 70%)",
        }}
      />

      {/* Inner glow ring */}
      <div
        className={`absolute ${s.glow1} rounded-full ${breatheClass}`}
        style={{
          background:
            "radial-gradient(circle, rgba(139,92,246,0.25) 0%, rgba(139,92,246,0) 70%)",
          animationDelay: "0.15s",
        }}
      />

      {/* Core orb */}
      <div
        className={`relative ${s.core} rounded-full flex items-center justify-center ${breatheClass} ${
          isSpeaking ? "shadow-orb-speak" : "shadow-orb-idle"
        }`}
        style={{
          background:
            "radial-gradient(circle at 35% 35%, #a78bfa 0%, #8b5cf6 50%, #6d28d9 100%)",
        }}
      >
        {/* Bot sparkle icon */}
        <svg
          className={`${s.icon} text-white/90`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
          />
        </svg>
      </div>
    </div>
  );
}
