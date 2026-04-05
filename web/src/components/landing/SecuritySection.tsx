const features = [
  {
    title: "Data Encryption",
    description:
      "All conversations are encrypted at rest and in transit using industry-standard AES-256 and TLS 1.3.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="32"
        height="32"
      >
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    ),
  },
  {
    title: "Access Controls",
    description:
      "Role-based permissions and API key scoping ensure only authorized users and agents access your data.",
    icon: (
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
    ),
  },
  {
    title: "Compliance",
    description:
      "Built with SOC 2 and GDPR readiness in mind. Your data handling meets enterprise compliance standards.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="32"
        height="32"
      >
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    title: "Audit Logging",
    description:
      "Every action is logged. Full audit trails for meetings, agent access, and data operations from day one.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="32"
        height="32"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
];

export function SecuritySection() {
  return (
    <section className="bg-green-600 py-20 px-4" id="security">
      <div className="mx-auto max-w-5xl">
        <h2 className="mb-12 text-center text-3xl font-bold text-white md:text-4xl">
          Enterprise-Grade Security
        </h2>

        <div className="grid gap-6 sm:grid-cols-2">
          {features.map((feature, i) => (
            <div
              key={i}
              className="rounded-xl bg-green-700/50 p-6 backdrop-blur-sm transition-colors hover:bg-green-700/70"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-white/15 text-white">
                {feature.icon}
              </div>
              <h3 className="mb-2 text-lg font-semibold text-white">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-green-100">
                {feature.description}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-green-200/80">
          Meeting content is processed by third-party LLM providers (such as
          Anthropic Claude) for transcription, extraction, and summarization.
          Review our privacy policy for details on how your data is handled.
        </p>
      </div>
    </section>
  );
}
