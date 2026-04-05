import { useAuth } from "@/hooks/useAuth";

interface AuthRedirectProps {
  authenticated: React.ReactNode;
  guest: React.ReactNode;
}

export function AuthRedirect({ authenticated, guest }: AuthRedirectProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return <>{user ? authenticated : guest}</>;
}
