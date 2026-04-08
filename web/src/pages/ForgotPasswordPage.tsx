import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardFooter } from "@/components/ui/Card";
import { KutanaLogoMark } from "@/components/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import * as authApi from "@/api/auth";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authApi.forgotPassword(email);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong"
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <ThemeToggle />

      {/* Ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div
          className="absolute left-1/2 top-0 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
          style={{
            background:
              "radial-gradient(circle, rgb(16 185 129 / 0.15) 0%, transparent 70%)",
          }}
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
            <p className="mt-0.5 text-sm text-gray-400">Reset your password</p>
          </div>
        </div>

        <Card className="border-gray-700 bg-gray-900/90">
          {success ? (
            <CardContent className="space-y-4 py-6 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-900/40">
                <svg
                  className="h-6 w-6 text-green-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <p className="text-sm text-gray-300">
                If that email is registered, we've sent a password reset link.
                Check your inbox.
              </p>
              <Link
                to="/login"
                className="inline-block text-sm font-medium text-blue-400 transition-colors hover:text-blue-300"
              >
                Back to sign in
              </Link>
            </CardContent>
          ) : (
            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-4 pt-6">
                {error && (
                  <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm text-red-400">
                    {error}
                  </div>
                )}

                <p className="text-sm text-gray-400">
                  Enter your email and we'll send you a link to reset your
                  password.
                </p>

                <Input
                  label="Email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </CardContent>

              <CardFooter className="flex-col gap-3 pt-2 pb-6">
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? "Sending..." : "Send reset link"}
                </Button>

                <p className="text-sm text-gray-500">
                  Remember your password?{" "}
                  <Link
                    to="/login"
                    className="font-medium text-blue-400 transition-colors hover:text-blue-300"
                  >
                    Sign in
                  </Link>
                </p>
              </CardFooter>
            </form>
          )}
        </Card>

        <p className="mt-6 text-center text-[11px] text-gray-600">
          AI-powered meeting platform &middot; Agent-first by design
        </p>
      </div>
    </div>
  );
}
