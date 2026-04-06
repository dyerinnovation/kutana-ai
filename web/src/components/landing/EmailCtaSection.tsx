import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

export function EmailCtaSection() {
  const [email, setEmail] = useState("");
  const navigate = useNavigate();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    navigate(`/register?email=${encodeURIComponent(email)}`);
  }

  return (
    <section id="contact" className="relative py-24 bg-gradient-to-br from-emerald-950/20 to-teal-950/10">
      <div className="max-w-3xl mx-auto px-6 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Ready to transform your meetings?
        </h2>
        <p className="text-white/70 mb-8">
          Join the future of intelligent collaboration. Start free, no credit card required.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-md mx-auto">
          <input
            type="email"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full sm:flex-1 px-4 py-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          />
          <button
            type="submit"
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-green-600 hover:bg-green-500 text-white font-semibold transition-all duration-300 shadow-lg shadow-green-600/25"
          >
            Get Started
          </button>
        </form>
      </div>
    </section>
  );
}
