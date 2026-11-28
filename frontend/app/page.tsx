// @ts-nocheck
"use client";
import { useState, useEffect, useMemo, useCallback, useRef } from "react";

const API_BASE = "https://football-analytics-8khk.onrender.com";

function safeArray(v: any) {
  return Array.isArray(v) ? v : [];
}

function safeStr(v: any, f?: any) {
  if (v === null || v === undefined) return f || "";
  try {
    return String(v);
  } catch {
    return f || "";
  }
}

function safeNum(v: any, f?: any) {
  const n = Number(v);
  return isNaN(n) ? (f || 0) : n;
}

function getTeamName(t: any) {
  if (!t) return "TBD";
  return t.short_name || t.name || t.shortName || "TBD";
}

function formatTime(s: any) {
  try {
    if (!s) return "";
    const d = new Date(s);
    if (isNaN(d.getTime())) return "";
    return d.toISOString().slice(11, 16) + " UTC";
  } catch {
    return "";
  }
}

function formatDateShort(s: any) {
  try {
    if (!s) return "";
    return safeStr(s, "").slice(0, 10);
  } catch {
    return "";
  }
}

function makeDates() {
  const out: any = [];
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

function getWorstScore(pred: any) {
  try {
    const s = safeStr(pred?.predicted_score, "");
    if (!s || !s.includes("-")) return "-";
    const parts = s.split("-");
    let h = parseInt(parts[0], 10);
    let a = parseInt(parts[1], 10);
    if (isNaN(h) || isNaN(a)) return "-";
    if (h > a) {
      h = h - 1;
    } else if (a > h) {
      a = a - 1;
    } else {
      a = a + 1;
    }
    if (h < 0) h = 0;
    if (a < 0) a = 0;
    return h + "-" + a;
  } catch {
    return "-";
  }
}

// V4.0 SMART - Use backend smart confidence if present, else fallback to max prob
function getConfidenceRating(pred: any) {
  try {
    if (!pred) return { pct: 0, basePct: 0, label: "-", color: "#64748b", bg: "#1e293b", advice: "", isSmart: false };
    // Backend smart fields
    const smartPct = safeNum(pred?.confidence_pct, 0);
    const smartLabel = safeStr(pred?.confidence_label, "");
    const smartAdvice = safeStr(pred?.confidence_advice, "");
    const basePct = safeNum(pred?.base_confidence_pct, 0);
    if (smartPct > 0 && smartLabel) {
      let color = "#065f46"; let bg = "#10b981";
      if (smartPct >= 70) { bg = "#10b981"; color = "#065f46"; }
      else if (smartPct >= 60) { bg = "#a7f3d0"; color = "#065f46"; }
      else if (smartPct >= 50) { bg = "#f59e0b"; color = "#451a03"; }
      else { bg = "#ef4444"; color = "white"; }
      return { pct: smartPct, basePct: basePct || smartPct, label: smartLabel, color, bg, advice: smartAdvice || "See breakdown below.", isSmart: true };
    }
    // Fallback old logic
    const hw = safeNum(pred?.home_win_prob, 0);
    const dr = safeNum(pred?.draw_prob, 0);
    const aw = safeNum(pred?.away_win_prob, 0);
    const conf = safeNum(pred?.confidence, Math.max(hw, dr, aw));
    const pct = Math.round(conf * 100);
    if (pct >= 70) return { pct, basePct: pct, label: "SUPER LOCK", color: "#065f46", bg: "#10b981", advice: "Very safe. Strong pick. Play Main.", isSmart: false };
    if (pct >= 60) return { pct, basePct: pct, label: "HIGH CONFIDENCE", color: "#065f46", bg: "#a7f3d0", advice: "Good pick. Play Main, cover Worst for safety.", isSmart: false };
    if (pct >= 50) return { pct, basePct: pct, label: "MEDIUM CONFIDENCE", color: "#451a03", bg: "#f59e0b", advice: "Play Main + cover Worst. Small stake only.", isSmart: false };
    return { pct, basePct: pct, label: "LOW - HIGH RISK TRAP - SKIP", color: "white", bg: "#ef4444", advice: "Skip this match. Too risky. Do not chase it.", isSmart: false };
  } catch {
    return { pct: 0, basePct: 0, label: "-", color: "#64748b", bg: "#1e293b", advice: "", isSmart: false };
  }
}

export default function Home() {
  const dates = useMemo(() => makeDates(), []);
  const [selectedDate, setSelectedDate] = useState(() => {
    try {
      return new Date().toISOString().slice(0, 10);
    } catch {
      return "2026-11-28";
    }
  });
  const [fixtures, setFixtures] = useState<any>([]);
  const [leagues, setLeagues] = useState<any>([]);
  const [selectedLeague, setSelectedLeague] = useState("ALL");
  const [selectedFixtureId, setSelectedFixtureId] = useState<any>(null);
  const [bundle, setBundle] = useState<any>(null);
  const [prediction, setPrediction] = useState<any>(null);
  const [loadingFixtures, setLoadingFixtures] = useState(false);
  const [loadingPred, setLoadingPred] = useState(false);
  const [homeRest, setHomeRest] = useState(7);
  const [awayRest, setAwayRest] = useState(7);
  const [errorMsg, setErrorMsg] = useState("");
  const [filterType, setFilterType] = useState("home");
  const [filterMin, setFilterMin] = useState(50);
  const [filterActive, setFilterActive] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [filterProgress, setFilterProgress] = useState("");
  const [filterPassed, setFilterPassed] = useState<any>(null);
  const [filterCount, setFilterCount] = useState(0);
  const [favorites, setFavorites] = useState<any>([]);
  const [pendingFavId, setPendingFavId] = useState<any>(null);
  const [fromCache, setFromCache] = useState(false);
  const [h2h, setH2h] = useState<any>(null);
  const [tableData, setTableData] = useState<any>(null);
  const [loadingH2h, setLoadingH2h] = useState(false);
  const [loadingTable, setLoadingTable] = useState(false);
  const [h2hError, setH2hError] = useState("");
  const [tableError, setTableError] = useState("");
  const predictionsCache = useRef<any>({});
  const h2hCache = useRef<any>({});
  const tableCache = useRef<any>({});

  useEffect(() => {
    try {
      const raw = localStorage.getItem("fav_matches_v1");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) setFavorites(parsed);
      }
    } catch {}
  }, []);

  const saveFavs = (list: any) => {
    setFavorites(list);
    try {
      localStorage.setItem("fav_matches_v1", JSON.stringify(list));
    } catch {}
  };

  const getCachedBundle = (fid: any) => {
    try {
      const raw = localStorage.getItem("bundle_" + fid);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (!obj || !obj.data) return null;
      if (Date.now() - obj.t > 3600000) return null;
      return obj.data;
    } catch {
      return null;
    }
  };

  const setCachedBundle = (fid: any, data: any) => {
    try {
      localStorage.setItem(
        "bundle_" + fid,
        JSON.stringify({ t: Date.now(), data: data })
      );
    } catch {}
  };

  const selectedFixture = useMemo(() => {
    if (!selectedFixtureId) return null;
    const found = safeArray(fixtures).find(
      (f: any) => safeStr(f?.id) === safeStr(selectedFixtureId)
    );
    return found || null;
  }, [fixtures, selectedFixtureId]);

  const loadFixtures = useCallback(async (dateStr: any) => {
    setLoadingFixtures(true);
    setErrorMsg("");
    try {
      const res = await fetch(
        API_BASE + "/api/fixtures?date=" + dateStr,
        { cache: "no-store" }
      );
      if (!res.ok) {
        setFixtures([]);
        setLeagues([]);
        setErrorMsg("No fixtures. Check backend.");
        return;
      }
      const data = await res.json().catch(() => []);
      const arr = safeArray(data);
      setFixtures(arr);
      const map: any = {};
      arr.forEach((f: any) => {
        const code = safeStr(f?.league_code || f?.competition, "OTHER");
        const name = safeStr(f?.league_name, code);
        if (!map[code]) map[code] = { code, name, count: 0 };
        map[code].count += 1;
      });
      setLeagues(Object.values(map));
    } catch {
      setFixtures([]);
      setLeagues([]);
      setErrorMsg("No fixtures. Check backend.");
    } finally {
      setLoadingFixtures(false);
    }
  }, []);

  useEffect(() => {
    setSelectedLeague("ALL");
    setSelectedFixtureId(null);
    setBundle(null);
    setPrediction(null);
    setH2h(null);
    setTableData(null);
    setH2hError("");
    setTableError("");
    setHomeRest(7);
    setAwayRest(7);
    setErrorMsg("");
    setFilterActive(false);
    setFilterPassed(null);
    setFilterCount(0);
    setFromCache(false);
    if (selectedDate) loadFixtures(selectedDate);
  }, [selectedDate, loadFixtures]);

  const loadH2h = useCallback(async (fixtureId: any) => {
    if (!fixtureId) return;
    if (h2hCache.current[fixtureId]) {
      setH2h(h2hCache.current[fixtureId]);
      return;
    }
    setLoadingH2h(true);
    setH2hError("");
    try {
      const res = await fetch(API_BASE + "/api/h2h?fixture_id=" + fixtureId, { cache: "no-store" });
      if (!res.ok) {
        setH2h(null);
        setH2hError("Backend H2H update is next. Paste this frontend, say Done, I will give backend file.");
        return;
      }
      const data = await res.json().catch(() => null);
      if (!data || data.error) {
        setH2h(null);
        setH2hError("No H2H data for this pair yet.");
        return;
      }
      h2hCache.current[fixtureId] = data;
      setH2h(data);
    } catch {
      setH2h(null);
      setH2hError("Backend H2H update is next. Paste this frontend, say Done, I will give backend file.");
    } finally {
      setLoadingH2h(false);
    }
  }, []);

  const loadTable = useCallback(async (fixtureObj: any) => {
    if (!fixtureObj) return;
    const leagueCode = safeStr(fixtureObj?.league_code || fixtureObj?.competition, "");
    const cacheKey = leagueCode || safeStr(fixtureObj?.league_name, "");
    if (tableCache.current[cacheKey]) {
      setTableData(tableCache.current[cacheKey]);
      return;
    }
    setLoadingTable(true);
    setTableError("");
    try {
      const res = await fetch(
        API_BASE + "/api/standings?league_code=" + encodeURIComponent(leagueCode) + "&league_name=" + encodeURIComponent(safeStr(fixtureObj?.league_name, "")),
        { cache: "no-store" }
      );
      if (!res.ok) {
        setTableData(null);
        setTableError("Backend Table update is next. Paste this frontend, say Done, I will give backend file.");
        return;
      }
      const data = await res.json().catch(() => null);
      if (!data || data.error) {
        setTableData(null);
        setTableError("No table data for this league yet.");
        return;
      }
      tableCache.current[cacheKey] = data;
      setTableData(data);
    } catch {
      setTableData(null);
      setTableError("Backend Table update is next. Paste this frontend, say Done, I will give backend file.");
    } finally {
      setLoadingTable(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedFixtureId || !selectedFixture) return;
    loadH2h(selectedFixtureId);
    loadTable(selectedFixture);
  }, [selectedFixtureId, selectedFixture, loadH2h, loadTable]);

  const loadBundle = useCallback(
    async (fixtureId: any) => {
      if (loadingPred || filtering) return;
      setLoadingPred(true);
      setFromCache(false);
      setBundle(null);
      setPrediction(null);
      try {
        if (predictionsCache.current[fixtureId]) {
          const cached = predictionsCache.current[fixtureId];
          setBundle(cached);
          setPrediction(cached.prediction || null);
          if (cached.h2h) setH2h(cached.h2h);
          if (cached.table || cached.standings) setTableData(cached.table || cached.standings);
          const r = cached.rest || {};
          setHomeRest(safeNum(r.home_rest, 7));
          setAwayRest(safeNum(r.away_rest, 7));
          setFromCache(true);
          return;
        }
        const saved = getCachedBundle(fixtureId);
        if (saved) {
          predictionsCache.current[fixtureId] = saved;
          setBundle(saved);
          setPrediction(saved.prediction || null);
          if (saved.h2h) setH2h(saved.h2h);
          if (saved.table || saved.standings) setTableData(saved.table || saved.standings);
          const r = saved.rest || {};
          setHomeRest(safeNum(r.home_rest, 7));
          setAwayRest(safeNum(r.away_rest, 7));
          setFromCache(true);
          return;
        }
        const res = await fetch(
          API_BASE + "/api/match-bundle?fixture_id=" + fixtureId,
          { cache: "no-store" }
        );
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        if (!data || data.error) return;
        predictionsCache.current[fixtureId] = data;
        setCachedBundle(fixtureId, data);
        setBundle(data);
        setPrediction(data.prediction || null);
        if (data.h2h) setH2h(data.h2h);
        if (data.table || data.standings) setTableData(data.table || data.standings);
        const r = data.rest || {};
        setHomeRest(safeNum(r.home_rest, 7));
        setAwayRest(safeNum(r.away_rest, 7));
        setFromCache(false);
      } catch {
      } finally {
        setLoadingPred(false);
      }
    },
    [loadingPred, filtering]
  );

  useEffect(() => {
    if (!pendingFavId) return;
    if (safeArray(fixtures).length === 0) return;
    const found = safeArray(fixtures).find(
      (f: any) => safeStr(f?.id) === safeStr(pendingFavId)
    );
    if (found) {
      const id = safeStr(found?.id);
      setSelectedFixtureId(id);
      setBundle(null);
      setPrediction(null);
      setH2h(null);
      setTableData(null);
      setPendingFavId(null);
      loadBundle(id);
    }
  }, [fixtures, pendingFavId, loadBundle]);

  const recalc = useCallback(async () => {
    if (!selectedFixtureId || loadingPred || filtering) return;
    setLoadingPred(true);
    try {
      const url =
        API_BASE +
        "/api/fixtures/" +
        selectedFixtureId +
        "/predict?home_rest_days=" +
        homeRest +
        "&away_rest_days=" +
        awayRest;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json().catch(() => null);
      if (data && !data.error) setPrediction(data);
    } catch {
    } finally {
      setLoadingPred(false);
    }
  }, [selectedFixtureId, homeRest, awayRest, loadingPred, filtering]);

  const filteredByLeague = useMemo(() => {
    const arr = safeArray(fixtures);
    if (selectedLeague === "ALL") return arr;
    return arr.filter(
      (f: any) => safeStr(f?.league_code || f?.competition) === selectedLeague
    );
  }, [fixtures, selectedLeague]);

  const filtered = useMemo(() => {
    if (!filterActive || !filterPassed) return filteredByLeague;
    const fp = filterPassed || [];
    return filteredByLeague.filter((f: any) => fp.includes(safeStr(f?.id)));
  }, [filteredByLeague, filterActive, filterPassed]);

  const played = useMemo(() => {
    return safeArray(fixtures).filter((f: any) => f?.status === "FINISHED").length;
  }, [fixtures]);

  const handleTap = (f: any) => {
    if (loadingPred || filtering) return;
    try {
      const id = safeStr(f?.id);
      if (!id) return;
      setSelectedFixtureId(id);
      setBundle(null);
      setPrediction(null);
      setH2h(null);
      setTableData(null);
      loadBundle(id);
    } catch {}
  };

  const isFav = useMemo(() => {
    if (!selectedFixtureId) return false;
    return safeArray(favorites).some(
      (fav: any) => safeStr(fav?.id) === safeStr(selectedFixtureId)
    );
  }, [favorites, selectedFixtureId]);

  const toggleFav = () => {
    if (!selectedFixture) return;
    const id = safeStr(selectedFixture?.id);
    if (isFav) {
      const next = safeArray(favorites).filter(
        (fav: any) => safeStr(fav?.id) !== id
      );
      saveFavs(next);
    } else {
      const favObj = {
        id: id,
        home: getTeamName(selectedFixture?.home_team),
        away: getTeamName(selectedFixture?.away_team),
        league: safeStr(selectedFixture?.league_name, ""),
        date: safeStr(selectedFixture?.date, selectedDate),
        home_score: safeStr(selectedFixture?.home_score, ""),
        away_score: safeStr(selectedFixture?.away_score, ""),
        status: safeStr(selectedFixture?.status, ""),
      };
      saveFavs([...safeArray(favorites), favObj]);
    }
  };

  const tapFav = (fav: any) => {
    if (loadingPred || filtering) return;
    const fid = safeStr(fav?.id);
    const fdate = safeStr(fav?.date, "").slice(0, 10);
    if (fdate && fdate !== selectedDate) {
      setPendingFavId(fid);
      setSelectedDate(fdate);
    } else {
      setSelectedFixtureId(fid);
      setBundle(null);
      setPrediction(null);
      setH2h(null);
      setTableData(null);
      loadBundle(fid);
    }
  };

  const removeFav = (fav: any) => {
    const id = safeStr(fav?.id);
    const next = safeArray(favorites).filter(
      (f: any) => safeStr(f?.id) !== id
    );
    saveFavs(next);
  };

  const passesFilter = (pred: any) => {
    if (!pred) return false;
    const getVal = (key: any) => safeNum(pred?.[key], 0) * 100;
    if (filterType === "home") return getVal("home_win_prob") >= filterMin;
    if (filterType === "away") return getVal("away_win_prob") >= filterMin;
    if (filterType === "draw") return getVal("draw_prob") >= filterMin;
    if (filterType === "over25") return getVal("over_25_prob") >= filterMin;
    if (filterType === "under25") return getVal("under_25_prob") >= filterMin;
    if (filterType === "any_win") {
      const m = Math.max(
        getVal("home_win_prob"),
        getVal("away_win_prob")
      );
      return m >= filterMin;
    }
    return false;
  };

  const runFilter = async () => {
    if (filtering || loadingPred) return;
    setFiltering(true);
    setFilterActive(false);
    setFilterPassed(null);
    setFilterCount(0);
    const list = filteredByLeague;
    const passed: any = [];
    for (let i = 0; i < list.length; i++) {
      const f = list[i];
      const fid = safeStr(f?.id);
      setFilterProgress(
        "Checking " +
          (i + 1) +
          " of " +
          list.length +
          " - " +
          getTeamName(f?.home_team) +
          " vs " +
          getTeamName(f?.away_team) +
          "... Please wait, do not tap."
      );
      try {
        let data = predictionsCache.current[fid];
        if (!data) data = getCachedBundle(fid);
        if (!data) {
          const res = await fetch(
            API_BASE + "/api/match-bundle?fixture_id=" + fid,
            { cache: "no-store" }
          );
          if (res.ok) {
            const j = await res.json().catch(() => null);
            if (j && !j.error) {
              data = j;
              predictionsCache.current[fid] = j;
              setCachedBundle(fid, j);
            }
          }
        }
        if (data && data.prediction && passesFilter(data.prediction)) {
          passed.push(fid);
        }
      } catch {}
    }
    setFilterPassed(passed);
    setFilterCount(passed.length);
    setFilterActive(true);
    setFiltering(false);
    setFilterProgress("");
  };

  const clearFilter = () => {
    setFilterActive(false);
    setFilterPassed(null);
    setFilterCount(0);
    setFilterProgress("");
  };

  const homeStats = bundle?.homeStats || bundle?.home_stats || null;
  const awayStats = bundle?.awayStats || bundle?.away_stats || null;
  const isDefault =
    bundle?.is_default === true ||
    (homeStats?.is_default && awayStats?.is_default);

  const filterLabel =
    filterType === "home"
      ? "Home Win"
      : filterType === "away"
      ? "Away Win"
      : filterType === "draw"
      ? "Draw"
      : filterType === "over25"
      ? "Over 2.5"
      : filterType === "under25"
      ? "Under 2.5"
      : "Home or Away Win";

  const worstScore = getWorstScore(prediction);
  const pickText = safeStr(
    prediction?.over_under_pick,
    safeNum(prediction?.over_25_prob, 0) >= 0.5 ? "Over 2.5" : "Under 2.5"
  );
  const confInfo = getConfidenceRating(prediction);
  const over25Pct = Math.round(safeNum(prediction?.over_25_prob, 0) * 100);
  const over25Label = over25Pct >= 60 ? "Strong Over 2.5" : over25Pct >= 50 ? "Lean Over 2.5" : "Lean Under 2.5";

  // V4.0 SMART BREAKDOWN
  const confBreakdown = safeArray(prediction?.confidence_breakdown);
  const confExpl = safeStr(prediction?.confidence_explanation, "");
  const rotationRisk = prediction?.rotation_risk === true;
  const rotationText = safeStr(prediction?.rotation_text, "");
  const homeNext = prediction?.home_next_match || bundle?.home_next_match || {};
  const awayNext = prediction?.away_next_match || bundle?.away_next_match || {};
  const hasNextInfo = homeNext?.has_next || awayNext?.has_next;

  const h2hMeetings = safeArray(h2h?.meetings || h2h?.games || h2h?.results);
  const h2hTotal = safeNum(h2h?.total || h2h?.total_meetings || h2hMeetings.length, h2hMeetings.length);
  const h2hHomeWins = safeNum(h2h?.home_wins || h2h?.homeWins || 0, 0);
  const h2hDraws = safeNum(h2h?.draws || 0, 0);
  const h2hAwayWins = safeNum(h2h?.away_wins || h2h?.awayWins || 0, 0);
  const h2hHomeGoals = safeNum(h2h?.home_goals || h2h?.homeGoals || 0, 0);
  const h2hAwayGoals = safeNum(h2h?.away_goals || h2h?.awayGoals || 0, 0);
  const h2hBtts = safeNum(h2h?.btts || h2h?.btts_count || 0, 0);
  const h2hOver25 = safeNum(h2h?.over25 || h2h?.over_25 || h2h?.over_25_count || 0, 0);
  const standingsList = safeArray(tableData?.standings || tableData?.table || tableData?.positions);
  const homeTeamName = selectedFixture ? getTeamName(selectedFixture?.home_team) : "";
  const awayTeamName = selectedFixture ? getTeamName(selectedFixture?.away_team) : "";
  const findTeamRow = (name: any) => {
    const n = safeStr(name, "").toLowerCase();
    return standingsList.find((r: any) => safeStr(r?.team || r?.team_name || r?.name, "").toLowerCase() === n || safeStr(r?.team || r?.team_name || r?.name, "").toLowerCase().includes(n.slice(0, 6)));
  };
  const homeRow = tableData?.home || tableData?.home_team || findTeamRow(homeTeamName) || null;
  const awayRow = tableData?.away || tableData?.away_team || findTeamRow(awayTeamName) || null;
  const homePos = safeNum(homeRow?.position || homeRow?.pos || homeRow?.rank, 0);
  const awayPos = safeNum(awayRow?.position || awayRow?.pos || awayRow?.rank, 0);
  const homePts = safeNum(homeRow?.points || homeRow?.pts, 0);
  const awayPts = safeNum(awayRow?.points || awayRow?.pts, 0);

  return (
    <div
      style={{
        background: "#0f172a",
        minHeight: "100vh",
        color: "white",
        padding: 16,
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          background: "#10b981",
          color: "white",
          borderRadius: 8,
          padding: "6px 10px",
          fontSize: 12,
          fontWeight: 700,
          display: "inline-block",
          marginBottom: 8,
        }}
      >
        V4.0 - Smart Confidence
      </div>

      <h1
        style={{
          fontSize: 34,
          fontWeight: 800,
          lineHeight: 1.1,
          marginBottom: 8,
        }}
      >
        Match Centre + Prediction
      </h1>

      <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 16 }}>
                1. Pick a date. 2. Pick a league. 3. Use Filter or tap a match. 4.
        Check Smart Confidence first — it now looks at Form, H2H, Table, Goals + Next Match / Resting.
      </p>

      <div
        style={{
          background: "#f59e0b",
          color: "#451a03",
          borderRadius: 16,
          padding: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ fontWeight: 800, fontSize: 16 }}>
          My Favorites ({safeArray(favorites).length})
        </div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          Tap a Favorite to open it instantly. If you opened it in the last
          1 hour it loads from saved cache, no long wait.
        </div>
        {safeArray(favorites).length === 0 && (
          <div style={{ fontSize: 13, marginTop: 8 }}>
            No favorites yet. Tap a match, then tap Add to Favorites below
            the match name.
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {safeArray(favorites).map((fav: any) => {
            return (
              <div
                key={safeStr(fav?.id)}
                style={{
                  display: "flex",
                  gap: 4,
                  background: "white",
                  borderRadius: 20,
                  padding: "4px 4px 4px 10px",
                  alignItems: "center",
                }}
              >
                <button
                  onClick={() => tapFav(fav)}
                  disabled={loadingPred || filtering}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#451a03",
                    cursor: "pointer",
                    textAlign: "left",
                    fontWeight: 700,
                    fontSize: 13,
                  }}
                >
                  {safeStr(fav?.home)} vs {safeStr(fav?.away)}
                  <div style={{ fontSize: 11, fontWeight: 400 }}>
                    {safeStr(fav?.date, "").slice(0, 10)}
                    {fav?.status === "FINISHED"
                      ? " - " +
                        safeStr(fav?.home_score) +
                        " - " +
                        safeStr(fav?.away_score) +
                        " FT"
                      : ""}
                  </div>
                </button>
                <button
                  onClick={() => removeFav(fav)}
                  style={{
                    background: "#451a03",
                    color: "white",
                    border: "none",
                    borderRadius: 20,
                    padding: "6px 10px",
                    cursor: "pointer",
                  }}
                >
                  X
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ fontWeight: 700, marginBottom: 8 }}>
        Date - 7 days ago to 7 days ahead
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          overflowX: "auto",
          paddingBottom: 8,
        }}
      >
        {safeArray(dates).map((d: any) => {
          const active = d === selectedDate;
          return (
            <button
              key={d}
              onClick={() => {
                if (!loadingPred && !filtering) setSelectedDate(d);
              }}
              disabled={loadingPred || filtering}
              style={{
                flexShrink: 0,
                background: active ? "#10b981" : "#1e293b",
                color: "white",
                border: "none",
                borderRadius: 12,
                padding: "10px 14px",
                cursor: "pointer",
              }}
            >
              <div>{d.slice(5)}</div>
            </button>
          );
        })}
      </div>

      <div style={{ fontWeight: 700, marginTop: 16, marginBottom: 8 }}>
        Leagues with matches on {selectedDate} ({safeArray(fixtures).length}{" "}
        matches, {played} played)
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => {
            setSelectedLeague("ALL");
            clearFilter();
          }}
          style={{
            background: selectedLeague === "ALL" ? "#10b981" : "#1e293b",
            color: "white",
            border: "none",
            borderRadius: 20,
            padding: "10px 16px",
            cursor: "pointer",
          }}
        >
          All leagues ({safeArray(fixtures).length})
        </button>
        {safeArray(leagues).map((l: any) => {
          const code = safeStr(l?.code);
          const name = safeStr(l?.name, code);
          return (
            <button
              key={code}
              onClick={() => {
                setSelectedLeague(code);
                clearFilter();
              }}
              style={{
                background: selectedLeague === code ? "#10b981" : "#1e293b",
                color: "white",
                border: "none",
                borderRadius: 20,
                padding: "10px 16px",
                cursor: "pointer",
              }}
            >
              {name} ({safeNum(l?.count, 0)})
            </button>
          );
        })}
      </div>

      <div
        style={{
          background: "#1e293b",
          borderRadius: 16,
          padding: 16,
          marginTop: 16,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 16 }}>
          Filter by Probability
        </div>
        <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 4 }}>
          Filter this date + league by Home Win, Draw, Away Win, Over 2.5 or
          Under 2.5. It checks one by one slowly so it does not hit the
          limit.
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            marginTop: 12,
          }}
        >
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              background: "#0f172a",
              color: "white",
              border: "none",
              borderRadius: 12,
              padding: "10px 12px",
            }}
          >
            <option value="home">Home Win %</option>
            <option value="away">Away Win %</option>
            <option value="draw">Draw %</option>
            <option value="over25">Over 2.5 %</option>
            <option value="under25">Under 2.5 %</option>
            <option value="any_win">Home or Away Win %</option>
          </select>
          <div style={{ flex: 1 }}>
            Min: {filterMin}%
            <br />
            <input
              type="range"
              min={30}
              max={75}
              value={filterMin}
              onChange={(e) => setFilterMin(safeNum(e.target.value, 50))}
              style={{ width: "100%" }}
            />
          </div>
        </div>
        <div
          style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}
        >
          <button
            onClick={runFilter}
            disabled={
              filtering || loadingPred || safeArray(filteredByLeague).length === 0
            }
            style={{
              background: filtering || loadingPred ? "#64748b" : "#10b981",
              color: "white",
              border: "none",
              borderRadius: 12,
              padding: "10px 16px",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Apply Filter - Check {safeArray(filteredByLeague).length} matches
          </button>
          {filterActive && (
            <button
              onClick={clearFilter}
              style={{
                background: "#334155",
                color: "white",
                border: "none",
                borderRadius: 12,
                padding: "10px 16px",
                cursor: "pointer",
              }}
            >
              Clear Filter
            </button>
          )}
        </div>
        {filtering && (
          <div style={{ color: "#fbbf24", marginTop: 10, fontWeight: 700 }}>
            {filterProgress}
          </div>
        )}
        {filterActive && !filtering && (
          <div
            style={{ color: "#dcfce7", marginTop: 10, fontWeight: 700 }}
          >
            Filter: {filterLabel} {">="} {filterMin}% - {filterCount} of{" "}
            {safeArray(filteredByLeague).length} matches pass.
          </div>
        )}
      </div>

      {safeArray(fixtures).length === 0 && !loadingFixtures && (
        <div style={{ color: "#94a3b8", marginTop: 12 }}>
          {errorMsg || "No matches on this date. Try another date."}
        </div>
      )}
      {loadingFixtures && (
        <div style={{ color: "#94a3b8", marginTop: 12 }}>
          Loading fixtures...
        </div>
      )}

      <div style={{ fontWeight: 700, marginTop: 20, marginBottom: 8 }}>
        Matches - {selectedDate}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {safeArray(filtered).map((f: any) => {
          const id = safeStr(f?.id);
          const active = id === selectedFixtureId;
          return (
            <button
              key={id}
              onClick={() => handleTap(f)}
              disabled={loadingPred || filtering}
              style={{
                background: active ? "#10b981" : "#1e293b",
                color: "white",
                border: "none",
                borderRadius: 20,
                padding: "12px 16px",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div>
                {getTeamName(f?.home_team)} vs {getTeamName(f?.away_team)}
              </div>
              <div
                style={{ fontSize: 12, color: "#cbd5e1", textAlign: "center" }}
              >
                {f?.status === "FINISHED"
                  ? safeStr(f?.home_score, "-") +
                    " - " +
                    safeStr(f?.away_score, "-") +
                    " FT"
                  : formatTime(f?.date)}
              </div>
            </button>
          );
        })}
      </div>

      {selectedFixture && (
        <div
          style={{
            marginTop: 24,
            background: "#1e293b",
            borderRadius: 16,
            padding: 16,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 18 }}>
            {getTeamName(selectedFixture?.home_team)} vs{" "}
            {getTeamName(selectedFixture?.away_team)}
          </div>
          <div style={{ color: "#94a3b8", fontSize: 13 }}>
            {safeStr(selectedFixture?.league_name)} -{" "}
            {formatTime(selectedFixture?.date)}
          </div>

          <button
            onClick={toggleFav}
            style={{
              marginTop: 12,
              background: isFav ? "#f59e0b" : "#0f172a",
              color: isFav ? "#451a03" : "white",
              border: "1px solid #f59e0b",
              borderRadius: 12,
              padding: "10px 16px",
              cursor: "pointer",
              fontWeight: 800,
              width: "100%",
            }}
          >
            {isFav
              ? "Saved - Tap to Remove from Favorites"
              : "Add to Favorites - Save for Instant Revisit"}
          </button>

          {loadingPred && (
            <div
              style={{
                background: "#fef3c7",
                color: "#92400e",
                borderRadius: 12,
                padding: 12,
                marginTop: 12,
                fontWeight: 700,
              }}
            >
              Fetching REAL analysis... Please wait 15 to 20 seconds. Now checks Form, H2H, Table + Next Match.
            </div>
          )}

          {!loadingPred && fromCache && bundle && (
            <div
              style={{
                background: "#dcfce7",
                color: "#166534",
                borderRadius: 12,
                padding: 10,
                marginTop: 12,
                fontSize: 13,
              }}
            >
              Loaded instantly from Favorites cache. No long wait.
            </div>
          )}

          {!loadingPred && isDefault && (
            <div
              style={{
                background: "#fef3c7",
                color: "#92400e",
                borderRadius: 12,
                padding: 10,
                marginTop: 12,
                fontSize: 13,
              }}
            >
              Showing default Rest 7,7 because limit was hit. Wait 1 minute,
              then tap this match again.
            </div>
          )}

          {!loadingPred && bundle && !isDefault && !fromCache && (
            <div
              style={{
                background: "#dcfce7",
                color: "#166534",
                borderRadius: 12,
                padding: 10,
                marginTop: 12,
                fontSize: 13,
              }}
            >
              Real analysis loaded. Form and goals are different for each
              team.
            </div>
          )}

          {!loadingPred && homeStats && (
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <div
                style={{
                  flex: 1,
                  background: "#0f172a",
                  borderRadius: 12,
                  padding: 10,
                }}
              >
                <b>{getTeamName(selectedFixture?.home_team)}</b>
                <br />
                Form: {safeArray(homeStats?.form).join(" ") || "N/A"}
                <br />
                Goals: {safeStr(homeStats?.goals_for_avg, "-")} scored,{" "}
                {safeStr(homeStats?.goals_against_avg, "-")} conceded
                <br />
                Last match: {safeStr(homeStats?.last_match_date, "N/A")}
              </div>
              <div
                style={{
                  flex: 1,
                  background: "#0f172a",
                  borderRadius: 12,
                  padding: 10,
                }}
              >
                <b>{getTeamName(selectedFixture?.away_team)}</b>
                <br />
                Form: {safeArray(awayStats?.form).join(" ") || "N/A"}
                <br />
                Goals: {safeStr(awayStats?.goals_for_avg, "-")} scored,{" "}
                {safeStr(awayStats?.goals_against_avg, "-")} conceded
                <br />
                Last match: {safeStr(awayStats?.last_match_date, "N/A")}
              </div>
            </div>
          )}

          <div style={{ fontWeight: 800, fontSize: 17, marginTop: 20 }}>
            Table Position - {safeStr(selectedFixture?.league_name)}
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 2 }}>
            Where both teams sit in the league right now.
          </div>
          {loadingTable && (
            <div style={{ color: "#fbbf24", marginTop: 8, fontWeight: 700 }}>
              Loading table position...
            </div>
          )}
          {!loadingTable && tableError && (
            <div style={{ background: "#fef3c7", color: "#92400e", borderRadius: 12, padding: 10, marginTop: 8, fontSize: 13 }}>
              {tableError}
            </div>
          )}
          {!loadingTable && !tableError && tableData && (
            <div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 12, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{homeTeamName}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>{homePos ? "#" + homePos : "-"}</div>
                  <div style={{ fontSize: 12, marginTop: 2 }}>{homePts} pts</div>
                  <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 4 }}>
                    P: {safeNum(homeRow?.played || homeRow?.games || homeRow?.p, 0)} | W: {safeNum(homeRow?.won || homeRow?.w, 0)} D: {safeNum(homeRow?.drawn || homeRow?.d, 0)} L: {safeNum(homeRow?.lost || homeRow?.l, 0)}
                  </div>
                  <div style={{ fontSize: 12, color: "#cbd5e1" }}>
                    GF: {safeNum(homeRow?.gf || homeRow?.goals_for || homeRow?.goalsFor, 0)} GA: {safeNum(homeRow?.ga || homeRow?.goals_against || homeRow?.goalsAgainst, 0)} GD: {safeNum(homeRow?.gd || homeRow?.goal_diff, 0)}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>Form: {safeStr(homeRow?.form, safeArray(homeStats?.form).join(" ") || "-")}</div>
                </div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 12, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{awayTeamName}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>{awayPos ? "#" + awayPos : "-"}</div>
                  <div style={{ fontSize: 12, marginTop: 2 }}>{awayPts} pts</div>
                  <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 4 }}>
                    P: {safeNum(awayRow?.played || awayRow?.games || awayRow?.p, 0)} | W: {safeNum(awayRow?.won || awayRow?.w, 0)} D: {safeNum(awayRow?.drawn || awayRow?.d, 0)} L: {safeNum(awayRow?.lost || awayRow?.l, 0)}
                  </div>
                  <div style={{ fontSize: 12, color: "#cbd5e1" }}>
                    GF: {safeNum(awayRow?.gf || awayRow?.goals_for || awayRow?.goalsFor, 0)} GA: {safeNum(awayRow?.ga || awayRow?.goals_against || awayRow?.goalsAgainst, 0)} GD: {safeNum(awayRow?.gd || awayRow?.goal_diff, 0)}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>Form: {safeStr(awayRow?.form, safeArray(awayStats?.form).join(" ") || "-")}</div>
                </div>
              </div>
              {homePos && awayPos && (
                <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 8, fontSize: 13, textAlign: "center" }}>
                  {homePos < awayPos ? homeTeamName + " is " + (awayPos - homePos) + " places above " + awayTeamName + " (" + homePts + " pts vs " + awayPts + " pts)." : awayPos < homePos ? awayTeamName + " is " + (homePos - awayPos) + " places above " + homeTeamName + " (" + awayPts + " pts vs " + homePts + " pts)." : "Both teams are level on position."}
                </div>
              )}
              {standingsList.length > 0 && (
                <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 8 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Mini Table - Top 6 + Both Teams</div>
                  {standingsList.slice(0, 6).map((r: any, idx: number) => {
                    const tName = safeStr(r?.team || r?.team_name || r?.name, "");
                    const isHome = tName.toLowerCase() === homeTeamName.toLowerCase();
                    const isAway = tName.toLowerCase() === awayTeamName.toLowerCase();
                    return (
                      <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 6px", background: isHome || isAway ? "#1e293b" : "transparent", borderRadius: 6 }}>
                        <span>{safeNum(r?.position || r?.pos || idx + 1, idx + 1)}. {tName} {isHome ? " (HOME)" : ""} {isAway ? " (AWAY)" : ""}</span>
                        <span>{safeNum(r?.points || r?.pts, 0)} pts | P {safeNum(r?.played || r?.games, 0)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div style={{ fontWeight: 800, fontSize: 17, marginTop: 20 }}>
            Head to Head Report - {homeTeamName} vs {awayTeamName}
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 2 }}>
            What happened when these 2 teams met before.
          </div>
          {loadingH2h && (
            <div style={{ color: "#fbbf24", marginTop: 8, fontWeight: 700 }}>Loading Head to Head...</div>
          )}
          {!loadingH2h && h2hError && (
            <div style={{ background: "#fef3c7", color: "#92400e", borderRadius: 12, padding: 10, marginTop: 8, fontSize: 13 }}>{h2hError}</div>
          )}
          {!loadingH2h && !h2hError && h2h && (
            <div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{homeTeamName} Wins</div>
                  <div style={{ fontSize: 22, fontWeight: 800 }}>{h2hHomeWins}</div>
                </div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>Draws</div>
                  <div style={{ fontSize: 22, fontWeight: 800 }}>{h2hDraws}</div>
                </div>
                <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, padding: 10, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{awayTeamName} Wins</div>
                  <div style={{ fontSize: 22, fontWeight: 800 }}>{h2hAwayWins}</div>
                </div>
              </div>
              <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 8, fontSize: 13, textAlign: "center" }}>
                Total: {h2hTotal} | Goals: {h2hHomeGoals} - {h2hAwayGoals} | BTTS: {h2hBtts} of {h2hTotal} | Over 2.5: {h2hOver25} of {h2hTotal}
              </div>
              <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 8, fontSize: 13, textAlign: "center", fontWeight: 700 }}>
                {h2hHomeWins > h2hAwayWins ? homeTeamName + " dominates H2H (" + h2hHomeWins + " vs " + h2hAwayWins + ")." : h2hAwayWins > h2hHomeWins ? awayTeamName + " dominates H2H (" + h2hAwayWins + " vs " + h2hHomeWins + ")." : "H2H is balanced. No team dominates."}
              </div>
              {h2hMeetings.length > 0 && (
                <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 8 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Last {Math.min(5, h2hMeetings.length)} Meetings - Newest First</div>
                  {h2hMeetings.slice(0, 5).map((m: any, idx: number) => {
                    const mHome = safeStr(m?.home || m?.home_team || m?.homeTeam, "");
                    const mAway = safeStr(m?.away || m?.away_team || m?.awayTeam, "");
                    const hs = safeStr(m?.home_score ?? m?.homeScore ?? m?.score_home, "-");
                    const as = safeStr(m?.away_score ?? m?.awayScore ?? m?.score_away, "-");
                    const mDate = formatDateShort(m?.date || m?.utcDate || m?.kickoff);
                    const winner = safeNum(hs, 0) > safeNum(as, 0) ? mHome : safeNum(as, 0) > safeNum(hs, 0) ? mAway : "Draw";
                    return (
                      <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "6px 0", borderBottom: idx < 4 ? "1px solid #1e293b" : "none" }}>
                        <span>{mDate} - {mHome} vs {mAway}</span>
                        <span style={{ fontWeight: 700 }}>{hs} - {as} {winner !== "Draw" ? "(" + winner + ")" : "(Draw)"}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div style={{ fontWeight: 700, marginTop: 20 }}>
            What-If - Rest Only
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12 }}>
            Rest is AUTO from real last match. Missing Player removed - no
            free API has real 2026 injuries.
          </div>

          <div
            style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}
          >
            <div>
              Home Rest: {homeRest} days
              <br />
              <input
                type="range"
                min={1}
                max={14}
                value={homeRest}
                onChange={(e) => setHomeRest(safeNum(e.target.value, 7))}
              />
            </div>
            <div>
              Away Rest: {awayRest} days
              <br />
              <input
                type="range"
                min={1}
                max={14}
                value={awayRest}
                onChange={(e) => setAwayRest(safeNum(e.target.value, 7))}
              />
            </div>
          </div>

          <button
            onClick={recalc}
            disabled={loadingPred || filtering}
            style={{
              marginTop: 12,
              background: loadingPred || filtering ? "#64748b" : "#10b981",
              color: "white",
              border: "none",
              borderRadius: 12,
              padding: "10px 16px",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Recalculate Prediction
          </button>

          <div style={{ fontWeight: 700, marginTop: 16 }}>Prediction</div>
          {loadingPred && (
            <div style={{ color: "#94a3b8" }}>Loading prediction...</div>
          )}
          {!loadingPred && !prediction && (
            <div style={{ color: "#94a3b8" }}>
              No prediction yet. Tap Recalculate.
            </div>
          )}

          {!loadingPred && prediction && (
            <div>
              <div
                style={{ fontSize: 20, fontWeight: 800, marginTop: 8 }}
              >
                Most Likely Score: {safeStr(prediction?.predicted_score, "-")}
              </div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 800,
                  marginTop: 6,
                  color: "#fbbf24",
                }}
              >
                Worst Scenario / Cover: {worstScore}
              </div>
              <div style={{ color: "#94a3b8", fontSize: 13, marginTop: 4 }}>
                Play Main, cover Worst for safety.
              </div>

              {/* V4.0 SMART CONFIDENCE */}
              <div style={{ background: confInfo.bg, color: confInfo.color, borderRadius: 16, padding: 14, marginTop: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontWeight: 800, fontSize: 14 }}>Smart Confidence Rating</div>
                  <div style={{ fontWeight: 800, fontSize: 22 }}>{confInfo.pct}%</div>
                </div>
                <div style={{ fontSize: 12, marginTop: 2 }}>
                  {confInfo.isSmart ? "Base " + confInfo.basePct + "% → Smart " + confInfo.pct + "% after Form, H2H, Table, Goals + Next Match" : "Base = Highest probability"}
                </div>
                <div style={{ fontWeight: 800, fontSize: 18, marginTop: 4 }}>{confInfo.label}</div>
                <div style={{ background: "rgba(0,0,0,0.25)", height: 10, borderRadius: 10, marginTop: 8, overflow: "hidden" }}>
                  <div style={{ width: confInfo.pct + "%", height: "100%", background: confInfo.color === "white" ? "white" : confInfo.color, borderRadius: 10 }} />
                </div>
                <div style={{ fontSize: 13, marginTop: 8, fontWeight: 600 }}>{confInfo.advice}</div>
                <div style={{ fontSize: 12, marginTop: 6 }}>
                  Based on highest probability: Home {(safeNum(prediction?.home_win_prob, 0) * 100).toFixed(1)}% / Draw {(safeNum(prediction?.draw_prob, 0) * 100).toFixed(1)}% / Away {(safeNum(prediction?.away_win_prob, 0) * 100).toFixed(1)}%
                </div>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  70%+ Super Lock | 60-69% High | 50-59% Medium | Below 50% Skip - Trap
                </div>
              </div>

              {/* BREAKDOWN */}
              {confBreakdown.length > 0 && (
                <div style={{ background: "#0f172a", borderRadius: 16, padding: 12, marginTop: 12 }}>
                  <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 8 }}>Why this Confidence? - Breakdown</div>
                  {confBreakdown.map((b: any, idx: number) => {
                    const pts = safeNum(b?.points, 0);
                    const col = pts > 0 ? "#10b981" : pts < 0 ? "#ef4444" : "#94a3b8";
                    const sign = pts > 0 ? "+" + pts + "%" : pts < 0 ? pts + "%" : "0%";
                    return (
                      <div key={idx} style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "8px 0", borderBottom: idx < confBreakdown.length - 1 ? "1px solid #1e293b" : "none" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 700, fontSize: 13 }}>{safeStr(b?.factor, "")}</div>
                          <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 2 }}>{safeStr(b?.detail, "")}</div>
                        </div>
                        <div style={{ fontWeight: 800, fontSize: 13, color: col, minWidth: 50, textAlign: "right" }}>{sign}</div>
                      </div>
                    );
                  })}
                  {confExpl && (
                    <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 10, lineHeight: 1.5 }}>{confExpl}</div>
                  )}
                </div>
              )}

              {/* NEXT MATCH / ROTATION */}
              <div style={{ background: rotationRisk ? "#7f1d1d" : "#0f172a", borderRadius: 16, padding: 12, marginTop: 12 }}>
                <div style={{ fontWeight: 800, fontSize: 14 }}>Next Match / Rotation Risk - Important of Next Match</div>
                <div style={{ fontSize: 12, color: rotationRisk ? "#fecaca" : "#94a3b8", marginTop: 4 }}>
                  If a team has a big match in 2-3 days, they may rest starters. Confidence is reduced when this happens.
                </div>
                {rotationRisk && (
                  <div style={{ background: "#ef4444", color: "white", borderRadius: 10, padding: 10, marginTop: 10, fontSize: 13, fontWeight: 700 }}>
                    ⚠️ ROTATION RISK: {rotationText || "One team may rest players for next big match - confidence reduced."}
                  </div>
                )}
                {!rotationRisk && (
                  <div style={{ background: "#065f46", color: "#dcfce7", borderRadius: 10, padding: 10, marginTop: 10, fontSize: 13 }}>
                    ✅ No rotation risk. No big match in next 2-3 days for the predicted winner.
                  </div>
                )}
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  <div style={{ flex: 1, background: "#1e293b", borderRadius: 12, padding: 10 }}>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{homeTeamName} Next</div>
                    {homeNext?.has_next ? (
                      <div style={{ fontSize: 12, marginTop: 4 }}>
                        <b>vs {safeStr(homeNext?.opponent, "-")}</b><br />
                        {safeStr(homeNext?.competition, "")} - {formatDateShort(homeNext?.next_date)}<br />
                        In {safeNum(homeNext?.days_until, 0)} days - {safeStr(homeNext?.importance_label, "")}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, marginTop: 4 }}>No match in next 14 days</div>
                    )}
                  </div>
                  <div style={{ flex: 1, background: "#1e293b", borderRadius: 12, padding: 10 }}>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{awayTeamName} Next</div>
                    {awayNext?.has_next ? (
                      <div style={{ fontSize: 12, marginTop: 4 }}>
                        <b>vs {safeStr(awayNext?.opponent, "-")}</b><br />
                        {safeStr(awayNext?.competition, "")} - {formatDateShort(awayNext?.next_date)}<br />
                        In {safeNum(awayNext?.days_until, 0)} days - {safeStr(awayNext?.importance_label, "")}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, marginTop: 4 }}>No match in next 14 days</div>
                    )}
                  </div>
                </div>
                {!hasNextInfo && (
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>Next match data not available for this fixture yet. Confidence used Form, H2H, Table + Goals only.</div>
                )}
              </div>
              {/* END V4.0 */}

              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Home Win
                  <br />
                  <b>
                    {(safeNum(prediction?.home_win_prob, 0) * 100).toFixed(1)}%
                  </b>
                </div>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Draw
                  <br />
                  <b>
                    {(safeNum(prediction?.draw_prob, 0) * 100).toFixed(1)}%
                  </b>
                </div>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Away Win
                  <br />
                  <b>
                    {(safeNum(prediction?.away_win_prob, 0) * 100).toFixed(1)}%
                  </b>
                </div>
              </div>

              <div style={{ fontWeight: 700, marginTop: 16 }}>
                Over / Under Analysis - Poisson from real goals
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 8,
                  marginTop: 8,
                  flexWrap: "wrap",
                }}
              >
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Over 1.5
                  <br />
                  <b>
                    {(safeNum(prediction?.over_15_prob, 0) * 100).toFixed(1)}%
                  </b>
                  <br />
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    Under 1.5{" "}
                    {(safeNum(prediction?.under_15_prob, 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Over 2.5
                  <br />
                  <b>
                    {(safeNum(prediction?.over_25_prob, 0) * 100).toFixed(1)}%
                  </b>
                  <br />
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    Under 2.5{" "}
                    {(safeNum(prediction?.under_25_prob, 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  Over 3.5
                  <br />
                  <b>
                    {(safeNum(prediction?.over_35_prob, 0) * 100).toFixed(1)}%
                  </b>
                  <br />
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    Under 3.5{" "}
                    {(safeNum(prediction?.under_35_prob, 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    borderRadius: 12,
                    padding: 10,
                    textAlign: "center",
                  }}
                >
                  BTTS
                  <br />
                  <b>
                    {(safeNum(prediction?.btts_prob, 0) * 100).toFixed(1)}%
                  </b>
                </div>
              </div>

              <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, marginTop: 10, fontSize: 13, textAlign: "center" }}>
                Over 2.5 Confidence: <b>{over25Pct}% - {over25Label}</b>
              </div>

              <div style={{ fontWeight: 700, marginTop: 12 }}>
                Pick: {pickText}
              </div>

              <div style={{ color: "#cbd5e1", fontSize: 13, marginTop: 8 }}>
                {safeStr(prediction?.explanation, "")}
              </div>
              <div style={{ color: "#cbd5e1", fontSize: 13, marginTop: 6 }}>
                Most Likely {safeStr(prediction?.predicted_score, "-")}, Worst
                Scenario / Cover {worstScore}.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
