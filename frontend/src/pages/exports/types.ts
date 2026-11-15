export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface Job {
  id: string;
  kind: 'export_xlsx' | 'export_pptx' | 'import_plan';
  status: JobStatus;
  params: Record<string, string>;
  result: Record<string, unknown>;
  error: string;
  requested_by: string | null;
  created_at: string;
  finished_at: string | null;
  file_name: string | null;
  download_url: string | null;
}

export const KIND_LABEL: Record<Job['kind'], string> = {
  export_xlsx: 'Excel workbook',
  export_pptx: 'PowerPoint deck',
  import_plan: 'Plan import',
};

export const STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'Waiting',
  running: 'Preparing…',
  done: 'Ready',
  failed: 'Failed',
};

export const SCOPE_LABEL: Record<string, string> = {
  office: 'One office',
  subtree: 'Office and everything beneath',
  agency: 'Whole agency',
};

export function isPending(job: Job): boolean {
  return job.status === 'queued' || job.status === 'running';
}

export const SLIDE_GROUPS = [
  { key: 'overall', label: 'Overall performance' },
  { key: 'offices', label: 'One slide per office' },
  { key: 'rankings', label: 'Rankings' },
  { key: 'indicators', label: 'Indicator tables' },
] as const;
export type SlideGroup = (typeof SLIDE_GROUPS)[number]['key'];
