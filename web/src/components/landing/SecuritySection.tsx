import GetStartedCTA from "./GetStartedCTA";

export function SecuritySection() {
  return (
    <section
      className="py-20 px-4"
      id="security"
    >
      <div className="mx-auto max-w-3xl">
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm p-8 md:p-12 text-center">
          <div className="mb-6 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-green-600/15 border border-green-500/20 text-green-400">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                width="32"
                height="32"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
          </div>

          <h2 className="mb-4 text-3xl font-bold text-white md:text-4xl">
            Your Data, Protected
          </h2>

          <p className="mb-6 leading-relaxed text-gray-300">
            Your conversations are encrypted at rest and in transit. Kutana takes
            data security seriously — access controls, audit logs, and secure
            infrastructure are built in from day one.
          </p>

          <p className="text-sm leading-relaxed text-gray-500">
            Meeting content is processed by third-party LLM providers (such as
            Anthropic Claude) for transcription, extraction, and summarization.
            Review our privacy policy for details on how your data is handled.
          </p>
        </div>
        <GetStartedCTA />
      </div>
    </section>
  );
}
