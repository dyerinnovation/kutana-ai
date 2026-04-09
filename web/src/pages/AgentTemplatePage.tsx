import { useEffect, useState } from "react";
import type { AgentTemplate } from "@/types";
import { listTemplates } from "@/api/agentTemplates";
import { formatCapability } from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { ActivateTemplateDialog } from "@/components/ActivateTemplateDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  canActivateTemplate,
  planLabel,
  TIER_BADGE_STYLES,
} from "@/lib/planLimits";
import { UpgradeBadge } from "@/components/UpgradeBadge";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "productivity", label: "Productivity" },
  { value: "engineering", label: "Engineering" },
  { value: "general", label: "General" },
];

const CATEGORY_COLORS: Record<string, string> = {
  productivity:
    "bg-blue-600/20 text-blue-400 border border-blue-500/30",
  engineering:
    "bg-cyan-600/20 text-cyan-400 border border-cyan-500/30",
  general:
    "bg-gray-600/20 text-gray-400 border border-gray-500/30",
};

export function AgentTemplatePage() {
  const { user } = useAuth();

  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");

  // Activate modal state
  const [activateTarget, setActivateTarget] = useState<AgentTemplate | null>(
    null
  );

  useEffect(() => {
    loadTemplates();
  }, [categoryFilter]);

  async function loadTemplates() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listTemplates(categoryFilter || undefined);
      setTemplates(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load templates"
      );
      setTemplates([]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-50">Agent Templates</h1>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-900/30 border border-violet-600/30 px-2.5 py-0.5 text-xs font-medium text-violet-300">
            Powered by Claude
          </span>
        </div>
        <p className="text-sm text-gray-400 mt-1">
          Browse and activate prebuilt AI agents for your meetings
        </p>
      </div>

      {/* Category filter */}
      <div className="flex gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategoryFilter(cat.value)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              categoryFilter === cat.value
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-50"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-yellow-800 bg-yellow-950/50 px-4 py-3">
          <p className="text-sm font-medium text-yellow-300">Templates temporarily unavailable</p>
          <p className="text-xs text-yellow-600 mt-0.5">{error}</p>
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          Loading templates...
        </div>
      )}

      {!isLoading && templates.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-400">
              No templates found{categoryFilter ? ` in "${categoryFilter}"` : ""}.
            </p>
          </CardContent>
        </Card>
      )}

      {templates.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {templates.map((template) => {
            const templateTier = template.tier ?? "basic";
            const userCanActivate = canActivateTemplate(user, templateTier);
            return (
              <Card key={template.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <CardTitle>{template.name}</CardTitle>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                          TIER_BADGE_STYLES[templateTier] ?? TIER_BADGE_STYLES.basic
                        }`}
                      >
                        {planLabel(templateTier)}
                      </span>
                      <span
                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                          CATEGORY_COLORS[template.category] ??
                          CATEGORY_COLORS.general
                        }`}
                      >
                        {template.category.charAt(0).toUpperCase() + template.category.slice(1)}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-400 mb-3">
                    {template.description}
                  </p>
                  {template.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {template.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="inline-flex rounded-md bg-gray-800 px-2 py-0.5 text-xs text-gray-400"
                        >
                          {formatCapability(cap)}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    {!userCanActivate && (
                      <UpgradeBadge requiredTier={templateTier as "basic" | "pro" | "business" | "enterprise"} />
                    )}
                    {userCanActivate ? (
                      <Button
                        size="sm"
                        onClick={() => setActivateTarget(template)}
                        className="ml-auto"
                      >
                        Activate
                      </Button>
                    ) : (
                      <Button size="sm" disabled className="ml-auto" title={`Requires ${planLabel(templateTier)} plan`}>
                        Activate
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <ActivateTemplateDialog
        template={activateTarget}
        onClose={() => setActivateTarget(null)}
      />
    </div>
  );
}
