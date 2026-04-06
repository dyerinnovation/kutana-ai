const linkColumns = [
  {
    title: "Product",
    links: [
      { label: "How It Works", href: "#how-it-works" },
      { label: "Features", href: "#features" },
      { label: "Pricing", href: "#pricing" },
      { label: "Use Cases", href: "#use-cases" },
    ],
  },
  {
    title: "Get Started",
    links: [
      { label: "Free Trial", href: "#pricing" },
      { label: "Read the Docs", href: "/docs" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
    ],
  },
];

export function LandingFooter() {
  return (
    <footer className="bg-gray-950 border-t border-gray-800 px-4 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 grid gap-8 sm:grid-cols-2 md:grid-cols-3">
          {linkColumns.map((col, i) => (
            <div key={i}>
              <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
                {col.title}
              </h4>
              <ul className="space-y-2">
                {col.links.map((link, j) => (
                  <li key={j}>
                    <a
                      href={link.href}
                      className="text-sm text-gray-500 transition-colors hover:text-green-400"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 pt-8 text-center">
          <p className="text-sm text-gray-600">
            &copy; 2026 Dyer Innovation. All rights reserved.
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Built with AI. For AI. Forever.
          </p>
          <p className="mt-4 text-xs text-gray-700">
            Claude and Anthropic are trademarks of Anthropic, PBC. OpenClaw is an open-source project. All trademarks are property of their respective owners.
          </p>
        </div>
      </div>
    </footer>
  );
}
