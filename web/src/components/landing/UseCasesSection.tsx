import { useState, useEffect, useCallback } from "react";

const slides = [
  {
    icon: "\u25B6",
    title: "Always-On Standup Agent",
    points: [
      "Your agent joins every morning automatically",
      "Takes notes and tracks blockers in real-time",
      "Posts the recap to Slack before you\u2019ve finished your coffee",
    ],
  },
  {
    icon: "\u2699",
    title: "Code Agent That Listens In",
    points: [
      "Claude Code agent calls into sprint planning",
      "Hears priorities and understands the context",
      "Gets right to work on the next ticket \u2014 no handoff meeting required",
    ],
  },
  {
    icon: "\uD83D\uDC4B",
    title: "Agent Attends When You Can\u2019t",
    points: [
      "Have your agent join meetings you can\u2019t attend",
      "It participates on your behalf \u2014 asks questions, takes notes",
      "You get the full Enriched Meeting Context afterward",
    ],
  },
  {
    icon: "\u23F1",
    title: "Double-Booked? Agent Goes Ahead",
    points: [
      "Agent joins ahead when you\u2019re in another meeting",
      "Listens, captures context, and tracks what\u2019s happening",
      "Catches you up instantly when you join",
    ],
  },
  {
    icon: "\uD83D\uDCAC",
    title: "DM Your Agent During the Meeting",
    points: [
      "Message your agent as a copilot during live meetings",
      "Ask questions or tell it what to listen for",
      "Get real-time answers without interrupting the conversation",
    ],
  },
  {
    icon: "\uD83C\uDFA4",
    title: "Conduct Bulk Interviews",
    points: [
      "Use Kutana to interview users about your product",
      "Use Kutana to gather initial info for prospects",
      "Customize Kutana's agents for your needs",
    ],
  },
];

export function UseCasesSection() {
  const [current, setCurrent] = useState(0);
  const [paused, setPaused] = useState(false);

  const next = useCallback(() => {
    setCurrent((prev) => (prev + 1) % slides.length);
  }, []);

  const prev = useCallback(() => {
    setCurrent((prev) => (prev - 1 + slides.length) % slides.length);
  }, []);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(next, 5000);
    return () => clearInterval(id);
  }, [paused, next]);

  const slide = slides[current];

  return (
    <section className="bg-gray-950 py-20 px-4" id="use-cases">
      <div className="mx-auto max-w-4xl">
        <h2 className="mb-12 text-center text-3xl font-bold text-white md:text-4xl">
          Use Cases for Kutana
        </h2>

        <div
          className="relative overflow-hidden rounded-2xl border border-gray-800 bg-gray-900 p-8 md:p-12"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          {/* Prev / Next arrows */}
          <button
            onClick={prev}
            className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-gray-800 p-2 text-2xl text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
            aria-label="Previous slide"
          >
            &#x2039;
          </button>
          <button
            onClick={next}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-gray-800 p-2 text-2xl text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
            aria-label="Next slide"
          >
            &#x203A;
          </button>

          {/* Slide content */}
          <div className="px-8 text-center">
            <div className="mb-4 text-4xl">{slide.icon}</div>
            <h3 className="mb-6 text-2xl font-semibold text-white">
              {slide.title}
            </h3>
            <ul className="mx-auto max-w-lg space-y-3 text-left text-gray-400">
              {slide.points.map((point, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-green-500" />
                  {point}
                </li>
              ))}
            </ul>
          </div>

          {/* Navigation dots */}
          <div className="mt-8 flex items-center justify-center gap-2">
            {slides.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrent(i)}
                className={`h-2.5 w-2.5 rounded-full transition-colors ${
                  current === i
                    ? "bg-green-500"
                    : "bg-gray-600 hover:bg-gray-500"
                }`}
                aria-label={`Go to slide ${i + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
