import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import { api } from '../../api/client';
import type { Attachment } from '../../api/types';
import { errorMessage } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { dateTime } from '../../lib/format';
import { ACCEPT, uploadMov, type MovTarget } from './movUpload';

function size(bytes: number): string {
  return bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Supporting files (MOVs) of one reported row: list, download, drag-and-drop upload, remove. */
export default function MovDialog({
  target,
  onClose,
  onChanged,
}: {
  target: MovTarget;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [files, setFiles] = useState<Attachment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let active = true;
    api
      .get<Attachment[]>('attachments', {
        target_type: target.targetType,
        lineage_id: target.lineageId,
        period_id: target.periodId,
      })
      .then((list) => active && setFiles(list))
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [target, reloadKey]);

  async function add(list: FileList | File[]) {
    setBusy(true);
    setError(null);
    const problems: string[] = [];
    for (const file of Array.from(list)) {
      try {
        await uploadMov(target, file);
      } catch (err) {
        problems.push(`${file.name}: ${errorMessage(err)}`);
      }
    }
    setBusy(false);
    if (problems.length) setError(problems.join(' '));
    load();
    onChanged();
  }

  async function remove(a: Attachment) {
    if (
      !window.confirm(
        `Remove ${a.file_name}? It is hidden from the report; the file itself is kept for the record.`,
      )
    )
      return;
    try {
      await api.del(`attachments/${a.id}`);
      load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    if (target.editable && e.dataTransfer.files.length) add(e.dataTransfer.files);
  }

  return (
    <Modal title={`Supporting files · ${target.label}`} onClose={onClose} wide>
      <div className="stack">
        {files === null ? (
          <p>Loading…</p>
        ) : files.length === 0 ? (
          <p className="muted">No files yet.</p>
        ) : (
          <ul className="plain-list">
            {files.map((a) => (
              <li key={a.id} className="row-between">
                <a href={a.download_url}>{a.file_name}</a>
                <span className="muted small">
                  {size(a.size_bytes)} · {a.uploaded_by} · {dateTime(a.uploaded_at)}
                </span>
                {target.editable && (
                  <button
                    type="button"
                    className="btn btn-small btn-danger"
                    onClick={() => remove(a)}
                    aria-label={`Remove ${a.file_name}`}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        <FormError message={error} />
        {target.editable && (
          <div
            className={`dropzone ${over ? 'over' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            <p>{busy ? 'Uploading…' : 'Drop files here, or'}</p>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => input.current?.click()}
            >
              Choose files
            </button>
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPT}
              hidden
              aria-label="Choose files to attach"
              onChange={(e) => e.target.files && add(e.target.files)}
            />
            <p className="muted small">PDF, JPG, PNG, DOCX, XLSX or PPTX, up to 25 MB each.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
