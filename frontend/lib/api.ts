const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export type Team = { id: string; name: string; short_name: string };
export type Fixture = {
  id: string;
  home_team: Team;
  away_team: Team;
  date: string;
  status: string;
  home_score: number | null;
  away_score: number | null;
  competition: string;
  league_code: string;
  league_name: string;
};
export type League = { code: string; name: string };

function dateRange(): { from: string; to: string } {
  const today = new Date();
  const from = new Date(today); from.setDate(today.getDate() - 7);
  const to = new Date(today); to.setDate(today.getDate() + 7);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { from: fmt(from), to: fmt(to) };
}

export async function getFixtures(competition = "ALL"): Promise<Fixture[]> {
  const { from, to } = dateRange();
  const r = await fetch(`${API}/api/fixtures?competition=${competition}&date_from=${from}&date_to=${to}`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}
export async function getLeagues(): Promise<League[]> {
  const r = await fetch(`${API}/api/leagues`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}
