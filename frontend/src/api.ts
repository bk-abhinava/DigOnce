import axios from 'axios';
import type {
  WorkOrder, Corridor, ConflictsResponse,
  Plan, ValidationResult, Emergency, PolicyRule, Advisory, AuditEntry
} from './types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

// ── Health ────────────────────────────────────────────────────────────────────
export const getHealth = () => api.get('/health').then(r => r.data);

// ── Work Orders ───────────────────────────────────────────────────────────────
export const getWorkOrders = (corridorId?: string): Promise<WorkOrder[]> =>
  api.get('/api/work-orders', { params: corridorId ? { corridor_id: corridorId } : {} }).then(r => r.data);

// ── Corridors ─────────────────────────────────────────────────────────────────
export const getCorridors = (): Promise<{ corridors: Corridor[] }> =>
  api.get('/api/corridors').then(r => r.data);

// ── Conflicts ─────────────────────────────────────────────────────────────────
export const getConflicts = (corridorId?: string): Promise<ConflictsResponse> =>
  api.get('/api/conflicts', { params: corridorId ? { corridor_id: corridorId } : {} }).then(r => r.data);

// ── Plans ─────────────────────────────────────────────────────────────────────
export const generatePlan = (corridorId: string): Promise<Plan> =>
  api.post('/api/plans/generate', { corridor_id: corridorId }).then(r => r.data);

export const getPlans = (): Promise<Plan[]> =>
  api.get('/api/plans').then(r => r.data);

export const getPlan = (planId: string): Promise<Plan> =>
  api.get(`/api/plans/${planId}`).then(r => r.data);

export const validatePlan = (planId: string): Promise<ValidationResult> =>
  api.post(`/api/plans/${planId}/validate`).then(r => r.data);

export const approvePlan = (planId: string, approvedBy = 'coordinator'): Promise<Plan> =>
  api.post(`/api/plans/${planId}/approve`, { approved_by: approvedBy }).then(r => r.data);

export const rejectPlan = (planId: string, reason: string, rejectedBy = 'coordinator'): Promise<Plan> =>
  api.post(`/api/plans/${planId}/reject`, { reason, rejected_by: rejectedBy }).then(r => r.data);

export const editPlan = (planId: string, items: unknown[], editedBy = 'coordinator'): Promise<Plan> =>
  api.post(`/api/plans/${planId}/edit`, { items, edited_by: editedBy }).then(r => r.data);

// ── Emergencies ───────────────────────────────────────────────────────────────
export const reportEmergency = (corridorId: string, description: string, location: string): Promise<Emergency> =>
  api.post('/api/emergencies', { corridor_id: corridorId, description, location }).then(r => r.data);

export const getEmergencies = (): Promise<Emergency[]> =>
  api.get('/api/emergencies').then(r => r.data);

// ── Audit ─────────────────────────────────────────────────────────────────────
export const getAuditLog = (): Promise<AuditEntry[]> =>
  api.get('/api/audit-log').then(r => r.data);

// ── Policies ──────────────────────────────────────────────────────────────────
export const getPolicies = (): Promise<PolicyRule[]> =>
  api.get('/api/policies').then(r => r.data);

export const proposePolicy = (data: {
  name: string; description: string; rule_type: string; parameters: Record<string, unknown>;
}): Promise<PolicyRule> =>
  api.post('/api/policies/propose', { ...data, proposed_by: 'coordinator' }).then(r => r.data);

export const approvePolicy = (policyId: string): Promise<PolicyRule> =>
  api.post(`/api/policies/${policyId}/approve`, { approved_by: 'coordinator' }).then(r => r.data);

// ── Advisories ────────────────────────────────────────────────────────────────
export const getAdvisory = (planId: string): Promise<Advisory> =>
  api.get(`/api/advisories/${planId}`).then(r => r.data);

// ── Demo ──────────────────────────────────────────────────────────────────────
export const resetDemo = (): Promise<{ message: string }> =>
  api.post('/api/demo/reset').then(r => r.data);
