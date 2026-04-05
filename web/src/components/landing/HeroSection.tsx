import { Link } from "react-router-dom";
import { useMemo } from "react";

function Particles() {
  const particles = useMemo(() => {
    return Array.from({ length: 20 }, (_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      tx: `${(Math.random() - 0.5) * 200}px`,
      ty: `${(Math.random() - 0.5) * 200}px`,
      delay: `${Math.random() * 20}s`,
      duration: `${15 + Math.random() * 10}s`,
    }));
  }, []);

  return (
    <>
      <style>{`
        @keyframes float {
          0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
          50% { transform: translate(var(--tx), var(--ty)) scale(1.5); opacity: 0.6; }
        }
      `}</style>
      <div className="absolute inset-0 z-0 overflow-hidden">
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute w-[3px] h-[3px] rounded-full bg-green-500 opacity-30"
            style={{
              left: p.left,
              top: p.top,
              "--tx": p.tx,
              "--ty": p.ty,
              animation: `float ${p.duration} ${p.delay} infinite ease-in-out`,
            } as React.CSSProperties}
          />
        ))}
      </div>
    </>
  );
}

function MockupWindow() {
  return (
    <div className="w-full max-w-[900px]">
      <div className="bg-slate-800/95 border border-green-600/30 rounded-2xl overflow-hidden shadow-[0_40px_80px_rgba(0,0,0,0.5),0_0_60px_rgba(22,163,74,0.15)]">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-3 bg-slate-900/80 border-b border-white/10">
          <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
          <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
          <div className="w-3 h-3 rounded-full bg-[#28c840]" />
          <span className="flex-1 text-center text-xs text-slate-400">
            Kutana AI &mdash; Sprint Planning &mdash; 4 participants
          </span>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col gap-4">
          {/* Video grid */}
          <div className="grid grid-cols-2 gap-2">
            {/* Human tile - Jonathan */}
            <div className="bg-slate-900/80 border border-white/10 rounded-lg p-4 aspect-[16/10] flex flex-col items-center justify-center gap-1.5">
              <div className="w-9 h-9 rounded-full bg-slate-400/30 flex items-center justify-center text-sm font-bold text-slate-400">
                JD
              </div>
              <span className="text-[0.7rem] text-white/60">Jonathan (You)</span>
            </div>

            {/* Agent tile - Sprint Planner */}
            <div className="bg-green-600/[0.08] border border-green-600/40 rounded-lg p-4 aspect-[16/10] flex flex-col items-center justify-center gap-1.5">
              <div className="w-9 h-9 rounded-full bg-green-600/30 flex items-center justify-center text-green-500">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83" />
                </svg>
              </div>
              <span className="text-[0.7rem] text-white/60">Sprint Planner Agent</span>
            </div>

            {/* Human tile - Sarah */}
            <div className="bg-slate-900/80 border border-white/10 rounded-lg p-4 aspect-[16/10] flex flex-col items-center justify-center gap-1.5">
              <div className="w-9 h-9 rounded-full bg-slate-400/30 flex items-center justify-center text-sm font-bold text-slate-400">
                SK
              </div>
              <span className="text-[0.7rem] text-white/60">Sarah K.</span>
            </div>

            {/* Agent tile - Action Tracker */}
            <div className="bg-green-600/[0.08] border border-green-600/40 rounded-lg p-4 aspect-[16/10] flex flex-col items-center justify-center gap-1.5">
              <div className="w-9 h-9 rounded-full bg-green-600/30 flex items-center justify-center text-green-500">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                  <path d="M16 13H8m8 4H8m2-8H8" />
                </svg>
              </div>
              <span className="text-[0.7rem] text-white/60">Action Tracker</span>
            </div>
          </div>

          {/* Sidebar panels */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Live Transcript */}
            <div className="bg-slate-900/60 border border-white/[0.08] rounded-lg p-3">
              <div className="text-[0.7rem] font-semibold text-teal-500 uppercase tracking-wider mb-1.5">
                Live Transcript
              </div>
              <div className="text-[0.65rem] text-white/50 py-0.5 border-b border-white/[0.04]">
                <strong className="text-white/70">Jonathan:</strong> Let&rsquo;s prioritize the auth refactor this sprint.
              </div>
              <div className="text-[0.65rem] text-white/50 py-0.5 border-b border-white/[0.04]">
                <strong className="text-white/70">Sarah:</strong> Agreed. I can take the API layer.
              </div>
              <div className="text-[0.65rem] text-white/50 py-0.5">
                <strong className="text-white/70">Sprint Planner:</strong> Based on velocity, I&rsquo;d estimate 5 story points for auth.
              </div>
            </div>

            {/* Extracted Tasks */}
            <div className="bg-slate-900/60 border border-white/[0.08] rounded-lg p-3">
              <div className="text-[0.7rem] font-semibold text-teal-500 uppercase tracking-wider mb-1.5">
                Extracted Tasks
              </div>
              <div className="text-[0.65rem] text-white/50 px-1.5 py-1 bg-green-600/10 rounded mb-1 flex items-center gap-1">
                <span className="text-green-500 text-[0.6rem]">&#10003;</span> Auth refactor - Sarah K. - 5pts
              </div>
              <div className="text-[0.65rem] text-white/50 px-1.5 py-1 bg-green-600/10 rounded mb-1 flex items-center gap-1">
                <span className="text-green-500 text-[0.6rem]">&#10003;</span> API layer migration - Sarah K.
              </div>
              <div className="text-[0.65rem] text-white/50 px-1.5 py-1 bg-green-600/10 rounded flex items-center gap-1">
                <span className="text-green-500 text-[0.6rem]">&#10003;</span> Sprint velocity review - Agent
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden mt-[60px] px-6 py-24">
      <Particles />

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-16 items-center max-w-[1200px] w-full">
        {/* Text side */}
        <div className="flex flex-col text-center lg:text-left">
          <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-8">
            <span className="bg-gradient-to-br from-green-500 to-lime-400 bg-clip-text text-transparent">
              The meeting platform where{" "}
              <span className="text-lime-400 font-extrabold" style={{ WebkitTextFillColor: "#a3e635" }}>
                AI&nbsp;Agents
              </span>{" "}
              are{" "}
              <span className="text-lime-400 font-extrabold" style={{ WebkitTextFillColor: "#a3e635" }}>
                Proactive Participants
              </span>
              .
            </span>
          </h1>

          <p className="text-lg md:text-xl text-white/80 mb-2">
            Your <span className="whitespace-nowrap">AI Agents</span> don&rsquo;t just observe &mdash; they actively participate, ask questions, and execute.
          </p>
          <p className="text-lg md:text-xl text-white/80 mb-10">
            When the meeting ends, Enriched Meeting Context flows straight to your agent.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
            <Link
              to="/register"
              className="inline-flex items-center justify-center px-8 py-3.5 rounded-lg bg-green-600 hover:bg-green-500 text-white font-semibold text-base transition-colors duration-300"
            >
              Get Started Free
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center px-8 py-3.5 rounded-lg border border-white/20 hover:border-green-500/50 text-white/80 hover:text-white font-semibold text-base transition-colors duration-300"
            >
              Learn More
            </a>
          </div>
        </div>

        {/* Mockup side */}
        <MockupWindow />
      </div>
    </section>
  );
}
