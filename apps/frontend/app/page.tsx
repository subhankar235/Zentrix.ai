import { Nav } from "@/components/landing/nav";
import { Hero } from "@/components/landing/hero";
import { HeroVisual } from "@/components/landing/hero-visuals";
import { Evidence } from "@/components/landing/evidence";
import { Agents } from "@/components/landing/agents";
import { Sandbox } from "@/components/landing/sandbox";
import { Loop } from "@/components/landing/loop";
import { Pipeline } from "@/components/landing/howItworks";
import { Roi } from "@/components/landing/roi";
import { Cta, Footer } from "@/components/landing/cta";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main>
        <Hero />
        <HeroVisual />
        <Evidence />
        <Pipeline />
        <Agents />
        <Sandbox />
        <Loop />
        <Roi />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}