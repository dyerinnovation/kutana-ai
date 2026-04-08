import { useEffect } from "react";
import LandingNav from "@/components/landing/LandingNav";
import HeroSection from "@/components/landing/HeroSection";
import ContextSection from "@/components/landing/ContextSection";
import MeetingDiagramSection from "@/components/landing/MeetingDiagramSection";
import { GettingStartedSection } from "@/components/landing/GettingStartedSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import AgentFlexibilitySection from "@/components/landing/AgentFlexibilitySection";
import { FeedsSection } from "@/components/landing/FeedsSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { EmailCtaSection } from "@/components/landing/EmailCtaSection";
import { UseCasesSection } from "@/components/landing/UseCasesSection";
import { SecuritySection } from "@/components/landing/SecuritySection";
import { LandingFooter } from "@/components/landing/LandingFooter";

export function LandingPage() {
  // Landing page is always dark — force data-theme="dark" so all gray/slate/ink
  // CSS variables resolve to dark-mode values regardless of OS or app theme
  useEffect(() => {
    const html = document.documentElement;
    const prevTheme = html.getAttribute("data-theme");
    const prevBg = document.body.style.backgroundColor;
    html.setAttribute("data-theme", "dark");
    document.body.style.backgroundColor = "#09090b";
    return () => {
      if (prevTheme) html.setAttribute("data-theme", prevTheme);
      else html.removeAttribute("data-theme");
      document.body.style.backgroundColor = prevBg;
    };
  }, []);

  return (
    <div className="min-h-screen text-white" style={{ background: "linear-gradient(135deg, #09090b 0%, #131318 100%)" }}>
      <LandingNav />
      <HeroSection />
      <MeetingDiagramSection />
      <ContextSection />
      <GettingStartedSection />
      <FeaturesSection />
      <AgentFlexibilitySection />
      <FeedsSection />
      <PricingSection />
      <EmailCtaSection />
      <UseCasesSection />
      <SecuritySection />
      <LandingFooter />
    </div>
  );
}
