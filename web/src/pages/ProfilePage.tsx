import { useState, useRef, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { updateProfile, changePassword, uploadAvatar, deleteAvatar } from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";

export function ProfilePage() {
  const { user, refreshUser } = useAuth();

  // Profile form
  const [name, setName] = useState(user?.name ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState<string | null>(null);

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPw, setIsChangingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Avatar
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSaveProfile(e: FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setProfileMsg(null);
    try {
      await updateProfile({ name });
      await refreshUser();
      setProfileMsg("Profile updated.");
    } catch (err) {
      setProfileMsg(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwMsg(null);

    if (newPassword !== confirmPassword) {
      setPwMsg({ type: "error", text: "Passwords do not match." });
      return;
    }
    if (newPassword.length < 8) {
      setPwMsg({ type: "error", text: "Password must be at least 8 characters." });
      return;
    }

    setIsChangingPw(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwMsg({ type: "success", text: "Password changed successfully." });
    } catch (err) {
      setPwMsg({ type: "error", text: err instanceof Error ? err.message : "Failed to change password" });
    } finally {
      setIsChangingPw(false);
    }
  }

  async function handleAvatarUpload(file: File) {
    setIsUploading(true);
    try {
      await uploadAvatar(file);
      await refreshUser();
    } catch {
      // Silently fail — user can retry
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAvatarDelete() {
    setIsUploading(true);
    try {
      await deleteAvatar();
      await refreshUser();
    } catch {
      // Silently fail
    } finally {
      setIsUploading(false);
    }
  }

  if (!user) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Profile &amp; Settings</h1>
        <p className="text-sm text-gray-400 mt-1">
          Manage your account information and preferences.
        </p>
      </div>

      {/* Profile Card */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSaveProfile} className="space-y-5">
            {/* Avatar */}
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="relative flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-gradient-brand text-xl font-semibold text-white overflow-hidden transition-opacity hover:opacity-80"
              >
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  user.name.charAt(0).toUpperCase()
                )}
                {isUploading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-950/60">
                    <svg className="h-5 w-5 animate-spin text-gray-50" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  </div>
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleAvatarUpload(file);
                  e.target.value = "";
                }}
              />
              <div className="space-y-1">
                <p className="text-sm text-gray-400">
                  Click the avatar to upload a photo.
                </p>
                {user.avatar_url && (
                  <button
                    type="button"
                    onClick={handleAvatarDelete}
                    disabled={isUploading}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    Remove photo
                  </button>
                )}
              </div>
            </div>

            {/* Email (read-only) */}
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">Email</label>
              <p className="rounded-lg border border-gray-800 bg-gray-900/50 px-3 py-2 text-sm text-gray-500">
                {user.email}
              </p>
            </div>

            {/* Name */}
            <Input
              label="Display Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />

            {/* Member since */}
            <div className="text-xs text-gray-500">
              Member since{" "}
              {new Date(user.created_at).toLocaleDateString(undefined, {
                month: "long",
                year: "numeric",
              })}
            </div>

            {profileMsg && (
              <p className="text-sm text-green-400">{profileMsg}</p>
            )}

            <Button type="submit" disabled={isSaving || name === user.name}>
              {isSaving ? "Saving..." : "Save Changes"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Password Card */}
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
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

            <Button type="submit" disabled={isChangingPw}>
              {isChangingPw ? "Changing..." : "Change Password"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Account Card */}
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300">Current Plan</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {user.plan_tier.charAt(0).toUpperCase() + user.plan_tier.slice(1)}
                {user.subscription_status === "trialing" && " (Trial)"}
                {user.subscription_status === "past_due" && " (Past Due)"}
              </p>
            </div>
            <Link to="/settings/billing">
              <Button variant="outline" size="sm">
                Manage Billing
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
