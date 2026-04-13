import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import type { Agent, AgentKey, KeyCreateResponse } from "@/types";
import {
  getAgent,
  deleteAgent,
  listKeys,
  createKey,
  revokeKey,
} from "@/api/agents";
import { formatCapability } from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";

export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [keys, setKeys] = useState<AgentKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Key creation state
  const [showCreateKey, setShowCreateKey] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [isCreatingKey, setIsCreatingKey] = useState(false);
  const [newKey, setNewKey] = useState<KeyCreateResponse | null>(null);

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Copy state
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const [agentData, keysData] = await Promise.all([
        getAgent(id),
        listKeys(id),
      ]);
      setAgent(agentData);
      setKeys(keysData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent");
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleCreateKey(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setIsCreatingKey(true);

    try {
      const response = await createKey(id, { name: keyName });
      setNewKey(response);
      setKeyName("");
      setShowCreateKey(false);
      // Refresh keys list
      const keysData = await listKeys(id);
      setKeys(keysData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setIsCreatingKey(false);
    }
  }

  async function handleRevokeKey(keyId: string) {
    if (!id) return;
    try {
      await revokeKey(id, keyId);
      const keysData = await listKeys(id);
      setKeys(keysData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    }
  }

  async function handleDelete() {
    if (!id) return;
    setIsDeleting(true);
    try {
      await deleteAgent(id);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent");
    } finally {
      setIsDeleting(false);
    }
  }

  function copyToClipboard(text: string, field: string) {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  }

  if (isLoading) {
    return (
      <div className="text-center py-12 text-gray-400">Loading agent...</div>
    );
  }

  if (error && !agent) {
    return (
      <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (!agent) return null;

  const activeKeys = keys.filter((k) => !k.revoked_at);
  const revokedKeys = keys.filter((k) => k.revoked_at);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Agent Info */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-xl">{agent.name}</CardTitle>
              <p className="mt-1 text-xs text-gray-500 font-mono">{agent.id}</p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete Agent
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {agent.system_prompt && (
            <div>
              <h4 className="text-sm font-medium text-gray-400 mb-1">
                System Prompt
              </h4>
              <p className="text-sm text-gray-300 whitespace-pre-wrap rounded-lg bg-gray-800/50 p-3 border border-gray-800">
                {agent.system_prompt}
              </p>
            </div>
          )}
          {agent.capabilities.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-400 mb-2">
                Capabilities
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {agent.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="inline-flex items-center rounded-md bg-blue-600/20 border border-blue-500/30 px-2.5 py-0.5 text-xs font-medium text-blue-400"
                  >
                    {formatCapability(cap)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Newly Created Key Alert */}
      {newKey && (
        <Card className="border-green-800 bg-green-950/30">
          <CardHeader>
            <CardTitle className="text-green-400">
              API Key Created Successfully
            </CardTitle>
            <p className="text-sm text-green-300/70">
              Copy this key now -- it will not be shown again.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-3 py-2 text-sm font-mono text-green-400 break-all">
                {newKey.raw_key}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(newKey.raw_key, "raw_key")}
              >
                {copiedField === "raw_key" ? "Copied!" : "Copy"}
              </Button>
            </div>
          </CardContent>
          <CardFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setNewKey(null)}
            >
              Dismiss
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* API Keys */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>API Keys</CardTitle>
            <Button size="sm" onClick={() => setShowCreateKey(true)}>
              Generate Key
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {activeKeys.length === 0 && (
            <p className="text-sm text-gray-500 py-4 text-center">
              No active API keys. Generate one to connect your agent.
            </p>
          )}
          {activeKeys.length > 0 && (
            <div className="space-y-2">
              {activeKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-800/30 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-50">
                      {key.name}
                    </p>
                    <p className="text-xs text-gray-500 font-mono">
                      {key.key_prefix}... &middot; Created{" "}
                      {new Date(key.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400 hover:text-red-300"
                    onClick={() => handleRevokeKey(key.id)}
                  >
                    Revoke
                  </Button>
                </div>
              ))}
            </div>
          )}
          {revokedKeys.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Revoked Keys
              </h4>
              {revokedKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between rounded-lg border border-gray-800/50 bg-gray-900/30 px-4 py-3 opacity-50"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-400 line-through">
                      {key.name}
                    </p>
                    <p className="text-xs text-gray-600 font-mono">
                      {key.key_prefix}... &middot; Revoked{" "}
                      {new Date(key.revoked_at!).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Connect to Kutana */}
      <Card>
        <CardHeader>
          <CardTitle>Connect to Kutana</CardTitle>
          <p className="text-sm text-gray-400">
            Choose an integration method to connect your agent. Your API key
            authenticates requests — no Docker or server setup required.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="border-gray-800 bg-gray-900/50">
              <CardHeader>
                <CardTitle className="text-base">Claude Code</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-400 mb-4">
                  Connect via the channel server integration for Claude Code
                  agents.
                </p>
                <Link to="/docs/claude-code-channel">
                  <Button variant="outline" size="sm" className="w-full">
                    View Guide
                  </Button>
                </Link>
              </CardContent>
            </Card>

            <Card className="border-gray-800 bg-gray-900/50">
              <CardHeader>
                <CardTitle className="text-base">OpenClaw</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-400 mb-4">
                  Use the OpenClaw skill to connect agents with built-in meeting
                  capabilities.
                </p>
                <Link to="/docs/openclaw-skill">
                  <Button variant="outline" size="sm" className="w-full">
                    View Guide
                  </Button>
                </Link>
              </CardContent>
            </Card>

            <Card className="border-gray-800 bg-gray-900/50">
              <CardHeader>
                <CardTitle className="text-base">Other Agents (MCP)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-400 mb-4">
                  Connect any MCP-compatible agent using the generic quickstart
                  guide.
                </p>
                <Link to="/docs/mcp-server">
                  <Button variant="outline" size="sm" className="w-full">
                    View Guide
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      {/* Create Key Dialog */}
      <Dialog open={showCreateKey} onClose={() => setShowCreateKey(false)}>
        <form onSubmit={handleCreateKey}>
          <DialogTitle>Generate API Key</DialogTitle>
          <Input
            label="Key Name"
            placeholder="e.g., claude-desktop-key"
            value={keyName}
            onChange={(e) => setKeyName(e.target.value)}
            required
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreateKey(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isCreatingKey}>
              {isCreatingKey ? "Generating..." : "Generate"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
      >
        <DialogTitle>Delete Agent</DialogTitle>
        <p className="text-sm text-gray-400">
          Are you sure you want to delete <strong>{agent.name}</strong>? This
          action cannot be undone. All associated API keys will be revoked.
        </p>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setShowDeleteConfirm(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete Agent"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
