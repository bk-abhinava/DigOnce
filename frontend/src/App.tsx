import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LayoutDashboard, Map, Bot, CheckSquare, AlertTriangle,
  FileText, Megaphone, RefreshCw, Activity, Clock,
  ChevronRight, Loader2, CheckCircle2, XCircle, AlertCircle,
  Zap, Droplets, Wifi, Construction, Shield, Volume2
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts';
import {
  getWorkOrders, getCorridors, getConflicts, generatePlan,
  getPlans, approvePlan, rejectPlan,
  getEmergencies, reportEmergency, getAuditLog, getPolicies,
  proposePolicy, approvePolicy, getAdvisory, resetDemo
} from './api';
import type {
  WorkOrder, Corridor, Conflict, Plan, Emergency,
  PolicyRule, Advisory, AuditEntry
} from './types';

// ── Helpers ───────────────────────────────────────────────────────────────────

const DEPT_COLORS: Record<string, string> = {
  water: '#3b82f6', power: '#f59e0b', fibre: '#8b5cf6', road: '#10b981'
};
const DEPT_ICONS: Record<string, React.ReactNode> = {
  water: <Droplets size={14} />, power: <Zap size={14} />,
  fibre: <Wifi size={14} />, road: <Construction size={14} />,
};
const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700', high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700', low: 'bg-slate-100 text-slate-600',
};
const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-600', approved: 'bg-green-100 text-green-700',
  in_progress: 'bg-blue-100 text-blue-700', completed: 'bg-teal-100 text-teal-700',
  cancelled: 'bg-red-100 text-red-600', emergency: 'bg-red-100 text-red-700',
};
const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
const fmtCost = (n: number) => n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : `₹${n.toLocaleString('en-IN')}`;

function Spinner() { return <Loader2 size={18} className="animate-spin" />; }
function ErrorMsg({ msg }: { msg: string }) {
  return <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3"><AlertCircle size={16} />{msg}</div>;
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const NAV = [
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} /> },
  { id: 'corridor', label: 'Corridor Planning', icon: <Map size={18} /> },
  { id: 'negotiation', label: 'Negotiation', icon: <Bot size={18} /> },
  { id: 'approval', label: 'Approval', icon: <CheckSquare size={18} /> },
  { id: 'emergency', label: 'Emergency', icon: <AlertTriangle size={18} /> },
  { id: 'policy', label: 'Policy & Audit', icon: <FileText size={18} /> },
  { id: 'advisory', label: 'Citizen Advisory', icon: <Megaphone size={18} /> },
];

function Sidebar({ active, setActive, onReset }: { active: string; setActive: (s: string) => void; onReset: () => void }) {
  return (
    <aside className="w-64 min-h-screen flex flex-col" style={{ background: 'var(--navy)' }}>
      <div className="p-5 border-b border-white/10">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center">
            <Construction size={18} className="text-white" />
          </div>
          <span className="text-white font-bold text-lg tracking-tight">Dig Once</span>
        </div>
        <p className="text-white/50 text-xs">Bengaluru Roadworks AI</p>
        <div className="mt-2 px-2 py-1 bg-amber-500/20 rounded text-amber-300 text-xs font-medium">⚠ DEMO / PROTOTYPE</div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(n => (
          <button key={n.id} onClick={() => setActive(n.id)}
            className={`sidebar-link w-full text-left ${active === n.id ? 'active' : 'text-white/70'}`}>
            {n.icon}{n.label}
          </button>
        ))}
      </nav>
      <div className="p-3 border-t border-white/10">
        <button onClick={onReset}
          className="sidebar-link w-full text-white/60 hover:text-white">
          <RefreshCw size={16} />Reset Demo
        </button>
        <p className="text-white/30 text-xs mt-2 px-4">IBM Bobathon 2026</p>
      </div>
    </aside>
  );
}

// ── Overview ──────────────────────────────────────────────────────────────────

function OverviewScreen({ setActive }: { setActive: (s: string) => void }) {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [emergencies, setEmergencies] = useState<Emergency[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getWorkOrders(), getConflicts(), getPlans(), getEmergencies()])
      .then(([wo, c, p, e]) => { setWorkOrders(wo); setConflicts(c.conflicts); setPlans(p); setEmergencies(e); })
      .finally(() => setLoading(false));
  }, []);

  const pendingApprovals = plans.filter(p => p.status === 'validated');

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Operations Overview</h1>
        <p className="text-slate-500 text-sm mt-1">Whitefield–Mahadevapura Corridor · <span className="text-amber-600 font-medium">Simulated Demo Data</span></p>
      </div>

      {loading ? <div className="flex justify-center py-12"><Spinner /></div> : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Active Work Orders', value: workOrders.filter(w => w.status !== 'cancelled').length, color: 'text-blue-600', action: () => setActive('corridor') },
              { label: 'Detected Conflicts', value: conflicts.length, color: 'text-red-600', action: () => setActive('corridor') },
              { label: 'Pending Approvals', value: pendingApprovals.length, color: 'text-amber-600', action: () => setActive('approval') },
              { label: 'Emergency Events', value: emergencies.length, color: 'text-red-700', action: () => setActive('emergency') },
            ].map(s => (
              <button key={s.label} onClick={s.action} className="card text-left hover:border-cyan-300 transition-colors">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">{s.label}</p>
                <p className={`text-3xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              </button>
            ))}
          </div>

          {conflicts.length > 0 && (
            <div className="card border-red-200 bg-red-50">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle size={18} className="text-red-600" />
                <h2 className="font-semibold text-red-800">Detected Conflicts</h2>
                <span className="badge bg-red-100 text-red-700">{conflicts.length}</span>
              </div>
              <div className="space-y-2">
                {conflicts.slice(0, 4).map(c => (
                  <div key={c.id} className="text-sm text-red-700 bg-red-100 rounded-lg p-3">
                    <span className="font-medium capitalize">{c.conflict_type.replace('_', ' ')}</span>
                    <span className="text-red-600 ml-2">({c.work_order_ids.join(', ')})</span>
                    <p className="mt-1 text-xs text-red-600">{c.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card">
            <h2 className="font-semibold text-slate-800 mb-3">Work Order Summary by Department</h2>
            {['water', 'power', 'fibre', 'road'].map(dept => {
              const count = workOrders.filter(w => w.department === dept).length;
              return (
                <div key={dept} className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0">
                  <span style={{ color: DEPT_COLORS[dept] }}>{DEPT_ICONS[dept]}</span>
                  <span className="capitalize text-sm font-medium text-slate-700 w-16">{dept}</span>
                  <div className="flex-1 bg-slate-100 rounded-full h-2">
                    <div className="h-2 rounded-full" style={{ width: `${count / workOrders.length * 100}%`, background: DEPT_COLORS[dept] }} />
                  </div>
                  <span className="text-sm text-slate-500">{count}</span>
                </div>
              );
            })}
          </div>

          <div className="flex gap-3">
            <button onClick={() => setActive('negotiation')} className="btn-primary">
              <Bot size={16} />Run Negotiation
            </button>
            <button onClick={() => setActive('approval')} className="btn-secondary">
              <CheckSquare size={16} />View Approvals
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── Corridor ──────────────────────────────────────────────────────────────────

function CorridorScreen() {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [corridors, setCorridors] = useState<Corridor[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getWorkOrders(), getCorridors(), getConflicts()])
      .then(([wo, c, cf]) => { setWorkOrders(wo); setCorridors(c.corridors); setConflicts(cf.conflicts); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const corridor = corridors[0];
  const conflictWOIds = new Set(conflicts.flatMap(c => c.work_order_ids));

  // Gantt: map work orders to timeline bars
  const startDates = workOrders.filter(w => w.proposed_start).map(w => new Date(w.proposed_start!).getTime());
  const endDates = workOrders.filter(w => w.proposed_end).map(w => new Date(w.proposed_end!).getTime());
  const minDate = startDates.length ? Math.min(...startDates) : Date.now();
  const maxDate = endDates.length ? Math.max(...endDates) : Date.now() + 1;
  const span = maxDate - minDate || 1;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Corridor Planning</h1>
      {error && <ErrorMsg msg={error} />}
      {loading ? <div className="flex justify-center py-12"><Spinner /></div> : (
        <>
          {corridor && (
            <div className="card bg-slate-800 text-white">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-lg">{corridor.name}</h2>
                  <p className="text-slate-400 text-sm mt-1">{corridor.description}</p>
                </div>
                <span className="badge bg-amber-500/20 text-amber-300">DEMO</span>
              </div>
              {corridor.resurfacing_planned_date && (
                <div className="mt-3 flex items-center gap-2 text-amber-300 text-sm">
                  <AlertCircle size={14} />
                  Resurfacing planned: <strong>{fmtDate(corridor.resurfacing_planned_date)}</strong>
                  <span className="text-slate-400">· {corridor.resurfacing_moratorium_days}-day moratorium after</span>
                </div>
              )}
            </div>
          )}

          {/* Conflict Badges */}
          {conflicts.length > 0 && (
            <div className="card border-red-200">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle size={16} className="text-red-600" />
                <span className="font-semibold text-red-700">{conflicts.length} Conflict(s) Detected</span>
              </div>
              <div className="space-y-2">
                {conflicts.map(c => (
                  <div key={c.id} className="text-xs p-2 rounded bg-red-50 border border-red-200">
                    <span className="font-medium text-red-700">{c.conflict_type.replace('_', ' ').toUpperCase()}</span>
                    <span className="text-red-500 ml-2">{c.work_order_ids.join(' + ')}</span>
                    <p className="text-red-600 mt-0.5">{c.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timeline Gantt */}
          <div className="card">
            <h2 className="font-semibold text-slate-800 mb-4">Work Order Timeline (Baseline / Before Negotiation)</h2>
            <div className="space-y-2">
              {workOrders.filter(w => w.proposed_start && w.proposed_end).map(wo => {
                const left = ((new Date(wo.proposed_start!).getTime() - minDate) / span) * 100;
                const width = Math.max(1, ((new Date(wo.proposed_end!).getTime() - new Date(wo.proposed_start!).getTime()) / span) * 100);
                const hasConflict = conflictWOIds.has(wo.id);
                return (
                  <div key={wo.id} className="flex items-center gap-3">
                    <div className="w-16 text-xs text-slate-500 font-mono shrink-0">{wo.id}</div>
                    <div style={{ color: DEPT_COLORS[wo.department] }} className="shrink-0">{DEPT_ICONS[wo.department]}</div>
                    <div className="flex-1 relative h-6 bg-slate-100 rounded">
                      <div
                        className={`absolute h-6 rounded flex items-center px-1 text-white text-xs font-medium ${hasConflict ? 'ring-2 ring-red-400' : ''}`}
                        style={{ left: `${left}%`, width: `${width}%`, minWidth: 20, background: hasConflict ? '#ef4444' : DEPT_COLORS[wo.department] }}
                        title={`${wo.id}: ${fmtDate(wo.proposed_start)} – ${fmtDate(wo.proposed_end)}`}
                      >
                        {width > 5 && wo.id}
                      </div>
                    </div>
                    <span className={`badge ${PRIORITY_COLORS[wo.priority]}`}>{wo.priority}</span>
                    {hasConflict && <AlertCircle size={14} className="text-red-500 shrink-0" />}
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-slate-400 mt-3">Red bars = conflicting work orders. Dates shown are original proposed dates (before coordination).</p>
          </div>

          {/* Work Order Table */}
          <div className="card overflow-x-auto">
            <h2 className="font-semibold text-slate-800 mb-3">Work Orders</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wide">
                  <th className="pb-2 pr-3">ID</th><th className="pb-2 pr-3">Dept</th>
                  <th className="pb-2 pr-3">Start</th><th className="pb-2 pr-3">End</th>
                  <th className="pb-2 pr-3">Days</th><th className="pb-2 pr-3">Deadline</th>
                  <th className="pb-2 pr-3">Cost/Day</th><th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {workOrders.map(wo => (
                  <tr key={wo.id} className={`border-b border-slate-100 ${conflictWOIds.has(wo.id) ? 'bg-red-50' : ''}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{wo.id}</td>
                    <td className="py-2 pr-3">
                      <span className="flex items-center gap-1" style={{ color: DEPT_COLORS[wo.department] }}>
                        {DEPT_ICONS[wo.department]}<span className="capitalize">{wo.department}</span>
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-xs">{fmtDate(wo.proposed_start)}</td>
                    <td className="py-2 pr-3 text-xs">{fmtDate(wo.proposed_end)}</td>
                    <td className="py-2 pr-3">{wo.duration_days}</td>
                    <td className="py-2 pr-3 text-xs">{fmtDate(wo.deadline)}</td>
                    <td className="py-2 pr-3 text-xs">{fmtCost(wo.delay_cost_per_day)}</td>
                    <td className="py-2">
                      <span className={`badge ${STATUS_COLORS[wo.status]}`}>{wo.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Negotiation ───────────────────────────────────────────────────────────────

function NegotiationScreen({ onPlanGenerated }: { onPlanGenerated: (p: Plan) => void }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runNegotiation = async () => {
    setLoading(true); setError(''); setPlan(null);
    try {
      const p = await generatePlan('COR-001');
      setPlan(p);
      onPlanGenerated(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const MetricsBar = ({ label, before, after, good }: { label: string; before: number; after: number; good: 'lower' | 'higher' }) => {
    const improved = good === 'lower' ? after < before : after > before;
    const delta = after - before;
    return (
      <div className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0">
        <span className="text-sm text-slate-600 w-40 shrink-0">{label}</span>
        <span className="text-sm font-mono text-slate-500 w-16">{before.toFixed(0)}</span>
        <ChevronRight size={14} className="text-slate-400" />
        <span className={`text-sm font-bold w-16 ${improved ? 'text-green-600' : delta === 0 ? 'text-slate-600' : 'text-red-600'}`}>{after.toFixed(0)}</span>
        {delta !== 0 && (
          <span className={`badge ${improved ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {improved ? '▼' : '▲'} {Math.abs(delta).toFixed(0)} {improved ? 'better' : 'worse'}
          </span>
        )}
      </div>
    );
  };

  // Gantt for optimized plan
  const ganttItems = plan?.items ?? [];
  const starts = ganttItems.map(i => new Date(i.proposed_start).getTime());
  const ends = ganttItems.map(i => new Date(i.proposed_end).getTime());
  const minT = starts.length ? Math.min(...starts) : Date.now();
  const maxT = ends.length ? Math.max(...ends) : Date.now() + 1;
  const spanT = maxT - minT || 1;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Negotiation Center</h1>
          <p className="text-slate-500 text-sm mt-1">Multi-agent scheduling · <span className="font-medium text-blue-600">Mode: LOCAL SIMULATED AGENTS</span></p>
        </div>
        <button onClick={runNegotiation} disabled={loading} className="btn-primary">
          {loading ? <Spinner /> : <Bot size={16} />}
          {loading ? 'Negotiating…' : 'Run Negotiation'}
        </button>
      </div>

      {error && <ErrorMsg msg={error} />}

      {!plan && !loading && (
        <div className="card text-center py-12 text-slate-400">
          <Bot size={40} className="mx-auto mb-3 opacity-30" />
          <p>Click "Run Negotiation" to trigger multi-agent scheduling.</p>
          <p className="text-xs mt-1">Water · Power · Fibre · Road agents will negotiate over 3 rounds.</p>
        </div>
      )}

      {plan && (
        <>
          {/* Agent Mode Badge */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3">
            <Shield size={18} className="text-blue-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-blue-800">Execution Mode: Local Deterministic Agents</p>
              <p className="text-xs text-blue-600 mt-0.5">
                No external LLM or watsonx Orchestrate connection active. 
                Agents use deterministic strategy rules. Results are not AI-generated free text.
              </p>
            </div>
          </div>

          {/* Negotiation Rounds */}
          {plan.negotiation_rounds.map(rnd => (
            <div key={rnd.round_number} className="card">
              <div className="flex items-center gap-3 mb-3">
                <span className="badge bg-blue-100 text-blue-700">Round {rnd.round_number}</span>
                <span className={`badge ${rnd.conflicts_remaining === 0 ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                  {rnd.conflicts_remaining} conflict(s) remaining
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{rnd.notes}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-400 border-b border-slate-100">
                      <th className="pb-1 pr-3">Agent</th><th className="pb-1 pr-3">WO</th>
                      <th className="pb-1 pr-3">Proposed Start</th><th className="pb-1 pr-3">End</th>
                      <th className="pb-1 pr-3">Delay Cost</th><th className="pb-1">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rnd.proposals.map((p, i) => (
                      <tr key={i} className="border-b border-slate-50">
                        <td className="py-1 pr-3">
                          <span className="flex items-center gap-1" style={{ color: DEPT_COLORS[p.agent] }}>
                            {DEPT_ICONS[p.agent]}<span className="capitalize font-medium">{p.agent}</span>
                          </span>
                        </td>
                        <td className="py-1 pr-3 font-mono">{p.work_order_id}</td>
                        <td className="py-1 pr-3">{fmtDate(p.proposed_start)}</td>
                        <td className="py-1 pr-3">{fmtDate(p.proposed_end)}</td>
                        <td className="py-1 pr-3 text-slate-600">{fmtCost(p.delay_cost)}</td>
                        <td className="py-1 text-slate-500 max-w-xs truncate" title={p.reason}>{p.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          {/* Before / After */}
          {plan.baseline_metrics && plan.optimized_metrics && (
            <div className="card">
              <h2 className="font-semibold text-slate-800 mb-4">Before vs After Coordination <span className="text-xs text-amber-600 font-normal">(calculated from seed data)</span></h2>
              <MetricsBar label="Road Openings" before={plan.baseline_metrics.road_openings} after={plan.optimized_metrics.road_openings} good="lower" />
              <MetricsBar label="Resurfacing Conflicts" before={plan.baseline_metrics.resurfacing_conflicts} after={plan.optimized_metrics.resurfacing_conflicts} good="lower" />
              <MetricsBar label="Total Work Days" before={plan.baseline_metrics.total_work_days} after={plan.optimized_metrics.total_work_days} good="lower" />
              <MetricsBar label="Total Delay Cost (₹)" before={plan.baseline_metrics.total_delay_cost} after={plan.optimized_metrics.total_delay_cost} good="lower" />
              <MetricsBar label="Hard Violations" before={plan.baseline_metrics.hard_violations} after={plan.optimized_metrics.hard_violations} good="lower" />
              <div className="mt-4 pt-4 border-t border-slate-200 flex gap-6">
                <div><p className="text-xs text-slate-400">Baseline Score</p><p className="text-2xl font-bold text-red-600">{plan.baseline_metrics.score}</p></div>
                <div><p className="text-xs text-slate-400">Optimized Score</p><p className="text-2xl font-bold text-green-600">{plan.optimized_metrics.score}</p></div>
              </div>
              <div className="mt-4">
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={[
                    { name: 'Road Openings', before: plan.baseline_metrics.road_openings, after: plan.optimized_metrics.road_openings },
                    { name: 'Resurf. Conflicts', before: plan.baseline_metrics.resurfacing_conflicts, after: plan.optimized_metrics.resurfacing_conflicts },
                    { name: 'Hard Violations', before: plan.baseline_metrics.hard_violations, after: plan.optimized_metrics.hard_violations },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="before" name="Before" fill="#ef4444" />
                    <Bar dataKey="after" name="After" fill="#22c55e" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Optimized Timeline */}
          <div className="card">
            <h2 className="font-semibold text-slate-800 mb-4">Coordinated Schedule (After Negotiation)</h2>
            <div className="space-y-2">
              {ganttItems.map(item => {
                const left = ((new Date(item.proposed_start).getTime() - minT) / spanT) * 100;
                const width = Math.max(1, ((new Date(item.proposed_end).getTime() - new Date(item.proposed_start).getTime()) / spanT) * 100);
                return (
                  <div key={item.work_order_id} className="flex items-center gap-3">
                    <div className="w-16 text-xs text-slate-500 font-mono shrink-0">{item.work_order_id}</div>
                    <span style={{ color: DEPT_COLORS[item.department] }}>{DEPT_ICONS[item.department]}</span>
                    <div className="flex-1 relative h-6 bg-slate-100 rounded">
                      <div
                        className="absolute h-6 rounded text-white text-xs flex items-center px-1 font-medium"
                        style={{ left: `${left}%`, width: `${width}%`, minWidth: 20, background: DEPT_COLORS[item.department] }}
                        title={item.reason}
                      >
                        {width > 5 && item.work_order_id}
                      </div>
                    </div>
                    <span className="text-xs text-slate-400 w-20 shrink-0">{fmtDate(item.proposed_start)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Explanation */}
          <div className="card bg-slate-50">
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Negotiation Explanation</h3>
            <p className="text-xs text-slate-600 leading-relaxed">{plan.explanation}</p>
          </div>
        </>
      )}
    </div>
  );
}

// ── Approval ──────────────────────────────────────────────────────────────────

function ApprovalScreen({ currentPlan, onApproved }: { currentPlan: Plan | null; onApproved: (p: Plan) => void }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [rejReason, setRejReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getPlans().then(setPlans);
  }, []);

  useEffect(() => {
    if (currentPlan) setSelectedPlan(currentPlan);
  }, [currentPlan]);

  const refresh = () => getPlans().then(setPlans);

  const handleApprove = async () => {
    if (!selectedPlan) return;
    setLoading(true); setError('');
    try {
      const p = await approvePlan(selectedPlan.id);
      setMsg('✓ Plan approved and recorded.');
      setSelectedPlan(p);
      onApproved(p);
      refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || String(e));
    } finally { setLoading(false); }
  };

  const handleReject = async () => {
    if (!selectedPlan || !rejReason.trim()) { setError('Rejection reason required.'); return; }
    setLoading(true); setError('');
    try {
      const p = await rejectPlan(selectedPlan.id, rejReason);
      setMsg('Plan rejected. Go to Negotiation Center and run a new negotiation to generate a revised plan.');
      setSelectedPlan(p);
      setRejReason('');
      refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || String(e));
    } finally { setLoading(false); }
  };

  const plan = selectedPlan;
  const vr = plan?.validation_result;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Approval Center</h1>

      {plans.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-600 mb-2">Existing Plans</h2>
          <div className="flex flex-wrap gap-2">
            {plans.map(p => (
              <button key={p.id} onClick={() => setSelectedPlan(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${selectedPlan?.id === p.id ? 'bg-slate-800 text-white border-slate-800' : 'bg-white border-slate-300 text-slate-700 hover:border-slate-400'}`}>
                {p.id} <span className="opacity-60 ml-1">{p.status}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {!plan && <div className="card text-center py-12 text-slate-400"><p>Run negotiation first to generate a plan for approval.</p></div>}

      {plan && (
        <>
          <div className="card">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="font-bold text-slate-800">{plan.id}</h2>
                <p className="text-xs text-slate-500">Generated {fmtDate(plan.created_at)} · {plan.agent_mode}</p>
              </div>
              <span className={`badge ${
                plan.status === 'approved' ? 'bg-green-100 text-green-700' :
                plan.status === 'rejected' ? 'bg-red-100 text-red-700' :
                plan.status === 'validated' ? 'bg-blue-100 text-blue-700' :
                'bg-slate-100 text-slate-600'
              } text-sm`}>{plan.status.toUpperCase()}</span>
            </div>

            {/* Validation Result */}
            {vr && (
              <div className={`rounded-xl p-4 mb-4 ${vr.valid ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                <div className="flex items-center gap-2 mb-2">
                  {vr.valid ? <CheckCircle2 size={18} className="text-green-600" /> : <XCircle size={18} className="text-red-600" />}
                  <span className={`font-semibold ${vr.valid ? 'text-green-800' : 'text-red-800'}`}>
                    Validation {vr.valid ? 'PASSED' : 'FAILED'} · Score: {vr.score}/100
                  </span>
                </div>
                {vr.violations.length > 0 && (
                  <div className="space-y-1">
                    {vr.violations.map((v, i) => (
                      <div key={i} className={`text-xs px-3 py-1.5 rounded ${v.severity === 'hard' ? 'bg-red-100 text-red-700' : 'bg-amber-50 text-amber-700'}`}>
                        <strong>{v.severity.toUpperCase()}</strong> · {v.rule}: {v.description}
                      </div>
                    ))}
                  </div>
                )}
                {vr.warnings.map((w, i) => (
                  <div key={i} className="text-xs px-3 py-1 text-amber-700 mt-1">⚠ {w}</div>
                ))}
              </div>
            )}

            {/* Scheduled Items */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs text-slate-400">
                    <th className="text-left pb-2 pr-3">Work Order</th>
                    <th className="text-left pb-2 pr-3">Dept</th>
                    <th className="text-left pb-2 pr-3">Start</th>
                    <th className="text-left pb-2 pr-3">End</th>
                    <th className="text-left pb-2 pr-3">Delay Cost</th>
                    <th className="text-left pb-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.items.map(item => (
                    <tr key={item.work_order_id} className="border-b border-slate-100">
                      <td className="py-2 pr-3 font-mono text-xs">{item.work_order_id}</td>
                      <td className="py-2 pr-3">
                        <span style={{ color: DEPT_COLORS[item.department] }} className="flex items-center gap-1">
                          {DEPT_ICONS[item.department]}<span className="capitalize text-xs">{item.department}</span>
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-xs">{fmtDate(item.proposed_start)}</td>
                      <td className="py-2 pr-3 text-xs">{fmtDate(item.proposed_end)}</td>
                      <td className="py-2 pr-3 text-xs">{fmtCost(item.delay_cost)}</td>
                      <td className="py-2 text-xs text-slate-500 max-w-xs truncate" title={item.reason}>{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {msg && <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-200 rounded-lg p-3 text-sm"><CheckCircle2 size={16} />{msg}</div>}
          {error && <ErrorMsg msg={error} />}

          {plan.status !== 'approved' && plan.status !== 'rejected' && (
            <div className="flex gap-3 flex-wrap">
              <button
                onClick={handleApprove}
                disabled={loading || !vr?.valid}
                className="btn-success"
                title={!vr?.valid ? 'Cannot approve: plan has hard violations' : ''}
              >
                {loading ? <Spinner /> : <CheckCircle2 size={16} />}
                Approve Plan
              </button>
              <div className="flex gap-2 flex-1">
                <input
                  value={rejReason}
                  onChange={e => setRejReason(e.target.value)}
                  placeholder="Rejection reason (required)"
                  className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
                />
                <button onClick={handleReject} disabled={loading} className="btn-danger">
                  <XCircle size={16} />Reject
                </button>
              </div>
            </div>
          )}

          {plan.status === 'approved' && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
              <CheckCircle2 size={20} className="text-green-600" />
              <div>
                <p className="font-semibold text-green-800">Plan Approved</p>
                <p className="text-xs text-green-600">By {plan.approved_by} · {fmtDate(plan.approved_at)}</p>
              </div>
            </div>
          )}

          {plan.status === 'rejected' && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <XCircle size={18} className="text-red-600" />
                <p className="font-semibold text-red-800">Plan Rejected</p>
              </div>
              <p className="text-xs text-red-600 mb-3">Reason: {plan.rejection_reason}</p>
              <p className="text-xs text-slate-500">Go to <strong>Negotiation Center</strong> → Run Negotiation to generate a revised plan.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Emergency ─────────────────────────────────────────────────────────────────

function EmergencyScreen({ onEmergency }: { onEmergency: () => void }) {
  const [emergencies, setEmergencies] = useState<Emergency[]>([]);
  const [desc, setDesc] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => { getEmergencies().then(setEmergencies); }, []);

  const submit = async () => {
    if (!desc.trim() || !location.trim()) { setError('Description and location required.'); return; }
    setLoading(true); setError(''); setSuccess('');
    try {
      const em = await reportEmergency('COR-001', desc, location);
      setEmergencies(prev => [em, ...prev]);
      setSuccess(`Emergency ${em.id} recorded. Work order ${em.work_order_id} created with CRITICAL priority. Re-run negotiation to update the schedule.`);
      setDesc(''); setLocation('');
      onEmergency();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || String(e));
    } finally { setLoading(false); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center shrink-0">
          <AlertTriangle size={24} className="text-red-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-red-800">Emergency Override</h1>
          <p className="text-red-600 text-sm mt-1">Report a burst pipe or urgent infrastructure failure. Creates a CRITICAL work order and triggers re-planning.</p>
        </div>
      </div>

      <div className="card border-red-200">
        <h2 className="font-semibold text-slate-700 mb-4">Report Burst Pipe / Emergency</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Description</label>
            <textarea
              value={desc} onChange={e => setDesc(e.target.value)}
              placeholder="e.g. Burst water main at Mahadevapura junction causing roadway flooding"
              className="w-full border border-slate-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
              rows={3}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Location</label>
            <input
              value={location} onChange={e => setLocation(e.target.value)}
              placeholder="e.g. Mahadevapura junction, near Metro pillar 42"
              className="w-full border border-slate-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
            />
          </div>
        </div>
        {error && <div className="mt-3"><ErrorMsg msg={error} /></div>}
        {success && (
          <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">
            <CheckCircle2 size={16} className="inline mr-2" />{success}
          </div>
        )}
        <button onClick={submit} disabled={loading} className="btn-danger mt-4">
          {loading ? <Spinner /> : <AlertTriangle size={16} />}
          {loading ? 'Recording…' : 'Report Emergency'}
        </button>
      </div>

      {emergencies.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-slate-800 mb-3">Emergency History</h2>
          <div className="space-y-3">
            {emergencies.map(em => (
              <div key={em.id} className="bg-red-50 border border-red-200 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="badge bg-red-200 text-red-800 font-mono">{em.id}</span>
                  <span className="text-xs text-slate-500">{fmtDate(em.created_at)}</span>
                  <span className="badge bg-slate-100 text-slate-600">WO: {em.work_order_id}</span>
                </div>
                <p className="text-sm text-red-800 font-medium">{em.description}</p>
                <p className="text-xs text-red-600 mt-1">📍 {em.location} · Reported by: {em.reported_by}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Policy & Audit ────────────────────────────────────────────────────────────

function PolicyAuditScreen() {
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [tab, setTab] = useState<'policy' | 'audit'>('policy');
  const [newPolicy, setNewPolicy] = useState({ name: '', description: '', rule_type: 'restricted_period', start_date: '', end_date: '' });
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getPolicies(), getAuditLog()])
      .then(([p, a]) => { setPolicies(p); setAuditLog(a); });
  }, []);

  const refresh = () => {
    Promise.all([getPolicies(), getAuditLog()])
      .then(([p, a]) => { setPolicies(p); setAuditLog(a); });
  };

  const propose = async () => {
    if (!newPolicy.name || !newPolicy.description) { setError('Name and description required.'); return; }
    setLoading(true); setError('');
    try {
      await proposePolicy({
        name: newPolicy.name, description: newPolicy.description,
        rule_type: newPolicy.rule_type,
        parameters: newPolicy.start_date ? { start_date: newPolicy.start_date, end_date: newPolicy.end_date } : {},
      });
      setMsg('Policy proposed. Awaiting approval.');
      setNewPolicy({ name: '', description: '', rule_type: 'restricted_period', start_date: '', end_date: '' });
      refresh();
    } catch (e: unknown) {
      setError(String(e));
    } finally { setLoading(false); }
  };

  const approve = async (id: string) => {
    setLoading(true);
    try { await approvePolicy(id); setMsg('Policy approved.'); refresh(); }
    catch (e: unknown) { setError(String(e)); }
    finally { setLoading(false); }
  };

  const AUDIT_COLORS: Record<string, string> = {
    plan_proposed: 'text-blue-600', plan_approved: 'text-green-600', plan_rejected: 'text-red-600',
    emergency_created: 'text-red-700', policy_approved: 'text-purple-600', demo_reset: 'text-slate-500',
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Policy & Audit</h1>
      <div className="flex gap-2">
        {(['policy', 'audit'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'}`}>
            {t === 'policy' ? 'Policies' : 'Audit Log'}
          </button>
        ))}
      </div>

      {tab === 'policy' && (
        <>
          <div className="card">
            <h2 className="font-semibold text-slate-700 mb-3">Propose New Policy</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-xs text-blue-700">
              <strong>Safe Workflow:</strong> Policies are proposed in plain language, structured, reviewed, and approved by a human coordinator before taking effect. No code is executed from user input.
            </div>
            <div className="space-y-3">
              <input value={newPolicy.name} onChange={e => setNewPolicy({ ...newPolicy, name: e.target.value })}
                placeholder="Policy name" className="w-full border border-slate-300 rounded-lg p-2.5 text-sm" />
              <textarea value={newPolicy.description} onChange={e => setNewPolicy({ ...newPolicy, description: e.target.value })}
                placeholder="Policy description (e.g. No excavation within 200m of schools during exam period)" rows={2}
                className="w-full border border-slate-300 rounded-lg p-2.5 text-sm resize-none" />
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-xs text-slate-500">Start Date</label>
                  <input type="date" value={newPolicy.start_date} onChange={e => setNewPolicy({ ...newPolicy, start_date: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm mt-1" />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500">End Date</label>
                  <input type="date" value={newPolicy.end_date} onChange={e => setNewPolicy({ ...newPolicy, end_date: e.target.value })}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm mt-1" />
                </div>
              </div>
            </div>
            {error && <div className="mt-2"><ErrorMsg msg={error} /></div>}
            {msg && <div className="mt-2 text-green-700 text-sm">{msg}</div>}
            <button onClick={propose} disabled={loading} className="btn-primary mt-3">
              {loading ? <Spinner /> : <FileText size={16} />}Propose Policy
            </button>
          </div>

          <div className="card">
            <h2 className="font-semibold text-slate-800 mb-3">Active & Proposed Policies</h2>
            <div className="space-y-3">
              {policies.map(p => (
                <div key={p.id} className={`rounded-xl p-4 border ${p.status === 'approved' ? 'border-green-200 bg-green-50' : p.status === 'proposed' ? 'border-amber-200 bg-amber-50' : 'border-red-200 bg-red-50'}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-slate-800">{p.name}</p>
                      <p className="text-xs text-slate-600 mt-1">{p.description}</p>
                      <div className="flex gap-2 mt-2">
                        <span className="badge bg-slate-200 text-slate-600">{p.rule_type}</span>
                        <span className="badge bg-slate-200 text-slate-600">{p.id}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className={`badge ${p.status === 'approved' ? 'bg-green-200 text-green-800' : p.status === 'proposed' ? 'bg-amber-200 text-amber-800' : 'bg-red-200 text-red-800'}`}>
                        {p.status}
                      </span>
                      {p.status === 'proposed' && (
                        <button onClick={() => approve(p.id)} disabled={loading} className="btn-success text-xs py-1 px-2">
                          Approve
                        </button>
                      )}
                    </div>
                  </div>
                  {p.parameters && Object.keys(p.parameters).length > 0 && (
                    <pre className="text-xs text-slate-500 bg-white/50 rounded p-2 mt-2 overflow-x-auto">
                      {JSON.stringify(p.parameters, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {tab === 'audit' && (
        <div className="card">
          <h2 className="font-semibold text-slate-800 mb-3">Audit Log <span className="text-xs text-slate-400 font-normal">(append-only)</span></h2>
          {auditLog.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">No audit events yet. Generate a plan to see entries.</p>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {auditLog.map(entry => (
                <div key={entry.id} className="flex items-start gap-3 py-2 border-b border-slate-100 last:border-0">
                  <Activity size={14} className={`mt-0.5 shrink-0 ${AUDIT_COLORS[entry.action] ?? 'text-slate-400'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs font-semibold ${AUDIT_COLORS[entry.action] ?? 'text-slate-600'}`}>{entry.action.replace(/_/g, ' ').toUpperCase()}</span>
                      <span className="text-xs text-slate-400 font-mono">{entry.entity_id}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {entry.actor} · <Clock size={10} className="inline" /> {fmtDate(entry.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Advisory ──────────────────────────────────────────────────────────────────

function AdvisoryScreen({ approvedPlan }: { approvedPlan: Plan | null }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [lang, setLang] = useState<'en' | 'kn'>('en');
  const [ttsStatus, setTtsStatus] = useState<'idle' | 'speaking' | 'unsupported'>('idle');
  const [loading, setLoading] = useState(false);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [error, setError] = useState('');
  const speechRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Re-fetch plans every time this screen mounts (user may have just approved one)
  useEffect(() => {
    setLoadingPlans(true);
    getPlans()
      .then(p => {
        setPlans(p);
        if (p.length > 0 && !selectedPlanId) setSelectedPlanId(p[0].id);
      })
      .finally(() => setLoadingPlans(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (approvedPlan) setSelectedPlanId(approvedPlan.id);
  }, [approvedPlan]);

  const loadAdvisory = useCallback(async () => {
    if (!selectedPlanId) return;
    setAdvisory(null);
    setLoading(true); setError('');
    try {
      const adv = await getAdvisory(selectedPlanId);
      setAdvisory(adv);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Failed to load advisory. The plan may have no scheduled items.');
    } finally { setLoading(false); }
  }, [selectedPlanId]);

  useEffect(() => { if (selectedPlanId) loadAdvisory(); }, [selectedPlanId, loadAdvisory]);

  const speak = () => {
    if (!window.speechSynthesis) { setTtsStatus('unsupported'); return; }
    if (ttsStatus === 'speaking') { window.speechSynthesis.cancel(); setTtsStatus('idle'); return; }
    if (!advisory) return;
    const text = lang === 'en'
      ? `${advisory.impact_en} ${advisory.precaution_en}`
      : `${advisory.impact_kn} ${advisory.precaution_kn}`;
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = lang === 'en' ? 'en-IN' : 'kn-IN';
    utt.onend = () => setTtsStatus('idle');
    utt.onerror = () => setTtsStatus('idle');
    speechRef.current = utt;
    window.speechSynthesis.speak(utt);
    setTtsStatus('speaking');
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Citizen Advisory</h1>
          <p className="text-slate-500 text-sm mt-1">Prototype-generated notice · Not an official public announcement</p>
        </div>
      </div>

      {/* Plan selector */}
      {loadingPlans ? (
        <div className="flex justify-center py-4"><Spinner /></div>
      ) : plans.length === 0 ? (
        <div className="card text-center py-12">
          <Megaphone size={36} className="mx-auto mb-3 text-slate-300" />
          <p className="text-slate-500 font-medium">No plans available yet.</p>
          <p className="text-slate-400 text-sm mt-1">
            Go to <strong>Negotiation Center</strong> → Run Negotiation, then approve a plan to generate an advisory.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-600">Plan:</label>
          <select
            value={selectedPlanId}
            onChange={e => { setSelectedPlanId(e.target.value); setAdvisory(null); setError(''); }}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
          >
            {plans.map(p => (
              <option key={p.id} value={p.id}>
                {p.id} — {p.status}{p.status === 'approved' ? ' ✓' : ''}
              </option>
            ))}
          </select>
          <button onClick={loadAdvisory} className="btn-secondary text-xs py-1.5 px-3">
            Refresh
          </button>
        </div>
      )}

      {loading && <div className="flex justify-center py-8"><Spinner /></div>}
      {error && <ErrorMsg msg={error} />}

      {!loading && !error && advisory && (
        <>
          {/* Main advisory card — dark navy background */}
          <div className="rounded-2xl overflow-hidden" style={{ background: '#0f1c2e' }}>
            {/* Header bar */}
            <div className="px-6 pt-5 pb-4 border-b border-white/10">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-amber-400/20 text-amber-300 mb-2">
                    ⚠ PROTOTYPE — NOT AN OFFICIAL ADVISORY
                  </span>
                  <h2 className="text-white text-xl font-bold leading-snug">{advisory.corridor_name}</h2>
                  {advisory.work_types.length > 0 && (
                    <p className="text-slate-400 text-xs mt-1">
                      Work: {advisory.work_types.join(' · ')}
                    </p>
                  )}
                </div>
                {/* Language toggle */}
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => setLang('en')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      lang === 'en' ? 'bg-white text-slate-900' : 'text-white/70 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    EN
                  </button>
                  <button
                    onClick={() => setLang('kn')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      lang === 'kn' ? 'bg-white text-slate-900' : 'text-white/70 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    ಕನ್ನಡ
                  </button>
                </div>
              </div>
            </div>

            {/* Dates row */}
            <div className="px-6 py-4 bg-white/5 flex items-center gap-6">
              <div>
                <p className="text-slate-400 text-xs uppercase tracking-wide mb-0.5">From</p>
                <p className="text-white font-bold text-lg">{fmtDate(advisory.start_date)}</p>
              </div>
              <ChevronRight size={20} className="text-slate-500" />
              <div>
                <p className="text-slate-400 text-xs uppercase tracking-wide mb-0.5">To</p>
                <p className="text-white font-bold text-lg">{fmtDate(advisory.end_date)}</p>
              </div>
            </div>

            {/* Impact text */}
            <div className="px-6 py-5">
              <p className="text-slate-200 text-sm leading-relaxed font-medium mb-1">
                {lang === 'en' ? 'Impact' : 'ಪ್ರಭಾವ'}
              </p>
              <p className="text-white text-sm leading-relaxed">
                {lang === 'en' ? advisory.impact_en : advisory.impact_kn}
              </p>
            </div>

            {/* Precaution box */}
            <div className="mx-6 mb-5 rounded-xl bg-amber-500/15 border border-amber-500/30 p-4">
              <p className="text-amber-300 text-xs font-semibold uppercase tracking-wide mb-2">
                {lang === 'en' ? 'Precautions' : 'ಮುನ್ನೆಚ್ಚರಿಕೆಗಳು'}
              </p>
              <p className="text-amber-100 text-sm leading-relaxed">
                {lang === 'en' ? advisory.precaution_en : advisory.precaution_kn}
              </p>
            </div>

            {/* TTS bar */}
            <div className="px-6 pb-5 flex items-center gap-3">
              <button
                onClick={speak}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  ttsStatus === 'speaking'
                    ? 'bg-red-500/80 text-white hover:bg-red-500'
                    : 'bg-white/15 text-white hover:bg-white/25'
                }`}
              >
                <Volume2 size={15} />
                {ttsStatus === 'speaking' ? 'Stop Reading' : 'Read Aloud'}
              </button>
              {ttsStatus === 'unsupported' && (
                <span className="text-slate-400 text-xs">
                  Text-to-speech is not available in this browser. Read the advisory above.
                </span>
              )}
            </div>
          </div>

          {/* Footer metadata */}
          <p className="text-xs text-slate-400 text-center">
            Advisory last updated: {fmtDate(advisory.updated_at)} · Prototype only · Not an official notice
          </p>
        </>
      )}

      {/* Empty state when plan selected but no advisory loaded yet and no error */}
      {!loading && !error && !advisory && selectedPlanId && plans.length > 0 && (
        <div className="card text-center py-10 text-slate-400">
          <p>Select a plan above to load the advisory.</p>
        </div>
      )}
    </div>
  );
}

// ── App Shell ─────────────────────────────────────────────────────────────────

export default function App() {
  const [activeScreen, setActiveScreen] = useState('overview');
  const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
  const [approvedPlan, setApprovedPlan] = useState<Plan | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    if (!confirm('Reset all demo data? This will clear all plans, emergencies, and audit log.')) return;
    setResetting(true);
    await resetDemo();
    setCurrentPlan(null);
    setApprovedPlan(null);
    setResetKey(k => k + 1);
    setActiveScreen('overview');
    setResetting(false);
  };

  return (
    <div className="flex min-h-screen" key={resetKey}>
      {resetting && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 flex items-center gap-4 shadow-xl">
            <Spinner />
            <span className="font-medium text-slate-700">Resetting demo…</span>
          </div>
        </div>
      )}
      <Sidebar active={activeScreen} setActive={setActiveScreen} onReset={handleReset} />
      <main className="flex-1 overflow-auto max-h-screen">
        {activeScreen === 'overview' && <OverviewScreen setActive={setActiveScreen} />}
        {activeScreen === 'corridor' && <CorridorScreen />}
        {activeScreen === 'negotiation' && <NegotiationScreen onPlanGenerated={setCurrentPlan} />}
        {activeScreen === 'approval' && <ApprovalScreen currentPlan={currentPlan} onApproved={setApprovedPlan} />}
        {activeScreen === 'emergency' && <EmergencyScreen onEmergency={() => {}} />}
        {activeScreen === 'policy' && <PolicyAuditScreen />}
        {activeScreen === 'advisory' && <AdvisoryScreen approvedPlan={approvedPlan} />}
      </main>
    </div>
  );
}
