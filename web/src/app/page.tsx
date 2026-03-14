"use client";

import Link from 'next/link';
import Image from 'next/image';
import React from 'react';
import { useRouter } from 'next/navigation';
import { Space_Grotesk } from "next/font/google";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Zap, Layout, Sparkles, Play, ArrowRight, ShieldCheck, Cpu } from "lucide-react";

const displayFont = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "700"],
});

const pipelineStages = [
  "Source Input",
  "Signal Extraction",
  "Scene Planning",
  "Interleaved Generation",
  "Final Media Bundle",
];

type CollageTile = {
  src: string;
  alt: string;
  className: string;
  fit?: "cover" | "contain";
};

const collageTiles: CollageTile[] = [
  { src: "/humanity/vitruvian.jpg", alt: "Vitruvian Man by Leonardo da Vinci", className: "tile-1", fit: "contain" },
  { src: "/humanity/mandelbrot.jpg", alt: "Mandelbrot fractal set visualization", className: "tile-2", fit: "cover" },
];

export default function Home() {
  const router = useRouter();
  const [modeDialogOpen, setModeDialogOpen] = React.useState(false);

  React.useEffect(() => {
    const storedChoice = window.sessionStorage.getItem("explainflow.entry_choice");
    if (!storedChoice) {
      setModeDialogOpen(true);
    }
  }, []);

  const handleEntryChoice = (mode: "quick" | "advanced") => {
    window.sessionStorage.setItem("explainflow.entry_choice", mode);
    setModeDialogOpen(false);
    router.push(mode === "quick" ? "/quick" : "/advanced");
  };

  const handleStayOnLanding = () => {
    window.sessionStorage.setItem("explainflow.entry_choice", "landing");
    setModeDialogOpen(false);
  };

  return (
    <div className="landing-home-shell relative isolate min-h-screen overflow-x-clip text-slate-100 selection:bg-cyan-300/30">
      <div className="landing-bg landing-bg-home pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
        <div className="landing-aurora" />
        <div className="landing-grid" />
        <div className="landing-noise" />
        <div className="landing-collage">
          {collageTiles.map((tile) => (
            <div key={tile.src} className={`collage-tile ${tile.className}`}>
              <Image
                src={tile.src}
                alt={tile.alt}
                fill
                sizes="(max-width: 768px) 45vw, 24vw"
                className={tile.fit === "contain" ? "object-contain p-4 md:p-6" : "object-cover"}
              />
              <div className="collage-tile-frame" />
              <div className="collage-tile-glow" />
            </div>
          ))}
        </div>
        <div className="landing-flow-map">
          <div className="flow-line" />
          {pipelineStages.map((stage, idx) => (
            <div key={stage} className={`flow-stage flow-stage-${idx + 1}`}>
              <span className="flow-dot" />
              <span className="flow-label">{stage}</span>
            </div>
          ))}
        </div>
        <div className="landing-orb landing-orb-a" />
        <div className="landing-orb landing-orb-b" />
        <div className="landing-orb landing-orb-c" />
        <div className="landing-rings">
          <div className="landing-ring landing-ring-a" />
          <div className="landing-ring landing-ring-b" />
          <div className="landing-ring landing-ring-c" />
        </div>
      </div>

      <main className="relative z-10 container mx-auto px-6 py-12 lg:py-20">
        <div className="mx-auto mb-24 flex max-w-5xl flex-col items-center text-center space-y-8">
          <Badge
            variant="secondary"
            className="rounded-full border border-cyan-300/25 bg-slate-900/65 px-5 py-2 text-sm font-medium text-cyan-100 shadow-sm backdrop-blur-md animate-in fade-in slide-in-from-bottom-4 duration-1000"
          >
            <Sparkles className="w-3.5 h-3.5 mr-2 text-cyan-100" />
            AI-Powered Multimodal Explainer
          </Badge>

          <h1 className={`${displayFont.className} text-5xl md:text-7xl font-bold tracking-tight lg:leading-[1.05] max-w-4xl drop-shadow-[0_2px_18px_rgba(2,6,23,0.75)] animate-in fade-in slide-in-from-bottom-6 duration-1000 delay-200`}>
            Turn complex ideas into{" "}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-200 via-blue-200 to-indigo-200">
              visual stories.
            </span>
          </h1>

          <p className="max-w-2xl text-xl text-slate-200/95 drop-shadow-[0_1px_10px_rgba(2,6,23,0.65)] animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
            ExplainFlow turns any input into a live-streamed pipeline of
            interleaved text, cinematic visuals, and professional audio.
          </p>

          <div className="grid w-full max-w-3xl grid-cols-2 gap-3 pt-2 text-left md:grid-cols-4">
            <div className="rounded-2xl border border-slate-400/30 bg-slate-900/58 px-4 py-3 backdrop-blur-md">
              <p className="text-[11px] uppercase tracking-wide text-slate-300">Output</p>
              <p className="text-sm font-semibold text-slate-100">Text + Image + Audio</p>
            </div>
            <div className="rounded-2xl border border-slate-400/30 bg-slate-900/58 px-4 py-3 backdrop-blur-md">
              <p className="text-[11px] uppercase tracking-wide text-slate-300">Latency</p>
              <p className="text-sm font-semibold text-slate-100">Scene-by-scene stream</p>
            </div>
            <div className="rounded-2xl border border-slate-400/30 bg-slate-900/58 px-4 py-3 backdrop-blur-md">
              <p className="text-[11px] uppercase tracking-wide text-slate-300">Control</p>
              <p className="text-sm font-semibold text-slate-100">Audience + Taste Bar</p>
            </div>
            <div className="rounded-2xl border border-slate-400/30 bg-slate-900/58 px-4 py-3 backdrop-blur-md">
              <p className="text-[11px] uppercase tracking-wide text-slate-300">Flow</p>
              <p className="text-sm font-semibold text-slate-100">Prompt to media bundle</p>
            </div>
          </div>
        </div>

        <div className="relative mx-auto mb-24 max-w-5xl">
          <div
            className="pointer-events-none absolute inset-x-12 -inset-y-8 rounded-[40px] bg-[radial-gradient(circle_at_center,_rgba(56,189,248,0.12),_transparent_48%),radial-gradient(circle_at_70%_35%,_rgba(99,102,241,0.12),_transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.18),rgba(15,23,42,0.04))] blur-2xl"
            aria-hidden
          />
          <div className="relative grid gap-8 md:grid-cols-2">
          <Link href="/quick" className="group">
            <Card className="h-full border border-slate-300/20 bg-slate-900/65 shadow-[0_24px_60px_rgba(15,23,42,0.28)] backdrop-blur-xl transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_28px_80px_rgba(6,182,212,0.22)]">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-300/30 bg-cyan-500/15 transition-transform group-hover:scale-110">
                  <Zap className="h-6 w-6 text-cyan-200" />
                </div>
                <CardTitle className="text-2xl text-slate-100">Quick Generate</CardTitle>
                <CardDescription className="text-base text-slate-300">
                  Ideal for rapid brainstorming. One prompt, one click,
                  and a complete explainer starts streaming instantly.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex items-center font-medium text-slate-100">
                Try it now <ArrowRight className="ml-2 w-4 h-4" />
              </CardContent>
            </Card>
          </Link>

          <Link href="/advanced" className="group">
            <Card className="h-full border border-slate-300/20 bg-slate-900/65 shadow-[0_24px_60px_rgba(15,23,42,0.28)] backdrop-blur-xl transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_28px_80px_rgba(30,64,175,0.22)]">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-indigo-300/30 bg-indigo-500/15 transition-transform group-hover:scale-110">
                  <Layout className="h-6 w-6 text-indigo-200" />
                </div>
                <CardTitle className="text-2xl text-slate-100">Advanced Studio</CardTitle>
                <CardDescription className="text-base text-slate-300">
                  For professional creators. Ingest long documents,
                  control visual mode, define audience persona, and set taste bars.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex items-center font-medium text-slate-100">
                Enter Studio <ArrowRight className="ml-2 w-4 h-4" />
              </CardContent>
            </Card>
          </Link>
          </div>
        </div>

        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 border-t border-slate-500/30 pt-16 text-center md:grid-cols-4">
          <div className="space-y-2 rounded-2xl border border-slate-400/25 bg-slate-900/58 p-4 backdrop-blur-md">
            <div className="flex justify-center">
              <Cpu className="w-6 h-6 text-slate-300" />
            </div>
            <p className="font-bold text-slate-100">Gemini 3.1 Pro</p>
            <p className="text-sm text-slate-300">Extraction & logic</p>
          </div>
          <div className="space-y-2 rounded-2xl border border-slate-400/25 bg-slate-900/58 p-4 backdrop-blur-md">
            <div className="flex justify-center">
              <Play className="w-6 h-6 text-slate-300" />
            </div>
            <p className="font-bold text-slate-100">Nano Banana Pro</p>
            <p className="text-sm text-slate-300">Multimodal streaming</p>
          </div>
          <div className="space-y-2 rounded-2xl border border-slate-400/25 bg-slate-900/58 p-4 backdrop-blur-md">
            <div className="flex justify-center">
              <ShieldCheck className="w-6 h-6 text-slate-300" />
            </div>
            <p className="font-bold text-slate-100">GCP Hosted</p>
            <p className="text-sm text-slate-300">Cloud Run architecture</p>
          </div>
          <div className="space-y-2 rounded-2xl border border-slate-400/25 bg-slate-900/58 p-4 backdrop-blur-md">
            <div className="flex justify-center">
              <Sparkles className="w-6 h-6 text-slate-300" />
            </div>
            <p className="font-bold text-slate-100">Infinite Styles</p>
            <p className="text-sm text-slate-300">Dynamic art direction</p>
          </div>
        </div>
      </main>

      <footer className="relative z-10 border-t border-slate-500/30 py-12 text-center text-slate-300">
        <p>© 2026 ExplainFlow • Built for Gemini Live Agent Challenge</p>
        <p className="mt-2 text-xs text-slate-400">Collage includes Wikimedia Commons assets + custom formula art.</p>
      </footer>

      <Dialog open={modeDialogOpen} onOpenChange={setModeDialogOpen}>
        <DialogContent className="bg-white text-slate-900 border-slate-300">
          <DialogHeader>
            <DialogTitle>What Are You Building Today?</DialogTitle>
            <DialogDescription className="text-slate-600">
              Choose your session mode and jump directly into the right workflow.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Button type="button" className="w-full" onClick={() => handleEntryChoice("quick")}>
              Quick Generate
            </Button>
            <Button type="button" variant="outline" className="w-full border-slate-300" onClick={() => handleEntryChoice("advanced")}>
              Advanced Studio
            </Button>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" className="text-slate-600" onClick={handleStayOnLanding}>
              Stay On Landing
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
