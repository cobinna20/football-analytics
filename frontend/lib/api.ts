const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export type Team = { id: string; name: string; short_name: string; crest?: string; league: string };
export type Fixture = { id: string; competition: string; matchday: number; home_team: Team; away_team: Team; kickoff: string; status: string; venue?: string };
export async function getFixtures(): Promise<Fixture[]> {
  const r = await fetch(`${API}/api/fixtures`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
}
export async function getTeams(): Promise<Team[]> {
  const r = await fetch(`${API}/api/teams`, { cache: "no-store" });
  if (!r.ok) return [];
  return r.json();
                       }
