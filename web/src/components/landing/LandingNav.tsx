import { Link } from "react-router-dom";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Pricing", href: "#pricing" },
  { label: "Use Cases", href: "#use-cases" },
] as const;

export default function LandingNav() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-slate-900/80 border-b border-white/10">
      <div className="flex items-center justify-between max-w-7xl mx-auto px-6 py-4">
        {/* Logo */}
        <span className="text-2xl font-extrabold bg-gradient-to-br from-green-600 to-teal-500 bg-clip-text text-transparent">
          Kutana AI
        </span>

        {/* Nav links - hidden on mobile */}
        <ul className="hidden md:flex items-center gap-8 list-none">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="text-white/70 hover:text-green-500 transition-colors duration-300 text-sm"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        {/* Auth actions */}
        <div className="flex items-center gap-4">
          <Link
            to="/login"
            className="text-white/70 hover:text-green-500 transition-colors duration-300 text-sm hidden md:inline"
          >
            Sign In
          </Link>
          <Link
            to="/register"
            className="inline-flex items-center px-5 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-semibold transition-colors duration-300"
          >
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  );
}
