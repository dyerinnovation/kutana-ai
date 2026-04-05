const linkColumns = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "Pricing", href: "#pricing" },
      { label: "Use Cases", href: "#use-cases" },
      { label: "How It Works", href: "#how-it-works" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Contact", href: "#contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
    ],
  },
];

export function LandingFooter() {
  return (
    <footer className="bg-gray-950 border-t border-gray-800 px-4 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          {/* Logo / brand column */}
          <div>
            <h3 className="mb-4 text-xl font-bold bg-gradient-to-r from-green-400 to-teal-400 bg-clip-text text-transparent">
              Kutana AI
            </h3>
            <p className="text-sm text-gray-500">
              Built with AI. For AI. Forever.
            </p>
          </div>

          {/* Link columns */}
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
            &copy; 2026 Kutana AI. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
