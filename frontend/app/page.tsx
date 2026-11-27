"use client";
import { useState, useEffect, useMemo, useCallback, useRef } from "react";

const API_BASE = "https://football-analytics-8khk.onrender.com";

function safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function safeStr(v, f) {
  if (v === null || v === undefined) return f || "";
  try {
    return String(v);
  } catch {
    return f || "";
  }
}

function safeNum(v, f) {
  const n = Number(v);
  return isNaN(n) ? (f || 0) : n;
}

function getTeamName(t) {
  if (!t) return "TBD";
  return t.short_name || t.name || t.shortName || "TBD";
}

function formatTime(s) {
  try {
    if (!s) return "";
    const d = new Date(s);
    if (isNaN(d.getTime())) return "";
    return d.toISOString().slice(11, 16) + " UTC";
  } catch {
    return "";
  }
}

function makeDates() {
  const out = [];
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

export default function Home() {
  const dates = useMemo(() => makeDates(), []);
  const [selectedDate, setSelectedDate] = useState(() => {
    try {
      return new Date().toISOString().slice(0, 10);
    } catch {
      return "2026-11-28";
    }
  });
  const [fixtures, setFixtures] = useState([]);
  const [leagues, setLeagues] = useState([]);
  const [selectedLeague, setSelectedLeague] = useState("ALL");
  const [selectedFixtureId, setSelectedFixtureId] = useState(null);
  const [bundle, setBundle] = useState(null);
  const [prediction, setPrediction] = useState(null);
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
  const [filterPassed, setFilterPassed] = useState(null);
  const [filterCount, setFilterCount] = useState(0);
  const predictionsCache = useRef({});

  const selectedFixture = useMemo(() => {
    if (!selectedFixtureId) return null;
    const found = safeArray(fixtures).find(
      (f) => safeStr(f?.id) === safeStr(selectedFixtureId)
    );
    return found || null;
  }, [fixtures, selectedFixtureId]);

  const loadFixtures = useCallback(async (dateStr) => {
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
      const map = {};
      arr.forEach((f) => {
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
    setHomeRest(7);
    setAwayRest(7);
    setErrorMsg("");
    setFilterActive(false);
    setFilterPassed(null);
    setFilterCount(0);
    if (selectedDate) loadFixtures(selectedDate);
  }, [selectedDate, loadFixtures]);

  const loadBundle = useCallback(
    async (fixtureId) => {
      if (loadingPred || filtering) return;
      setLoadingPred(true);
      setBundle(null);
      setPrediction(null);
      try {
        if (predictionsCache.current[fixtureId]) {
          const cached = predictionsCache.current[fixtureId];
          setBundle(cached);
          setPrediction(cached.prediction || null);
          const r = cached.rest || {};
          setHomeRest(safeNum(r.home_rest, 7));
          setAwayRest(safeNum(r.away_rest, 7));
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
        setBundle(data);
        setPrediction(data.prediction || null);
        const r = data.rest || {};
        setHomeRest(safeNum(r.home_rest, 7));
        setAwayRest(safeNum(r.away_rest, 7));
      } catch {
      } finally {
        setLoadingPred(false);
      }
    },
    [loadingPred, filtering]
  );

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
      (f) => safeStr(f?.league_code || f?.competition) === selectedLeague
    );
  }, [fixtures, selectedLeague]);

  const filtered = useMemo(() => {
    if (!filterActive || !filterPassed) return filteredByLeague;
    const fp = filterPassed || [];
    return filteredByLeague.filter((f) => fp.includes(safeStr(f?.id)));
  }, [filteredByLeague, filterActive, filterPassed]);

  const played = useMemo(() => {
    return safeArray(fixtures).filter((f) => f?.status === "FINISHED").length;
  }, [fixtures]);

  const handleTap = (f) => {
    if (loadingPred || filtering) return;
    try {
      const id = safeStr(f?.id);
      if (!id) return;
      setSelectedFixtureId(id);
      setBundle(null);
      setPrediction(null);
      loadBundle(id);
    } catch {}
  };

  const passesFilter = (pred) => {
    if (!pred) return false;
    const getVal = (key) => safeNum(pred?.[key], 0) * 100;
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
    const passed = [];
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
        V3.3 - Filter + Over/Under - Fixed Build
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
        1. Pick a date. 2. Pick a league. 3. Use Filter or tap a match.
      </p>

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
        {safeArray(dates).map((d) => {
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
        Leagues on {selectedDate} ({safeArray(fixtures).length} matches)
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
        {safeArray(leagues).map((l) => {
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
          Under 2.5. Checks one by one slowly so it does not hit the limit.
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
        {safeArray(filtered).map((f) => {
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
              Fetching REAL analysis... Please wait 10 to 15 seconds.
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

          {!loadingPred && bundle && !isDefault && (
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
              Real analysis loaded.
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
                Form: {safeArray(homeStats?.form).
