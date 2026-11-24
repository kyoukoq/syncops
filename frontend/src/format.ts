import type { Health, Status, System } from './api';

export const statusLabels: Record<Status, string> = {
  queued: 'Queued',
  processing: 'Processing',
  retry_scheduled: 'Retry scheduled',
  succeeded: 'Succeeded',
  dead_letter: 'Dead letter',
};

export const healthLabels: Record<Health, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  idle: 'Idle',
  disabled: 'Disabled',
};

export const systems: Record<System, string> = { crm: 'Mock CRM', erp: 'Mock ERP', tms: 'Mock TMS' };

export const roleLabels = { admin: 'Administrator', operator: 'Operator', viewer: 'Viewer' };

export const eventTypes = [
  'company.created', 'contact.created', 'customer.updated', 'account.synced', 'order.created', 'shipment.updated',
];

const formatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' });
const numberFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function time(value: string | number | null | undefined): string {
  if (value == null) return '—';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '—' : formatter.format(date);
}

export function number(value: number | null, unit = ''): string {
  return value == null ? '—' : `${numberFormatter.format(value)}${unit}`;
}

export function eventPath(id: string): string {
  return `#/events/${encodeURIComponent(id)}`;
}
