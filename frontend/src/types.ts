// Dig Once — API types matching backend Pydantic models

export type Department = 'water' | 'power' | 'fibre' | 'road';
export type Priority = 'critical' | 'high' | 'medium' | 'low';
export type WorkOrderStatus = 'pending' | 'approved' | 'in_progress' | 'completed' | 'cancelled' | 'emergency';
export type PlanStatus = 'proposed' | 'validated' | 'approved' | 'rejected' | 'superseded';
export type ConflictType = 'overlap' | 'resurfacing' | 'deadline' | 'dependency' | 'restricted_period';
export type PolicyStatus = 'proposed' | 'approved' | 'rejected';

export interface WorkOrder {
  id: string;
  department: Department;
  corridor_id: string;
  description: string;
  start_window: string;
  end_window: string;
  duration_days: number;
  deadline: string;
  priority: Priority;
  delay_cost_per_day: number;
  flexibility_days: number;
  dependencies: string[];
  is_emergency: boolean;
  status: WorkOrderStatus;
  proposed_start: string | null;
  proposed_end: string | null;
  created_at: string;
}

export interface Corridor {
  id: string;
  name: string;
  description: string;
  resurfacing_planned_date: string | null;
  resurfacing_moratorium_days: number;
  lat: number;
  lon: number;
}

export interface Conflict {
  id: string;
  conflict_type: ConflictType;
  work_order_ids: string[];
  description: string;
  severity: string;
  detected_at: string;
}

export interface AgentProposal {
  agent: string;
  work_order_id: string;
  proposed_start: string;
  proposed_end: string;
  duration_days: number;
  reason: string;
  delay_cost: number;
  round_number: number;
}

export interface NegotiationRound {
  round_number: number;
  proposals: AgentProposal[];
  conflicts_remaining: number;
  notes: string;
}

export interface ScheduledItem {
  work_order_id: string;
  department: Department;
  description: string;
  proposed_start: string;
  proposed_end: string;
  duration_days: number;
  reason: string;
  delay_cost: number;
}

export interface PlanMetrics {
  road_openings: number;
  resurfacing_conflicts: number;
  total_work_days: number;
  total_delay_cost: number;
  hard_violations: number;
  score: number;
}

export interface ValidationViolation {
  rule: string;
  severity: string;
  work_order_ids: string[];
  description: string;
}

export interface ValidationResult {
  valid: boolean;
  violations: ValidationViolation[];
  warnings: string[];
  affected_work_orders: string[];
  explanations: string[];
  validated_at: string;
  score: number;
  score_breakdown: Record<string, number>;
}

export interface Plan {
  id: string;
  corridor_id: string;
  status: PlanStatus;
  items: ScheduledItem[];
  negotiation_rounds: NegotiationRound[];
  baseline_metrics: PlanMetrics | null;
  optimized_metrics: PlanMetrics | null;
  explanation: string;
  created_at: string;
  approved_at: string | null;
  approved_by: string;
  rejection_reason: string | null;
  validation_result: ValidationResult | null;
  agent_mode: string;
}

export interface Emergency {
  id: string;
  corridor_id: string;
  description: string;
  location: string;
  reported_by: string;
  created_at: string;
  work_order_id: string;
  revised_plan_id: string | null;
}

export interface PolicyRule {
  id: string;
  name: string;
  description: string;
  rule_type: string;
  parameters: Record<string, unknown>;
  status: PolicyStatus;
  proposed_by: string;
  proposed_at: string;
  approved_at: string | null;
  test_results: Record<string, unknown> | null;
}

export interface Advisory {
  plan_id: string;
  corridor_name: string;
  work_types: string[];
  start_date: string;
  end_date: string;
  impact_en: string;
  impact_kn: string;
  precaution_en: string;
  precaution_kn: string;
  status: string;
  updated_at: string;
  is_prototype: boolean;
}

export interface AuditEntry {
  id: string;
  action: string;
  entity_id: string;
  entity_type: string;
  actor: string;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface ConflictsResponse {
  conflicts: Conflict[];
  total: number;
}
