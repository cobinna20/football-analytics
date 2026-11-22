"use client";
import { useEffect, useState } from "react";
import { getFixtures, type Fixture } from "@/lib/api";
import { getPrediction, getTeamStats, type Prediction, type TeamStats } from "@/lib/predict";
import PredictionCard from "@/components/PredictionCard";
import WhatIfSimulator, { type SimContext } from "@/components/WhatIfSimulator";

export default function Home() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [homeStats, setHomeStats] = useState<TeamStats | null>(null);
  const [awayStats, setAwayStats] = useState<TeamStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [context, setContext] = useState<SimContext>({ home_rest_days: 7, away_rest_days: 7, home_missing_key: 0, away_missing_key: 0 });

  useEffect(() => {
    getFixtures().then((f) => {
      setFixtures(f);
      if (f.length > 0) setSelectedId(f[0].id);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const fx = fixtures.find((x) => x.id === selectedId);
    if (!fx) return;
    getPrediction(selectedId, context).then(setPrediction);
    getTeamStats(fx.home_team.id).then(setHomeStats);
    getTeamStats(fx.away_team.id).then(setAwayStats);
  }, [selectedId, fixtures, context]);

  const selected = fixtures.find((f) => f.id === selectedId);

  return (
    <main className="min-h-screen p-4 md:p-6 max-w-6xl mx-auto space-y-6">
      <header>
        <p className="text-xs tracking-[0.3em] text-emerald-400">FOOTBALL ANALYTICS TERMINAL</p>
        <h1 className="text-3xl md:text-4xl font-bold mt-2">Match Centre + Prediction</h1>
        <p className="text-slate-400 mt-1 text-sm">Pick a match, see the guess, then change the What-If to see it update.</p>
      </header>

      <div className="flex gap-2 flex-wrap">
        {fixtures.map((f) => (
          <button key={f.id} onClick={() => setSelectedId(f.id)} className={`px-4 py-2 rounded-full text-sm ${selectedId === f.id ? "bg-emerald-500 text-white" : "bg-slate-800"}`}>
            {f.home_team.short_name} vs {f.away_team.short_name}
          </button>
        ))}
      </div>

      {loading && <p className="text-slate-400">Loading fixtures...</p>}
      {!loading && fixtures.length === 0 && <p className="text-slate-400">No fixtures. Start backend on port 8000.</p>}

      {selected && (
        <WhatIfSimulator context={context} onChange={setContext} homeName={selected.home_team.name} awayName={selected.away_team.name} />
      )}

      {prediction && <PredictionCard prediction={prediction} homeStats={homeStats} awayStats={awayStats} />}
      {!prediction && selectedId && <p className="text-slate-400">Loading prediction...</p>}
    </main>
  );
    }
