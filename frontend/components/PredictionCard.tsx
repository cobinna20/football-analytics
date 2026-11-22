"use client";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from "recharts";
import type { Prediction, TeamStats } from "@/lib/predict";

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm"><span>{label}</span><span>{(value * 100).toFixed(1)}%</span></div>
      <div className="h-3 bg-slate-800 rounded-full overflow-hidden mt-1"><div className="h-full rounded-full" style={{ width: `${value * 100}%`, background: color }} /></div>
    </div>
  );
}

export default function PredictionCard({ prediction, homeStats, awayStats }: { prediction: Prediction; homeStats: TeamStats | null; awayStats: TeamStats | null }) {
  const radarData = homeStats && awayStats ? [
    { metric: "npxG", home: homeStats.npxg, away: awayStats.npxg },
    { metric: "PPDA (inv)", home: 20 - homeStats.ppda, away: 20 - awayStats.ppda },
    { metric: "Field Tilt", home: homeStats.field_tilt, away: awayStats.field_tilt },
    { metric: "SetPiece xG", home: homeStats.set_piece_xg * 10, away: awayStats.set_piece_xg * 10 },
    { metric: "Compact", home: homeStats.defensive_compactness, away: awayStats.defensive_compactness },
  ] : [];
  const getProb = (h: number, a: number) => {
    const s = prediction.scorelines.find((x) => x.home_goals === h && x.away_goals === a);
    return s ? s.probability : 0;
  };
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex justify-between items-center"><h2 className="text-xl font-bold">{prediction.home_team} vs {prediction.away_team}</h2><span className="text-emerald-400 font-bold">Most likely: {prediction.most_likely_score}</span></div>
        <p className="text-slate-400 text-sm mt-1">Expected goals: {prediction.expected_home_goals.toFixed(2)} - {prediction.expected_away_goals.toFixed(2)}</p>
        <div className="space-y-3 mt-4">
          <Bar label={prediction.home_team + " Win"} value={prediction.home_win} color="#10b981" />
          <Bar label="Draw" value={prediction.draw} color="#94a3b8" />
          <Bar label={prediction.away_team + " Win"} value={prediction.away_win} color="#3b82f6" />
        </div>
        <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
          <div className="bg-slate-800/50 rounded-xl p-3"><p className="text-slate-400">Over 2.5</p><p className="font-bold">{(prediction.over_25 * 100).toFixed(1)}%</p></div>
          <div className="bg-slate-800/50 rounded-xl p-3"><p className="text-slate-400">Under 2.5</p><p className="font-bold">{(prediction.under_25 * 100).toFixed(1)}%</p></div>
          <div className="bg-slate-800/50 rounded-xl p-3"><p className="text-slate-400">BTTS Yes</p><p className="font-bold">{(prediction.btts_yes * 100).toFixed(1)}%</p></div>
          <div className="bg-slate-800/50 rounded-xl p-3"><p className="text-slate-400">BTTS No</p><p className="font-bold">{(prediction.btts_no * 100).toFixed(1)}%</p></div>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-4 text-xs text-slate-400">
          <span>Model Edge Home: {(prediction.model_edge_home * 100).toFixed(1)}%</span>
          <span>Edge Draw: {(prediction.model_edge_draw * 100).toFixed(1)}%</span>
          <span>Edge Away: {(prediction.model_edge_away * 100).toFixed(1)}%</span>
        </div>
      </div>

      {radarData.length > 0 && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <h3 className="font-bold mb-2">Team Radar: {prediction.home_team} vs {prediction.away_team}</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
                <PolarRadiusAxis tick={false} />
                <Radar name={prediction.home_team} dataKey="home" stroke="#10b981" fill="#10b981" fillOpacity={0.4} />
                <Radar name={prediction.away_team} dataKey="away" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.4} />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <h3 className="font-bold mb-3">Exact Scoreline Matrix 0-0 to 4-4</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-center text-sm">
            <thead><tr><th className="p-2 text-left">Home \ Away</th>{[0, 1, 2, 3, 4].map((a) => <th key={a} className="p-2">{a}</th>)}</tr></thead>
            <tbody>
              {[0, 1, 2, 3, 4].map((h) => (
                <tr key={h}>
                  <td className="p-2 font-bold text-left">{h}</td>
                  {[0, 1, 2, 3, 4].map((a) => {
                    const p = getProb(h, a);
                    const isTop = prediction.most_likely_score === `${h}-${a}`;
                    return <td key={a} className={`p-2 rounded ${isTop ? "bg-emerald-500 text-white font-bold" : "bg-slate-800/50"}`}>{(p * 100).toFixed(1)}%</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-400 mt-2">Green cell = most likely score.</p>
      </div>
    </div>
  );
                                        }
