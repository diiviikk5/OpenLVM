import Navbar from "./components/Navbar";
import HeroSection from "./components/HeroSection";
import FeaturesSection from "./components/FeaturesSection";
import HowItWorksSection from "./components/HowItWorksSection";
import ArchitectureSection from "./components/ArchitectureSection";
import CLISection from "./components/CLISection";
import ComparisonSection from "./components/ComparisonSection";
import CTASection from "./components/CTASection";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <HeroSection />
        <FeaturesSection />
        <HowItWorksSection />
        <ArchitectureSection />
        <CLISection />
        <ComparisonSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
