import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { AgentCreatePage } from "@/pages/AgentCreatePage";
import { AgentDetailPage } from "@/pages/AgentDetailPage";
import { MeetingsPage } from "@/pages/MeetingsPage";
import { MeetingRoomPage } from "@/pages/MeetingRoomPage";
import { AgentTemplatePage } from "@/pages/AgentTemplatePage";

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
        <Route path="/agents/new" element={<AgentCreatePage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/meetings/:id/room" element={<MeetingRoomPage />} />
        <Route path="/templates" element={<AgentTemplatePage />} />
      </Route>
    </Routes>
  );
}
