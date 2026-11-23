"use client";
import { useEffect, useMemo, useState } from "react";
import { getFixtures, getLeagues, type Fixture, type League } from "@/lib/api";
import { getPrediction, getTeamStats, type Prediction, type TeamStats } from "@/lib/predict";
import PredictionCard from "@/components/PredictionCard";
import WhatIfSimulator, { type SimContext } from "@/components/WhatIfSimulator";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://football-analytics-8khk.onrender.com";

function fmtDate(d: Date) { return d.toISOString().slice(0, 10); }
function dayLabel(iso: string) {
  const d = new Date(iso + "T12:00:00");
  const today = fmtDate(new Date());
  if (iso === today) return "Today";
  const t = new Date(today + "T12:00:00"); const diff = Math.round((d.getTime() - t.getTime()) / 86400000);
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString("en-GB", { weekday: "short" });
}

export default function Home() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>(fmtDate(new Date()));
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");
  const [selectedId, setSelectedId] = useState<string>("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [homeStats, setHomeStats] = useState<TeamStats | null>(null);
  const [awayStats, setAwayStats] = useState<TeamStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [context, setContext] = useState<SimContext>({ home_rest_days: 7, away_rest_days: 7, home_missing_key: 0, away_missing_key: 0 });

  const dates = useMemo(() => {
    const arr: string[] = [];
    const today = new Date();
    for (let i = -7; i <= 7; i++) { const d = new Date(today); d.setDate(today.getDate() + i); arr.push(fmtDate(d)); }
    return arr;
  }, []);

  useEffect(() => {
    Promise.all([getFixtures("ALL"), getLeagues()]).then(([f, l]) => {
      setFixtures(f); setLeagues(l); setLoading(false);
      const todayF = f.filter((x) => x.date.slice(0, 10) === fmtDate(new Date()));
      if (todayF.length > 0) setSelectedId(todayF[0].id);
      else if (f.length > 0) { setSelectedId(f[0].id); setSelectedDate(f[0].date.slice(0, 10)); }
    });
  }, []);

  const fixturesForDate = useMemo(() => fixtures.filter((f) => f.date.slice(0, 10) === selectedDate), [fixtures, selectedDate]);
  const leaguesForDate = useMemo(() => {
    const map = new Map<string, string>();
    fixturesForDate.forEach((f) => map.set(f.league_code || f.competition, f.league_name || f.league_code));
    return Array.from(map.entries()).map(([code, name]) => ({ code, name }));
  }, [fixturesForDate]);

  const visibleFixtures = useMemo(() => {
    if (selectedLeague === "ALL") return fixturesForDate;
    return fixturesForDate.filter((f) => (f.league_code || f.competition) === selectedLeague);
  }, [fixturesForDate, selectedLeague]);

  // PHASE B: AUTO REST - when you tap a new match, fetch real rest from backend and auto-fill What-If
  useEffect(() => {
    if (!selectedId) return;
    const fx = fixtures.find((x) => x.id === selectedId);
    if (!fx) return;
    const homeId = fx.home_team.id;
    const awayId = fx.away_team.id;
    const fixtureDate = fx.date.slice(0, 10);
    if (!homeId || !awayId || !fixtureDate) return;
    fetch(`${API_BASE}/api/rest-both?home_team_id=${homeId}&away_team_id=${awayId}&fixture_date=${fixtureDate}`)
      .then((r) => r.json())
      .then((d) => {
        if (typeof d.home_rest === "number" && typeof d.away_rest === "number") {
          setContext((prev) => ({ ...prev, home_rest_days: d.home_rest, away_rest_days: d.away_rest, home_missing_key: 0, away_missing_key: 0 }));
        }
      })
      .catch(() => {});
  }, [selectedId, fixtures]);

  useEffect(() => {
    if (!selectedId) return;
    setPrediction(null);
    const fx = fixtures.find((x) => x.id === selectedId);
    if (!fx) return;
    getPrediction(selectedId, context).then(setPrediction);
    getTeamStats(fx.home_team.id).then(setHomeStats);
    getTeamStats(fx.away_team.id).then(setAwayStats);
  }, [selectedId, fixtures, context]);

  const selected = fixtures.find((f) => f.id === selectedId);
  const finishedCount = fixturesForDate.filter((f) => f.status === "FINISHED").length;

  return (
    <main className="min-h-screen p-4 md:p-6 max-w-6xl mx-auto space-y-6">
      <header>
        <p className="text-xs tracking-[0.3em] text-emerald-400">FOOTBALL ANALYTICS TERMINAL</p>
        <h1 className="text-3xl md:text-4xl font-bold mt-2">Match Centre + Prediction</h1>
        <p className="text-slate-400 mt-1 text-sm">1. Pick a date. 2. Pick a league that has matches that day. 3. Pick a match. 4. See prediction below.</p>
      </header>

      <div>
        <p className="text-sm font-bold mb-2">📅 Date - 7 days ago to 7 days ahead</p>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {dates.map((d) => (
            <button key={d} onClick={() => { setSelectedDate(d); setSelectedLeague("ALL"); }} className={`shrink-0 px-3 py-2 rounded-xl text-sm ${selectedDate === d ? "bg-emerald-500 text-white" : "bg-slate-800"}`}>
              <span className="block text-xs">{dayLabel(d)}</span><span className="font-bold">{d.slice(5)}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-bold mb-2">🏆 Leagues with matches on {selectedDate} ({fixturesForDate.length} matches, {finishedCount} played)</p>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setSelectedLeague("ALL")} className={`px-4 py-2 rounded-full text-sm ${selectedLeague === "ALL" ? "bg-emerald-500 text-white" : "bg-slate-800"}`}>All leagues ({fixturesForDate.length})</button>
          {leaguesForDate.map((l) => {
            const count = fixturesForDate.filter((f) => (f.league_code || f.competition) === l.code).length;
            return <button key={l.code} onClick={() => setSelectedLeague(l.code)} className={`px-4 py-2 rounded-full text-sm ${selectedLeague === l.code ? "bg-emerald-500 text-white" : "bg-slate-800"}`}>{l.name} ({count})</button>;
          })}
        </div>
        {fixturesForDate.length === 0 && <p className="text-slate-400 text-sm mt-2">No matches on this date. Try another date.</p>}
      </div>

      <div>
        <p className="text-sm font-bold mb-2">⚽ Matches - {selectedDate} {selectedLeague !== "ALL" ? `- ${leaguesForDate.find((l) => l.code === selectedLeague)?.name || selectedLeague}` : ""}</p>
        <div className="flex gap-2 flex-wrap">
          {visibleFixtures.map((f) => (
            <button key={f.id} onClick={() => setSelectedId(f.id)} className={`px-4 py-2 rounded-full text-sm ${selectedId === f.id ? "bg-emerald-500 text-white" : "bg-slate-800"}`}>
              {f.home_team.short_name} {f.status === "FINISHED" ? `${f.home_score}-${f.away_score}` : "vs"} {f.away_team.short_name}
              <span className="block text-[10px] opacity-70">{f.status === "FINISHED" ? "Full Time" : f.date.slice(11, 16) + " UTC"}</span>
            </button>
          ))}
        </div>
        {visibleFixtures.length === 0 && <p className="text-slate-400 text-sm">No matches for this league on this date.</p>}
      </div>

      {loading && <p className="text-slate-400">Loading fixtures...</p>}
      {!loading && fixtures.length === 0 && <p className="text-slate-400">No fixtures. Check backend.</p>}

      {selected && <WhatIfSimulator context={context} onChange={setContext} homeName={selected.home_team.name} awayName={selected.away_team.name} />}
      {prediction && <PredictionCard prediction={prediction} homeStats={homeStats} awayStats={awayStats} />}
      {!prediction && selectedId && <p className="text-slate-400">Loading prediction...</p>}
    </main>
  );
    }
