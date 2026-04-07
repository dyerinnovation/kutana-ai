import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Meeting, Agent } from "@/types";
import { listMeetings } from "@/api/meetings";
import { listAgents } from "@/api/agents";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-600/20 text-green-400 border border-green-500/30",
  scheduled: "bg-blue-600/20 text-blue-400 border border-blue-500/30",
  completed: "bg-gray-600/20 text-gray-400 border border-gray-500/30",
};

export function DashboardPage() {
  const { user } = useAuth();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      listMeetings().then((res) => setMeetings(res.items)),
      listAgents().then((res) => setAgents(res.items)),
    ]).finally(() => setLoading(false));
  }, []);

  const upcomingMeetings = meetings
    .filter((m) => m.status === "scheduled" || m.status === "active")
    .slice(0, 5);

  const recentMeetings = meetings
    .filter((m) => m.status === "completed")
    .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-gray-50">
          Welcome back{user?.name ? `, ${user.name}` : ""}
        </h1>
        <p className="mt-0.5 text-sm text-gray-400">
          Here&apos;s what&apos;s happening across your meetings and agents.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-sm text-gray-500">
          <SpinnerIcon />
          Loading…
        </div>
      )}

      {!loading && (
        <>
          {/* Quick actions */}
          <div className="flex gap-3">
            <Link to="/meetings?create=true">
              <Button variant="outline">
                <CalendarPlusIcon />
                New Meeting
              </Button>
            </Link>
            <Link to="/agents/new">
              <Button variant="outline">
                <PlusIcon />
                New Agent
              </Button>
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Upcoming Meetings */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Upcoming Meetings</CardTitle>
                  <Link to="/meetings" className="text-xs text-blue-400 hover:underline">
                    View all
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                {upcomingMeetings.length === 0 ? (
                  <p className="text-sm text-gray-500 py-4 text-center">
                    No upcoming meetings.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {upcomingMeetings.map((m) => (
                      <li key={m.id}>
                        <Link
                          to={`/meetings/${m.id}/room`}
                          className="flex items-center justify-between rounded-lg border border-gray-800 px-3 py-2 transition-colors hover:bg-gray-800/50"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-gray-200 truncate">
                              {m.title || "Untitled Meeting"}
                            </p>
                            <p className="text-xs text-gray-500">
                              {new Date(m.scheduled_at).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "numeric",
                                minute: "2-digit",
                              })}
                            </p>
                          </div>
                          <div className="ml-2 flex items-center gap-2">
                            {m.status === "active" && (
                              <span className="text-[10px] font-medium text-green-400">Join</span>
                            )}
                            <span
                              className={`inline-flex flex-shrink-0 items-center rounded-md px-2 py-0.5 text-[10px] font-medium ${
                                STATUS_STYLES[m.status] ?? STATUS_STYLES.scheduled
                              }`}
                            >
                              {m.status.charAt(0).toUpperCase() + m.status.slice(1)}
                            </span>
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Your Agents summary */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Your Agents</CardTitle>
                  <Link to="/agents" className="text-xs text-blue-400 hover:underline">
                    View all
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                {agents.length === 0 ? (
                  <div className="text-center py-4">
                    <p className="text-sm text-gray-500 mb-3">No agents yet.</p>
                    <Link to="/agents/new">
                      <Button size="sm">Create your first agent</Button>
                    </Link>
                  </div>
                ) : (
                  <ul className="space-y-2">
                    {agents.slice(0, 5).map((agent) => (
                      <li key={agent.id}>
                        <Link
                          to={`/agents/${agent.id}`}
                          className="flex items-center gap-3 rounded-lg border border-gray-800 px-3 py-2 transition-colors hover:bg-gray-800/50"
                        >
                          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/15 text-xs font-semibold text-blue-400">
                            {agent.name.charAt(0).toUpperCase()}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-gray-200 truncate">
                              {agent.name}
                            </p>
                          </div>
                          <span className="text-[10px] text-gray-500">
                            {agent.capabilities.includes("listen") && agent.capabilities.includes("speak")
                              ? "Voice Agent"
                              : agent.capabilities.includes("speak")
                                ? "Text + Speech"
                                : "Text Only"}
                          </span>
                        </Link>
                      </li>
                    ))}
                    {agents.length > 5 && (
                      <p className="text-center text-xs text-gray-500 pt-1">
                        +{agents.length - 5} more
                      </p>
                    )}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Recent Meetings */}
          {recentMeetings.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Recent Meetings</CardTitle>
                  <Link to="/meetings" className="text-xs text-blue-400 hover:underline">
                    View all
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {recentMeetings.map((m) => (
                    <li key={m.id}>
                      <Link
                        to={`/meetings/${m.id}/room`}
                        className="flex items-center justify-between rounded-lg border border-gray-800 px-3 py-2 transition-colors hover:bg-gray-800/50"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-200 truncate">
                            {m.title || "Untitled Meeting"}
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(m.scheduled_at).toLocaleString(undefined, {
                              month: "short",
                              day: "numeric",
                              hour: "numeric",
                              minute: "2-digit",
                            })}
                          </p>
                        </div>
                        <span className="ml-2 text-[10px] font-medium text-gray-500">
                          View Notes
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg className="mr-2 h-4 w-4 animate-spin text-gray-500" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function CalendarPlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}
