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
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 to-[#131318] text-white">
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
