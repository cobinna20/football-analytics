"use client";
import { useState, useEffect, useMemo, useCallback } from "react";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "https://football-analytics-8khk.onrender.com").replace(/\/$/, "");

function safeArray(v: any): any[] {
  return Array.isArray(v) ? v : [];
}
function safeStr(v: any, fallback = ""): string {
  if (v === null || v === undefined) return fallback;
  try { return String(v); } catch { return fallback; }
}
function safeNum(v: any, fallback = 0): number {
  const n = Number(v);
  return isNaN(n) ? fallback : n;
}
function getTeamName(team: any): string {
  if (!team) return "TBD";
  return team.short_name || team.name || team.shortName || "TBD";
}
function formatTime(dateStr: any): string {
  try {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "";
    return d.toISOString().slice(11, 16) + " UTC";
  } catch { return ""; }
}
function makeDates(): string[] {
  const out: string[] = [];
  try {
    const today = new Date();
    today.setHours(12, 0, 0, 0);
    for (let i = -7; i <= 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      out.push(d.toISOString().slice(0, 10));
    }
  } catch {}
  return out;
}
function dateLabel(dateStr: string, idx: number): string {
  try {
    const d = new Date(dateStr + "T12:00:00Z");
    const names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const dayName = names[d.getUTCDay()] || "";
    const short = dateStr.slice(5).replace("-", "-");
    if (idx === 7) return `Today ${short}`;
    if (idx === 6) return `Yesterday ${short}`;
    if (idx === 8) return `Tomorrow ${short}`;
    return `${dayName} ${short}`;
  } catch { return dateStr; }
}

export default function Home() {
  const dates = useMemo(() => makeDates(), []);
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    try { return new Date().toISOString().slice(0, 10); } catch { return "2026-11-24"; }
  });
  const [fixtures, setFixtures] = useState<any[]>([]);
  const [leagues, setLeagues] = useState<any[]>([]);
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");
  const [selectedFixtureId, setSelectedFixtureId] = useState<string | null>(null);
  const [bundle, setBundle] = useState<any>(null);
  const [prediction, setPrediction] = useState<any>(null);
  const [loadingFixtures, setLoadingFixtures] = useState(false);
  const [loadingPred, setLoadingPred] = useState(false);
  const [homeRest, setHomeRest] = useState(7);
  const [awayRest, setAwayRest] = useState(7);
  const [homeMissing, setHomeMissing] = useState(0);
  const [awayMissing, setAwayMissing] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const selectedFixture = useMemo(() => {
    if (!selectedFixtureId) return null;
    const found = safeArray(fixtures).find((f: any) => safeStr(f?.id) === safeStr(selectedFixtureId));
    return found || null;
  }, [fixtures, selectedFixtureId]);

  const loadFixtures = useCallback(async (dateStr: string) => {
    setLoadingFixtures(true);
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/fixtures?date=${dateStr}`, { cache: "no-store" });
      if (!res.ok) {
        setFixtures([]);
        setLeagues([]);
        setErrorMsg("No fixtures. Check backend.");
        return;
      }
      const data = await res.json().catch(() => []);
      const arr = safeArray(data);
      setFixtures(arr);
      // Build leagues from fixtures only, so leagues shown are only leagues that have matches that day
      const map: any = {};
      arr.forEach((f: any) => {
        const code = safeStr(f?.league_code || f?.competition, "OTHER");
        const name = safeStr(f?.league_name, code);
        if (!map[code]) map[code] = { code, name, count: 0 };
        map[code].count += 1;
      });
      const leagueList = Object.values(map);
      setLeagues(leagueList as any[]);
    } catch (e) {
      setFixtures([]);
      setLeagues([]);
      setErrorMsg("No fixtures. Check backend.");
    } finally {
      setLoadingFixtures(false);
    }
  }, []);

  // Load fixtures when date changes, and RESET everything to prevent crash
  useEffect(() => {
    setSelectedLeague("ALL");
    setSelectedFixtureId(null);
    setBundle(null);
    setPrediction(null);
    setHomeRest(7);
    setAwayRest(7);
    setHomeMissing(0);
    setAwayMissing(0);
    setErrorMsg("");
    if (selectedDate) loadFixtures(selectedDate);
  }, [selectedDate, loadFixtures]);

  const loadBundle = useCallback(async (fixtureId: string) => {
    setLoadingPred(true);
    try {
      const res = await fetch(`${API_BASE}/api/match-bundle?fixture_id=${fixtureId}`, { cache: "no-store" });
      if (!res.ok) {
        setBundle(null);
        setPrediction(null);
        return;
      }
      const data = await res.json().catch(() => null);
      if (!data || data.error) {
        setBundle(null);
        setPrediction(null);
        return;
      }
      setBundle(data);
      const pred = data.prediction || null;
      setPrediction(pred);
      const r = data.rest || {};
      setHomeRest(safeNum(r.home_rest ?? data.home_rest, 7));
      setAwayRest(safeNum(r.away_rest ?? data.away_rest, 7));
      setHomeMissing(0);
      setAwayMissing(0);
    } catch {
      setBundle(null);
      setPrediction(null);
    } finally {
      setLoadingPred(false);
    }
  }, []);

  const recalcPrediction = useCallback(async () => {
    if (!selectedFixtureId) return;
    setLoadingPred(true);
    try {
      const res = await fetch(`${API_BASE}/api/fixtures/${selectedFixtureId}/predict?home_rest_days=${homeRest}&away_rest_days=${awayRest}&home_missing_key=${homeMissing}&away_missing_key=${awayMissing}`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json().catch(() => null);
      if (data && !data.error) setPrediction(data);
    } catch {} finally { setLoadingPred(false); }
  }, [selectedFixtureId, homeRest, awayRest, homeMissing, awayMissing]);

  const filteredFixtures = useMemo(() => {
    const arr = safeArray(fixtures);
    if (selectedLeague === "ALL") return arr;
    return arr.filter((f: any) => safeStr(f?.league_code || f?.competition) === selectedLeague);
  }, [fixtures, selectedLeague]);

  const playedCount = useMemo(() => safeArray(fixtures).filter((f: any) => f?.status === "FINISHED").length, [fixtures]);

  const handleFixtureTap = (fixture: any) => {
    try {
      const id = safeStr(fixture?.id);
      if (!id) return;
      setSelectedFixtureId(id);
      setBundle(null);
      setPrediction(null);
      loadBundle(id);
    } catch {}
  };

  return (
    <div style={{ background: "#0f172a", minHeight: "100vh", color: "white", padding: 16, fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: 34, fontWeight: 800, lineHeight: 1.1, marginBottom: 8 }}>Match Centre +<br />Prediction</h1>
      <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 16 }}>1. Pick a date. 2. Pick a league that has matches that day. 3. Pick a match. 4. See prediction below.</p>

      <div style={{ fontWeight: 700, marginBottom: 8 }}>📅 Date - 7 days ago to 7 days ahead</div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 8 }}>
        {safeArray(dates).map((d: string, idx: number) => {
          const active = d === selectedDate;
          return (
            <button key={d} onClick={() => setSelectedDate(d)} style={{ flexShrink: 0, background: active ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 12, padding: "10px 14px", cursor: "pointer", fontWeight: active ? 700 : 400 }}>
              <div style={{ fontSize: 12 }}>{dateLabel(d, idx)}</div>
              <div style={{ fontSize: 13 }}>{d.slice(5)}</div>
            </button>
          );
        })}
      </div>

      <div style={{ fontWeight: 700, marginTop: 16, marginBottom: 8 }}>🏆 Leagues with matches on {selectedDate} ({safeArray(fixtures).length} matches, {playedCount} played)</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={() => setSelectedLeague("ALL")} style={{ background: selectedLeague === "ALL" ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "10px 16px", cursor: "pointer" }}>All leagues ({safeArray(fixtures).length})</button>
        {safeArray(leagues).map((l: any) => {
          const code = safeStr(l?.code);
          const name = safeStr(l?.name, code);
          const count = safeNum(l?.count, 0);
          const active = selectedLeague === code;
          return (
            <button key={code} onClick={() => setSelectedLeague(code)} style={{ background: active ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "10px 16px", cursor: "pointer" }}>{name} ({count})</button>
          );
        })}
      </div>
      {safeArray(fixtures).length === 0 && !loadingFixtures && <div style={{ color: "#94a3b8", marginTop: 12 }}>{errorMsg || "No matches on this date. Try another date."}</div>}
      {loadingFixtures && <div style={{ color: "#94a3b8", marginTop: 12 }}>Loading fixtures...</div>}

      <div style={{ fontWeight: 700, marginTop: 20, marginBottom: 8 }}>⚽ Matches - {selectedDate}</div>
      {safeArray(filteredFixtures).length === 0 && !loadingFixtures && <div style={{ color: "#94a3b8" }}>No matches for this league on this date.</div>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {safeArray(filteredFixtures).map((f: any) => {
          const id = safeStr(f?.id);
          const home = getTeamName(f?.home_team);
          const away = getTeamName(f?.away_team);
          const active = id === selectedFixtureId;
          const isFinished = f?.status === "FINISHED";
          return (
            <button key={id} onClick={() => handleFixtureTap(f)} style={{ background: active ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "12px 16px", cursor: "pointer", textAlign: "left" }}>
              <div style={{ fontSize: 15 }}>{home} vs {away}</div>
              <div style={{ fontSize: 12, color: "#cbd5e1", textAlign: "center" }}>{isFinished ? `${safeStr(f?.home_score, "-")} - ${safeStr(f?.away_score, "-")} • FT` : formatTime(f?.date)}</div>
            </button>
          );
        })}
      </div>

      {!selectedFixture && <div style={{ color: "#94a3b8", marginTop: 20 }}>{safeArray(fixtures).length === 0 ? "No fixtures. Check backend." : "Tap a match to see prediction."}</div>}

      {selectedFixture && (
        <div style={{ marginTop: 24, background: "#1e293b", borderRadius: 16, padding: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{getTeamName(selectedFixture?.home_team)} vs {getTeamName(selectedFixture?.away_team)}</div>
          <div style={{ color: "#94a3b8", fontSize: 13, marginTop: 4 }}>{safeStr(selectedFixture?.league_name)} • {formatTime(selectedFixture?.date)}</div>

          <div style={{ fontWeight: 700, marginTop: 16 }}>What-If - Rest and Missing Player</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
            <div>Home Rest: {homeRest} days<br /><input type="range" min={1} max={14} value={homeRest} onChange={(e) => setHomeRest(safeNum(e.target.value, 7))} /></div>
            <div>Away Rest: {awayRest} days<br /><input type="range" min={1} max={14} value={awayRest} onChange={(e) => setAwayRest(safeNum(e.target.value, 7))} /></div>
            <div>Home Missing: {homeMissing}<br /><input type="range" min={0} max={5} value={homeMissing} onChange={(e) => setHomeMissing(safeNum(e.target.value, 0))} /></div>
            <div>Away Missing: {awayMissing}<br /><input type="range" min={0} max={5} value={awayMissing} onChange={(e) => setAwayMissing(safeNum(e.target.value, 0))} /></div>
          </div>
          <button onClick={recalcPrediction} style={{ marginTop: 12, background: "#10b981", color: "white", border: "none", borderRadius: 12, padding: "10px 16px", cursor: "pointer", fontWeight: 700 }}>Recalculate Prediction</button>
          <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 6 }}>Auto Rest is loaded from real last match. Move the sliders to test What-If.</div>

          <div style={{ fontWeight: 700, marginTop: 16 }}>Prediction</div>
          {loadingPred && <div style={{ color: "#94a3b8" }}>Loading prediction...</div>}
          {!loadingPred && !prediction && <div style={{ color: "#94a3b8" }}>No prediction yet. Tap Recalculate.</div>}
          {prediction && (
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, marginTop: 8 }}>Predicted Score: {safeStr(prediction?.predicted_score, `${safeStr(prediction?.predicted_home_goals, "-")} - ${safeStr(prediction?.predicted_away_goals, "-")}`)}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Home Win<br /><b>{(safeNum(prediction?.home_win_prob ?? prediction?.home_win, 0) * 100).toFixed(1)}%</b></div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Draw<br /><b>{(safeNum(prediction?.draw_prob ?? prediction?.draw, 0) * 100).toFixed(1)}%</b></div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Away Win<br /><b>{(safeNum(prediction?.away_win_prob ?? prediction?.away_win, 0) * 100).toFixed(1)}%</b></div>
              </div>
              <div style={{ color: "#cbd5e1", fontSize: 13, marginTop: 10 }}>{safeStr(prediction?.explanation, "")}</div>
              <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 6 }}>Confidence: {(safeNum(prediction?.confidence, 0) * 100).toFixed(1)}%</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
