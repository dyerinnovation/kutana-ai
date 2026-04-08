import { Link } from "react-router-dom";
import { KutanaKMark } from "@/components/Logo";
import { useAuth } from "@/hooks/useAuth";

export function NotFoundPage() {
  const { user } = useAuth();
  const homeHref = user ? "/" : "/";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 px-6 text-center">
      <KutanaKMark size={48} />
      <p className="mt-6 text-6xl font-extrabold text-green-500">404</p>
      <h1 className="mt-2 text-xl font-bold text-gray-50">Page not found</h1>
      <p className="mt-2 max-w-md text-sm text-gray-400">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to={homeHref}
        className="mt-6 inline-flex items-center rounded-lg bg-green-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-500"
      >
        {user ? "Back to Dashboard" : "Back to Home"}
      </Link>
    </div>
  );
}
