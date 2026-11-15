import { API_BASE, ApiError, readCookie } from '../../api/client';
import type { Attachment } from '../../api/types';

export const ACCEPT = '.pdf,.jpg,.jpeg,.png,.docx,.xlsx,.pptx';

export interface MovTarget {
  targetType: 'activity_actual' | 'indicator_actual';
  lineageId: string;
  periodId: string;
  label: string;
  editable: boolean;
}

/** Upload one file through the authorised endpoint (shared with the phone upload, P12.2). */
export async function uploadMov(
  target: MovTarget,
  file: File,
  description = '',
): Promise<Attachment> {
  const form = new FormData();
  form.append('target_type', target.targetType);
  form.append('lineage_id', target.lineageId);
  form.append('period_id', target.periodId);
  form.append('description', description);
  form.append('file', file);
  const res = await fetch(`${API_BASE}/attachments`, {
    method: 'POST',
    body: form,
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': readCookie('gm_csrftoken') ?? '', Accept: 'application/json' },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body);
  return body as Attachment;
}
