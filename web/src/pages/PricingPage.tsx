import LandingNav from "@/components/landing/LandingNav";
import { PricingSection } from "@/components/landing/PricingSection";
import { LandingFooter } from "@/components/landing/LandingFooter";

export function PricingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 to-[#131318] text-white">
      <LandingNav />
      <div className="pt-20">
        <PricingSection />
      </div>
      <LandingFooter />
    </div>
  );
}
