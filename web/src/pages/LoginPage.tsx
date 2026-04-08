import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardFooter } from "@/components/ui/Card";
import { KutanaLogoMark } from "@/components/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <ThemeToggle />

      {/* Ambient glow — radiates from top-center like a light source */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div
          className="absolute left-1/2 top-0 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgb(16 185 129 / 0.15) 0%, transparent 70%)" }}
        />
      </div>

      <div className="relative w-full max-w-sm">

        {/* Logo + wordmark */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="shadow-glow-brand rounded-xl">
            <KutanaLogoMark size={48} />
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold tracking-tight text-gray-50">
              Kutana <span className="text-blue-400">AI</span>
            </h1>
            <p className="mt-0.5 text-sm text-gray-400">
              Sign in to your workspace
            </p>
          </div>
        </div>

        {/* Form card */}
        <Card className="border-gray-700 bg-gray-900/90">
          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4 pt-6">
              {error && (
                <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              <Input
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />

              <Input
                label="Password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />

              <div className="flex justify-end">
                <Link
                  to="/forgot-password"
                  className="text-xs text-gray-500 transition-colors hover:text-blue-400"
                >
                  Forgot password?
                </Link>
              </div>
            </CardContent>

            <CardFooter className="flex-col gap-3 pt-2 pb-6">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? "Signing in…" : "Continue"}
              </Button>

              <p className="text-sm text-gray-500">
                Don&apos;t have an account?{" "}
                <Link
                  to="/register"
                  className="font-medium text-blue-400 transition-colors hover:text-blue-300"
                >
                  Create account
                </Link>
              </p>
            </CardFooter>
          </form>
        </Card>

        {/* Footer note */}
        <p className="mt-6 text-center text-[11px] text-gray-600">
          AI-powered meeting platform &middot; Agent-first by design
        </p>
      </div>
    </div>
  );
}
