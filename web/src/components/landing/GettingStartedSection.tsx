import { useState } from "react";

const tabs = [
  {
    num: 1,
    label: "Sign Up",
    title: "Create a Kutana Account",
    description:
      "Sign up with your email and password. Takes less than a minute — and you can start for free.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="64"
        height="64"
      >
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    num: 2,
    label: "Add Agents",
    title: "Add an Agent to Your Profile",
    description:
      "Connect your own agent via MCP, Skills, or CLI. Or add a Kutana Agent.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="64"
        height="64"
      >
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83" />
      </svg>
    ),
  },
  {
    num: 3,
    label: "Schedule",
    title: "Schedule a Meeting",
    description:
      "Invite your team and your agents. Kutana handles the orchestration — everyone connects automatically.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="64"
        height="64"
      >
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    num: 4,
    label: "Collaborate",
    title: "Agents Join & Collaborate",
    description:
      "Agents speak and participate in meetings like a colleague. Kutana transcribes and extracts tasks from the conversation. Your Agent leaves the meeting ready to work.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        width="64"
        height="64"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
];

export function GettingStartedSection() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <section className="py-20 px-4" id="getting-started">
      <div className="mx-auto max-w-5xl">
        <h2 className="mb-12 text-center text-3xl font-bold text-white md:text-4xl">
          Get Started in 4 Simple Steps
        </h2>

        <div className="overflow-hidden rounded-2xl border border-gray-800 bg-gray-900">
          {/* Tab buttons */}
          <div className="flex border-b border-gray-800">
            {tabs.map((tab, i) => (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={`flex-1 px-4 py-4 text-sm font-medium transition-colors md:text-base ${
                  activeTab === i
                    ? "border-b-2 border-green-500 bg-gray-800/50 text-green-400"
                    : "text-gray-400 hover:bg-gray-800/30 hover:text-gray-200"
                }`}
              >
                <span
                  className={`mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                    activeTab === i
                      ? "bg-green-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  {tab.num}
                </span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Panel content */}
          <div className="flex flex-col items-center gap-6 p-8 md:flex-row md:gap-12 md:p-12">
            <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-gray-800 text-green-400">
              {tabs[activeTab].icon}
            </div>
            <div>
              <h3 className="mb-3 text-xl font-semibold text-white">
                {tabs[activeTab].title}
              </h3>
              <p className="leading-relaxed text-gray-400">
                {tabs[activeTab].description}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
