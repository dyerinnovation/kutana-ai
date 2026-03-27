import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { AgentCreatePage } from "@/pages/AgentCreatePage";
import { AgentDetailPage } from "@/pages/AgentDetailPage";
import { MeetingsPage } from "@/pages/MeetingsPage";
import { MeetingRoomPage } from "@/pages/MeetingRoomPage";
import { DocsPage } from "@/pages/DocsPage";
import { FeedsPage } from "@/pages/FeedsPage";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/new" element={<AgentCreatePage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/meetings/:id/room" element={<MeetingRoomPage />} />
        <Route path="/feeds" element={<FeedsPage />} />
        <Route path="/templates" element={<Navigate to="/agents" replace />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/docs/*" element={<DocsPage />} />
      </Route>
    </Routes>
  );
}
