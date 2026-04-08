import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/Card";
import { KutanaLogoMark } from "@/components/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import * as authApi from "@/api/auth";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("Missing verification token.");
      return;
    }

    authApi
      .verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err: unknown) => {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Verification failed");
      });
  }, [token]);

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <ThemeToggle />

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
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="shadow-glow-brand rounded-xl">
            <KutanaLogoMark size={48} />
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold tracking-tight text-gray-50">
              Kutana <span className="text-blue-400">AI</span>
            </h1>
            <p className="mt-0.5 text-sm text-gray-400">Email verification</p>
          </div>
        </div>

        <Card className="border-gray-700 bg-gray-900/90">
          <CardContent className="space-y-4 py-6 text-center">
            {status === "loading" && (
              <p className="text-sm text-gray-400">Verifying your email...</p>
            )}

            {status === "success" && (
              <>
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
                  Your email has been verified successfully.
                </p>
                <Link
                  to="/"
                  className="inline-block text-sm font-medium text-blue-400 transition-colors hover:text-blue-300"
                >
                  Go to dashboard
                </Link>
              </>
            )}

            {status === "error" && (
              <>
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-900/40">
                  <svg
                    className="h-6 w-6 text-red-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </div>
                <p className="text-sm text-red-400">{error}</p>
                <Link
                  to="/login"
                  className="inline-block text-sm font-medium text-blue-400 transition-colors hover:text-blue-300"
                >
                  Back to sign in
                </Link>
              </>
            )}
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-[11px] text-gray-600">
          AI-powered meeting platform &middot; Agent-first by design
        </p>
      </div>
    </div>
  );
}
