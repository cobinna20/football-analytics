"use client";
import { useEffect, useState } from "react";
import { getFixtures, type Fixture } from "@/lib/api";

export default function Home() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getFixtures().then((f) => { setFixtures(f); setLoading(false); });
  }, []);
  return (
    <main className="min-h-screen p-6 max-w-6xl mx-auto">
      <header className="mb-8">
        <p className="text-xs tracking-[0.3em] text-emerald-400">FOOTBALL ANALYTICS TERMINAL</p>
        <h1 className="text-4xl font-bold mt-2">Match Centre</h1>
        <p className="text-slate-400 mt-2">Phase 1: Live ingestion with local fallback. Prediction engine arrives in Phase 2.</p>
      </header>
      {loading && <p className="text-slate-400">Loading fixtures...</p>}
      {!loading && fixtures.length === 0 && <p className="text-slate-400">No fixtures. Start the backend on port 8000.</p>}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {fixtures.map((f) => (
          <div key={f.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex justify-between text-xs text-slate-400"><span>{f.competition} • MD {f.matchday}</span><span>{f.status}</span></div>
            <div className="mt-4 space-y-2">
              <div className="flex justify-between"><span className="font-semibold">{f.home_team.name}</span><span className="text-slate-400">{f.home_team.short_name}</span></div>
              <div className="flex justify-between"><span className="font-semibold">{f.away_team.name}</span><span className="text-slate-400">{f.away_team.short_name}</span></div>
            </div>
            <p className="mt-4 text-sm text-slate-400">{new Date(f.kickoff).toLocaleString()} • {f.venue || "TBD"}</p>
          </div>
        ))}
      </div>
    </main>
  );
      }
