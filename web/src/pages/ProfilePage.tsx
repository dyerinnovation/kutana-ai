import { useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/useAuth";
import { updateProfile } from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";

export function ProfilePage() {
  const { user, refreshUser } = useAuth();

  // Name editing
  const [name, setName] = useState(user?.name ?? "");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameMsg, setNameMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Password change
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  async function handleNameSave(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setNameSaving(true);
    setNameMsg(null);
    try {
      await updateProfile({ name: name.trim() });
      await refreshUser();
      setNameMsg({ type: "success", text: "Name updated" });
    } catch (err) {
      setNameMsg({ type: "error", text: err instanceof Error ? err.message : "Failed to update name" });
    } finally {
      setNameSaving(false);
    }
  }

  async function handlePasswordChange(e: FormEvent) {
    e.preventDefault();
    setPwMsg(null);

    if (newPassword !== confirmPassword) {
      setPwMsg({ type: "error", text: "Passwords do not match" });
      return;
    }
    if (newPassword.length < 8) {
      setPwMsg({ type: "error", text: "New password must be at least 8 characters" });
      return;
    }

    setPwSaving(true);
    try {
      await updateProfile({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwMsg({ type: "success", text: "Password updated" });
    } catch (err) {
      setPwMsg({ type: "error", text: err instanceof Error ? err.message : "Failed to change password" });
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-gray-50">Profile</h1>
        <p className="mt-0.5 text-sm text-gray-400">
          Manage your account settings
        </p>
      </div>

      {/* Avatar + basic info */}
      <Card>
        <CardContent className="flex items-center gap-4 py-5">
          <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full bg-gradient-brand text-lg font-semibold text-white">
            {user?.name?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-50">{user?.name}</p>
            <p className="text-xs text-gray-400">{user?.email}</p>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Member since{" "}
              {user?.created_at
                ? new Date(user.created_at).toLocaleDateString(undefined, {
                    month: "long",
                    year: "numeric",
                  })
                : "—"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Edit name */}
      <Card>
        <CardHeader>
          <CardTitle>Display Name</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleNameSave} className="space-y-3">
            <Input
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            {nameMsg && (
              <p className={`text-sm ${nameMsg.type === "success" ? "text-green-400" : "text-red-400"}`}>
                {nameMsg.text}
              </p>
            )}
            <Button type="submit" size="sm" disabled={nameSaving || !name.trim()}>
              {nameSaving ? "Saving..." : "Update Name"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Change password */}
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePasswordChange} className="space-y-3">
            <Input
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <Input
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
            {pwMsg && (
              <p className={`text-sm ${pwMsg.type === "success" ? "text-green-400" : "text-red-400"}`}>
                {pwMsg.text}
              </p>
            )}
            <Button
              type="submit"
              size="sm"
              disabled={pwSaving || !currentPassword || !newPassword || !confirmPassword}
            >
              {pwSaving ? "Changing..." : "Change Password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
