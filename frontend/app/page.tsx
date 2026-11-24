"use client";
import { useState, useEffect, useMemo, useCallback } from "react";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "https://football-analytics-8khk.onrender.com").replace(/\/$/, "");
function safeArray(v: any): any[] { return Array.isArray(v) ? v : []; }
function safeStr(v: any, f = ""): string { if (v === null || v === undefined) return f; try { return String(v); } catch { return f; } }
function safeNum(v: any, f = 0): number { const n = Number(v); return isNaN(n) ? f : n; }
function getTeamName(t: any): string { if (!t) return "TBD"; return t.short_name || t.name || t.shortName || "TBD"; }
function formatTime(s: any): string { try { if (!s) return ""; const d = new Date(s); if (isNaN(d.getTime())) return ""; return d.toISOString().slice(11, 16) + " UTC"; } catch { return ""; } }
function makeDates(): string[] { const out: string[] = []; try { const today = new Date(); today.setHours(12, 0, 0, 0); for (let i = -7; i <= 7; i++) { const d = new Date(today); d.setDate(today.getDate() + i); out.push(d.toISOString().slice(0, 10)); } } catch {} return out; }
export default function Home() {
  const dates = useMemo(() => makeDates(), []);
  const [selectedDate, setSelectedDate] = useState<string>(() => { try { return new Date().toISOString().slice(0, 10); } catch { return "2026-11-28"; } });
  const [fixtures, setFixtures] = useState<any[]>([]);
  const [leagues, setLeagues] = useState<any[]>([]);
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");
  const [selectedFixtureId, setSelectedFixtureId] = useState<string | null>(null);
  const [bundle, setBundle] = useState<any>(null);
  const [prediction, setPrediction] = useState<any>(null);
  const [loadingFixtures, setLoadingFixtures] = useState(false);
  const [loadingPred, setLoadingPred] = useState(false);
  const [homeRest, setHomeRest] = useState(7); const [awayRest, setAwayRest] = useState(7);
  const [homeMissing, setHomeMissing] = useState(0); const [awayMissing, setAwayMissing] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const selectedFixture = useMemo(() => { if (!selectedFixtureId) return null; return safeArray(fixtures).find((f: any) => safeStr(f?.id) === safeStr(selectedFixtureId)) || null; }, [fixtures, selectedFixtureId]);
  const loadFixtures = useCallback(async (dateStr: string) => {
    setLoadingFixtures(true); setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/fixtures?date=${dateStr}`, { cache: "no-store" });
      if (!res.ok) { setFixtures([]); setLeagues([]); setErrorMsg("No fixtures. Check backend."); return; }
      const data = await res.json().catch(() => []);
      const arr = safeArray(data); setFixtures(arr);
      const map: any = {};
      arr.forEach((f: any) => { const code = safeStr(f?.league_code || f?.competition, "OTHER"); const name = safeStr(f?.league_name, code); if (!map[code]) map[code] = { code, name, count: 0 }; map[code].count += 1; });
      setLeagues(Object.values(map) as any[]);
    } catch { setFixtures([]); setLeagues([]); setErrorMsg("No fixtures. Check backend."); } finally { setLoadingFixtures(false); }
  }, []);
  // FINAL FIX: Changing date clears old match, so it can never crash
  useEffect(() => { setSelectedLeague("ALL"); setSelectedFixtureId(null); setBundle(null); setPrediction(null); setHomeRest(7); setAwayRest(7); setHomeMissing(0); setAwayMissing(0); setErrorMsg(""); if (selectedDate) loadFixtures(selectedDate); }, [selectedDate, loadFixtures]);
  const loadBundle = useCallback(async (fixtureId: string) => {
    if (loadingPred) return;
    setLoadingPred(true); setBundle(null); setPrediction(null);
    try {
      const res = await fetch(`${API_BASE}/api/match-bundle?fixture_id=${fixtureId}`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json().catch(() => null);
      if (!data || data.error) return;
      setBundle(data); setPrediction(data.prediction || null);
      const r = data.rest || {}; setHomeRest(safeNum(r.home_rest ?? data.home_rest, 7)); setAwayRest(safeNum(r.away_rest ?? data.away_rest, 7)); setHomeMissing(0); setAwayMissing(0);
    } catch {} finally { setLoadingPred(false); }
  }, [loadingPred]);
  const recalc = useCallback(async () => {
    if (!selectedFixtureId || loadingPred) return; setLoadingPred(true);
    try { const res = await fetch(`${API_BASE}/api/fixtures/${selectedFixtureId}/predict?home_rest_days=${homeRest}&away_rest_days=${awayRest}&home_missing_key=${homeMissing}&away_missing_key=${awayMissing}`, { cache: "no-store" }); if (!res.ok) return; const data = await res.json().catch(() => null); if (data && !data.error) setPrediction(data); } catch {} finally { setLoadingPred(false); }
  }, [selectedFixtureId, homeRest, awayRest, homeMissing, awayMissing, loadingPred]);
  const filtered = useMemo(() => { const arr = safeArray(fixtures); if (selectedLeague === "ALL") return arr; return arr.filter((f: any) => safeStr(f?.league_code || f?.competition) === selectedLeague); }, [fixtures, selectedLeague]);
  const played = useMemo(() => safeArray(fixtures).filter((f: any) => f?.status === "FINISHED").length, [fixtures]);
  const handleTap = (f: any) => { if (loadingPred) return; try { const id = safeStr(f?.id); if (!id) return; setSelectedFixtureId(id); setBundle(null); setPrediction(null); loadBundle(id); } catch {} };
  const homeStats = bundle?.homeStats || bundle?.home_stats || null; const awayStats = bundle?.awayStats || bundle?.away_stats || null;
  const isDefault = bundle?.is_default === true || (homeStats?.is_default && awayStats?.is_default);
  return (
    <div style={{ background: "#0f172a", minHeight: "100vh", color: "white", padding: 16, fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: 34, fontWeight: 800, lineHeight: 1.1, marginBottom: 8 }}>Match Centre +<br />Prediction</h1>
      <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 16 }}>1. Pick a date. 2. Pick a league. 3. Pick ONE match and WAIT. 4. See real analysis.</p>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>📅 Date - 7 days ago to 7 days ahead</div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 8 }}>{safeArray(dates).map((d: string) => { const active = d === selectedDate; return (<button key={d} onClick={() => { if (!loadingPred) setSelectedDate(d); }} disabled={loadingPred} style={{ flexShrink: 0, background: active ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 12, padding: "10px 14px", cursor: loadingPred ? "not-allowed" : "pointer", opacity: loadingPred ? 0.5 : 1 }}><div>{d.slice(5)}</div></button>); })}</div>
      <div style={{ fontWeight: 700, marginTop: 16, marginBottom: 8 }}>🏆 Leagues with matches on {selectedDate} ({safeArray(fixtures).length} matches, {played} played)</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={() => setSelectedLeague("ALL")} style={{ background: selectedLeague === "ALL" ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "10px 16px", cursor: "pointer" }}>All leagues ({safeArray(fixtures).length})</button>
        {safeArray(leagues).map((l: any) => { const code = safeStr(l?.code); const name = safeStr(l?.name, code); return (<button key={code} onClick={() => setSelectedLeague(code)} style={{ background: selectedLeague === code ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "10px 16px", cursor: "pointer" }}>{name} ({safeNum(l?.count, 0)})</button>); })}
      </div>
      {safeArray(fixtures).length === 0 && !loadingFixtures && <div style={{ color: "#94a3b8", marginTop: 12 }}>{errorMsg || "No matches on this date. Try another date."}</div>}
      {loadingFixtures && <div style={{ color: "#94a3b8", marginTop: 12 }}>Loading fixtures...</div>}
      <div style={{ fontWeight: 700, marginTop: 20, marginBottom: 8 }}>⚽ Matches - {selectedDate} {loadingPred ? "(Loading... do not tap another match)" : ""}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{safeArray(filtered).map((f: any) => { const id = safeStr(f?.id); const active = id === selectedFixtureId; return (<button key={id} onClick={() => handleTap(f)} disabled={loadingPred} style={{ background: active ? "#10b981" : "#1e293b", color: "white", border: "none", borderRadius: 20, padding: "12px 16px", cursor: loadingPred ? "not-allowed" : "pointer", opacity: loadingPred && !active ? 0.5 : 1 }}><div>{getTeamName(f?.home_team)} vs {getTeamName(f?.away_team)}</div><div style={{ fontSize: 12, color: "#cbd5e1", textAlign: "center" }}>{f?.status === "FINISHED" ? `${safeStr(f?.home_score, "-")} - ${safeStr(f?.away_score, "-")} • FT` : formatTime(f?.date)}</div></button>); })}</div>
      {selectedFixture && (
        <div style={{ marginTop: 24, background: "#1e293b", borderRadius: 16, padding: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{getTeamName(selectedFixture?.home_team)} vs {getTeamName(selectedFixture?.away_team)}</div>
          <div style={{ color: "#94a3b8", fontSize: 13 }}>{safeStr(selectedFixture?.league_name)} • {formatTime(selectedFixture?.date)}</div>
          {loadingPred && <div style={{ background: "#fef3c7", color: "#92400e", borderRadius: 12, padding: 12, marginTop: 12, fontWeight: 700 }}>⏳ Fetching REAL analysis... Please wait 10 to 15 seconds. Do not tap another match. Free tier is slow but real.</div>}
          {!loadingPred && isDefault && <div style={{ background: "#fef3c7", color: "#92400e", borderRadius: 12, padding: 10, marginTop: 12, fontSize: 13 }}>⚠️ Showing default Rest 7,7 because limit was hit. Wait 1 minute, then tap this match again to get real Rest.</div>}
          {!loadingPred && bundle && !isDefault && <div style={{ background: "#dcfce7", color: "#166534", borderRadius: 12, padding: 10, marginTop: 12, fontSize: 13 }}>✅ Real analysis loaded. Form and goals are different for each team.</div>}
          {!loadingPred && homeStats && (
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10 }}><b>{getTeamName(selectedFixture?.home_team)}</b><br />Form: {safeArray(homeStats?.form).join(" ") || "N/A"}<br />Goals: {safeStr(homeStats?.goals_for_avg, "-")} scored, {safeStr(homeStats?.goals_against_avg, "-")} conceded<br />Last match: {safeStr(homeStats?.last_match_date, "N/A")}</div>
              <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10 }}><b>{getTeamName(selectedFixture?.away_team)}</b><br />Form: {safeArray(awayStats?.form).join(" ") || "N/A"}<br />Goals: {safeStr(awayStats?.goals_for_avg, "-")} scored, {safeStr(awayStats?.goals_against_avg, "-")} conceded<br />Last match: {safeStr(awayStats?.last_match_date, "N/A")}</div>
            </div>
          )}
          <div style={{ fontWeight: 700, marginTop: 16 }}>What-If - Rest and Missing Player</div>
          <div style={{ color: "#94a3b8", fontSize: 12 }}>Rest is AUTO from real last match. Missing Player is MANUAL What-If, because no free API has 2026 injuries.</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
            <div>Home Rest: {homeRest} days<br /><input type="range" min={1} max={14} value={homeRest} onChange={(e) => setHomeRest(safeNum(e.target.value, 7))} /></div>
            <div>Away Rest: {awayRest} days<br /><input type="range" min={1} max={14} value={awayRest} onChange={(e) => setAwayRest(safeNum(e.target.value, 7))} /></div>
            <div>Home Missing: {homeMissing}<br /><input type="range" min={0} max={5} value={homeMissing} onChange={(e) => setHomeMissing(safeNum(e.target.value, 0))} /></div>
            <div>Away Missing: {awayMissing}<br /><input type="range" min={0} max={5} value={awayMissing} onChange={(e) => setAwayMissing(safeNum(e.target.value, 0))} /></div>
          </div>
          <button onClick={recalc} disabled={loadingPred} style={{ marginTop: 12, background: loadingPred ? "#64748b" : "#10b981", color: "white", border: "none", borderRadius: 12, padding: "10px 16px", cursor: loadingPred ? "not-allowed" : "pointer", fontWeight: 700 }}>Recalculate Prediction</button>
          <div style={{ fontWeight: 700, marginTop: 16 }}>Prediction</div>
          {loadingPred && <div style={{ color: "#94a3b8" }}>Loading prediction...</div>}
          {!loadingPred && !prediction && <div style={{ color: "#94a3b8" }}>No prediction yet. Tap Recalculate.</div>}
          {!loadingPred && prediction && (
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, marginTop: 8 }}>Predicted Score: {safeStr(prediction?.predicted_score, "-")}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Home Win<br /><b>{(safeNum(prediction?.home_win_prob ?? prediction?.home_win, 0) * 100).toFixed(1)}%</b></div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Draw<br /><b>{(safeNum(prediction?.draw_prob ?? prediction?.draw, 0) * 100).toFixed(1)}%</b></div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>Away Win<br /><b>{(safeNum(prediction?.away_win_prob ?? prediction?.away_win, 0) * 100).toFixed(1)}%</b></div>
              </div>
              <div style={{ color: "#cbd5e1", fontSize: 13, marginTop: 10 }}>{safeStr(prediction?.explanation, "")}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
  }
