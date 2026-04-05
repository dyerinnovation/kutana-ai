import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AuthRedirect } from "@/components/AuthRedirect";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { LandingPage } from "@/pages/LandingPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { AgentCreatePage } from "@/pages/AgentCreatePage";
import { AgentDetailPage } from "@/pages/AgentDetailPage";
import { MeetingsPage } from "@/pages/MeetingsPage";
import { MeetingRoomPage } from "@/pages/MeetingRoomPage";
import { AgentTemplatePage } from "@/pages/AgentTemplatePage";
import { DocsPage } from "@/pages/DocsPage";
import { FeedsPage } from "@/pages/FeedsPage";
import { PricingPage } from "@/pages/PricingPage";
import { BillingPage } from "@/pages/BillingPage";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/pricing" element={<PricingPage />} />

      {/* Home: landing page for guests, dashboard for authenticated users */}
      <Route
        path="/"
        element={
          <AuthRedirect
            authenticated={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
            guest={<LandingPage />}
          />
        }
      >
        <Route index element={<DashboardPage />} />
      </Route>

      {/* Protected routes */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/new" element={<AgentCreatePage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/meetings/:id/room" element={<MeetingRoomPage />} />
        <Route path="/feeds" element={<FeedsPage />} />
        <Route path="/templates" element={<AgentTemplatePage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/docs/*" element={<DocsPage />} />
        <Route path="/settings/billing" element={<BillingPage />} />
      </Route>
    </Routes>
  );
}
