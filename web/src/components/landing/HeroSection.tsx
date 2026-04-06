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

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden mt-[60px] px-6 py-24">
      <Particles />

      <div className="relative z-10 flex flex-col items-center text-center max-w-[800px] w-full">
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

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
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
            Watch Demo
          </a>
        </div>
      </div>
    </section>
  );
}
