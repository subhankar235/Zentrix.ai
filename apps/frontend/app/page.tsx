import { Nav } from "@/components/landing/nav";
import { Hero } from "@/components/landing/hero";
import { Evidence } from "@/components/landing/evidence";
import { Agents } from "@/components/landing/agents";
import { Sandbox } from "@/components/landing/sandbox";
import { Loop } from "@/components/landing/loop";
import { Roi } from "@/components/landing/roi";
import { Cta, Footer } from "@/components/landing/cta";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main>
        <Hero />
        <Evidence />
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
