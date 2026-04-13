import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { KutanaKMark } from "@/components/Logo";

const navLinks = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
  { label: "Use Cases", href: "#use-cases" },
  { label: "Contact", href: "#contact" },
] as const;

export default function LandingNav() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // Close drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-slate-900/80 border-b border-white/10">
        <div className="flex items-center justify-between max-w-7xl mx-auto px-6 py-4">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <KutanaKMark size={36} />
            <span className="text-2xl font-extrabold" style={{ color: "#16A34A" }}>
              Kutana AI
            </span>
          </div>

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

          {/* Auth actions + hamburger */}
          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="text-white/70 hover:text-green-500 transition-colors duration-300 text-sm"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="inline-flex items-center px-3 py-1.5 sm:px-5 sm:py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-xs sm:text-sm font-semibold transition-colors duration-300 whitespace-nowrap"
            >
              Get Started
            </Link>

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden flex items-center justify-center rounded-lg p-2 text-gray-300 hover:bg-white/10 transition-colors"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              {mobileOpen ? <XIcon /> : <MenuIcon />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile drawer + backdrop */}
      {mobileOpen && (
        <div className="fixed inset-0 z-[60] md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />

          {/* Drawer */}
          <div className="absolute right-0 top-0 h-full w-72 bg-gray-950 border-l border-gray-800 shadow-2xl flex flex-col">
            {/* Drawer header */}
            <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
              <div className="flex items-center gap-2">
                <KutanaKMark size={28} />
                <span className="text-lg font-bold text-green-500">Kutana</span>
              </div>
              <button
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
                aria-label="Close menu"
              >
                <XIcon />
              </button>
            </div>

            {/* Nav links */}
            <nav className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="block rounded-lg px-3 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-gray-50 transition-colors"
                >
                  {link.label}
                </a>
              ))}
            </nav>

            {/* Auth actions */}
            <div className="border-t border-gray-800 p-4 space-y-2">
              <Link
                to="/login"
                className="block w-full rounded-lg border border-gray-700 px-4 py-2.5 text-center text-sm font-medium text-gray-200 hover:bg-gray-800 transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="block w-full rounded-lg bg-green-600 px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-green-500 transition-colors"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MenuIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
