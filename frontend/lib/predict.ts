const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export type Scoreline = { home_goals: number; away_goals: number; probability: number };
export type Prediction = {
  fixture_id: string;
  home_team: string;
  away_team: string;
  home_win: number;
  draw: number;
  away_win: number;
  over_25: number;
  under_25: number;
  btts_yes: number;
  btts_no: number;
  expected_home_goals: number;
  expected_away_goals: number;
  most_likely_score: string;
  scorelines: Scoreline[];
  model_edge_home: number;
  model_edge_draw: number;
  model_edge_away: number;
};
export type TeamStats = {
  team_id: string;
  team_name: string;
  npxg: number;
  npxga: number;
  ppda: number;
  field_tilt: number;
  set_piece_xg: number;
  defensive_compactness: number;
};
export async function getPrediction(fixtureId: string, params: { home_rest_days: number; away_rest_days: number; home_missing_key: number; away_missing_key: number }): Promise<Prediction | null> {
  const q = new URLSearchParams({
    home_rest_days: String(params.home_rest_days),
    away_rest_days: String(params.away_rest_days),
    home_missing_key: String(params.home_missing_key),
    away_missing_key: String(params.away_missing_key),
  });
  const r = await fetch(`${API}/api/fixtures/${fixtureId}/predict?${q.toString()}`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}
export async function getTeamStats(teamId: string): Promise<TeamStats | null> {
  const r = await fetch(`${API}/api/teams/${teamId}/stats`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
  }
