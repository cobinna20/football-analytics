"use client";

export type SimContext = { home_rest_days: number; away_rest_days: number; home_missing_key: number; away_missing_key: number };

export default function WhatIfSimulator({ context, onChange, homeName, awayName }: { context: SimContext; onChange: (c: SimContext) => void; homeName: string; awayName: string }) {
  const Row = ({ label, value, onMinus, onPlus, max = 7 }: { label: string; value: number; onMinus: () => void; onPlus: () => void; max?: number }) => (
    <div className="flex justify-between items-center bg-slate-800/50 rounded-xl p-3">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <button className="w-8 h-8 rounded-full bg-slate-700" onClick={onMinus}>-</button>
        <span className="font-bold w-6 text-center">{value}</span>
        <button className="w-8 h-8 rounded-full bg-slate-700" onClick={onPlus}>+</button>
      </div>
    </div>
  );
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h3 className="font-bold">What-If Simulator</h3>
      <p className="text-sm text-slate-400 mb-3">Change something and watch the prediction update in real time.</p>
      <div className="grid md:grid-cols-2 gap-3">
        <Row label={`${homeName} - Rest days`} value={context.home_rest_days} onMinus={() => onChange({ ...context, home_rest_days: Math.max(1, context.home_rest_days - 1) })} onPlus={() => onChange({ ...context, home_rest_days: Math.min(7, context.home_rest_days + 1) })} />
        <Row label={`${awayName} - Rest days`} value={context.away_rest_days} onMinus={() => onChange({ ...context, away_rest_days: Math.max(1, context.away_rest_days - 1) })} onPlus={() => onChange({ ...context, away_rest_days: Math.min(7, context.away_rest_days + 1) })} />
        <Row label={`${homeName} - Missing key players`} value={context.home_missing_key} onMinus={() => onChange({ ...context, home_missing_key: Math.max(0, context.home_missing_key - 1) })} onPlus={() => onChange({ ...context, home_missing_key: Math.min(3, context.home_missing_key + 1) })} max={3} />
        <Row label={`${awayName} - Missing key players`} value={context.away_missing_key} onMinus={() => onChange({ ...context, away_missing_key: Math.max(0, context.away_missing_key - 1) })} onPlus={() => onChange({ ...context, away_missing_key: Math.min(3, context.away_missing_key + 1) })} max={3} />
      </div>
      <button className="mt-4 w-full bg-slate-700 rounded-xl py-2 text-sm" onClick={() => onChange({ home_rest_days: 7, away_rest_days: 7, home_missing_key: 0, away_missing_key: 0 })}>Reset to normal</button>
    </div>
  );
        }
