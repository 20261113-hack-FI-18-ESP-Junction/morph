import React, { useRef, useState } from 'react';
import { StationHttpError } from '@morph/station-client';
import type { CycleDetail, CycleReviewRequest, CycleReviewResult } from '@morph/station-client';
import type { Attempt, Cycle, ReferenceLabel } from '../types/morph.ts';
import { loadPendingReview, preservePendingReview } from '../services/pendingReview.ts';

interface Props {
  cycle: Cycle; attempts: Attempt[]; label: ReferenceLabel | null; evidenceIds: string[];
  available: boolean; onSubmit: (cycleId: string, request: CycleReviewRequest) => Promise<CycleReviewResult>;
  onRefresh: () => Promise<CycleDetail>;
}
const inputStyle = 'mt-1 w-full rounded border border-[#514633] bg-[#101010] px-2 py-2 text-[#F2EEE6] disabled:opacity-50';
const buttonStyle = 'rounded border border-[#6c5840] px-3 py-2 text-[#F2EEE6] disabled:opacity-45';
const idPattern = '[A-Za-z0-9][A-Za-z0-9_.:\\-]{0,119}';

/** An uncertain submission remains unchanged in this browser tab until explicitly retried. */
export function CycleReviewForm({ cycle, attempts, label, evidenceIds, available, onSubmit, onRefresh }: Props) {
  const storageKey = `morph:record-review:${cycle.sessionId}:${cycle.id}`;
  const [base, setBase] = useState({ cycle, attempts, label });
  const [stored] = useState(() => {
    try { return loadPendingReview(sessionStorage, storageKey); }
    catch { return { request: null, invalid: true }; }
  });
  const [pending, setPending] = useState<CycleReviewRequest | null>(stored.request);
  const [invalidSaved, setInvalidSaved] = useState(stored.invalid);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [message, setMessage] = useState('');
  const [rejected, setRejected] = useState(false);
  const [author, setAuthor] = useState('');
  const [reason, setReason] = useState('');
  const [changeLabel, setChangeLabel] = useState(false);
  const [quality, setQuality] = useState(label?.quality ?? 'good');
  const [method, setMethod] = useState(label?.method ?? '');
  const [addConfirmation, setAddConfirmation] = useState(false);
  const [success, setSuccess] = useState('');
  const [confirmedAt, setConfirmedAt] = useState('');
  const [destination, setDestination] = useState('');
  const [attemptId, setAttemptId] = useState('');
  const [attemptOutcome, setAttemptOutcome] = useState('');
  const [outcome, setOutcome] = useState('');
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const changed = base.cycle.revision !== cycle.revision || (base.label?.revision ?? null) !== (label?.revision ?? null);

  const applyBase = (detail: CycleDetail) => {
    const savedLabel = detail.referenceLabels.find(saved=>saved.id===detail.cycle.referenceLabelId);
    setBase({ cycle: { ...cycle, ...detail.cycle },
      attempts: detail.attempts.map(a=>({...a,executionIds:attempts.find(old=>old.id===a.id)?.executionIds ?? []})),
      label: savedLabel ? {...savedLabel,reason:null} : null });
  };
  const send = async (request: CycleReviewRequest) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setRejected(false); setMessage('Saving audited review…');
    try {
      const result = await onSubmit(cycle.id, request);
      sessionStorage.removeItem(storageKey); setPending(null);
      applyBase(result.cycle);
      setChangeLabel(false); setAddConfirmation(false); setOutcome(''); setReason('');
      setMessage(result.duplicate ? 'Confirmed saved review. The identical retry created no duplicate records.' : 'Saved audited review. Original IDs and previous values are retained.');
    } catch (error) {
      if (error instanceof StationHttpError && error.status === 409) {
        setRejected(true); setMessage('Revision conflict. Nothing from this request was applied. Refresh the saved record and review your changes again.');
      } else if (error instanceof StationHttpError && [400, 413, 415, 422].includes(error.status)) {
        setRejected(true); setMessage('Review rejected. Check observation time, evidence, outcome and attempt prerequisites. Confirmed correct needs an independent label, matching inspection and confirmed placement.');
      } else {
        setMessage('The save result is unconfirmed. Your exact request is retained in this tab. Retry it to confirm delivery without creating a duplicate.');
      }
    } finally { busyRef.current = false; setBusy(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busyRef.current || !available || invalidSaved) return;
    if (pending) { await send(pending); return; }
    if (!changeLabel && !addConfirmation && !outcome) { setMessage('Choose a label, confirmation or outcome change.'); return; }
    if (addConfirmation && (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(confirmedAt) || !Number.isFinite(Date.parse(confirmedAt)))) {
      setMessage('Enter the actual observation time with seconds and timezone, for example 2026-11-14T12:30:00-08:00.'); return;
    }
    const request: CycleReviewRequest = { id: crypto.randomUUID(), eventId: crypto.randomUUID(),
      expectedRevision: base.cycle.revision, authorId: author.trim(), reason: reason.trim(), createdAt: new Date().toISOString() };
    if (changeLabel) request.label = { id: base.label?.id ?? crypto.randomUUID(), quality: quality as 'good' | 'defective',
      method: method.trim(), evidenceIds: base.label?.evidenceIds ?? selectedEvidence,
      ...(base.label ? { expectedRevision: base.label.revision } : {}) };
    if (outcome) request.changes = { outcome: outcome as NonNullable<CycleReviewRequest['changes']>['outcome'] };
    if (addConfirmation) {
      const attempt = base.attempts.find(a => a.id === attemptId);
      request.confirmation = { id: crypto.randomUUID(), source: 'operator', confirmedAt,
        physicalSuccess: success === 'yes', observedDestination: destination ? destination as 'good_bin' | 'defective_bin' | 'other' : null,
        evidenceIds: selectedEvidence,
        ...(attempt ? { attemptId: attempt.id, expectedAttemptRevision: attempt.revision,
          ...(attemptOutcome ? { attemptOutcome: attemptOutcome as 'successful' | 'failed' | 'aborted' | 'unverified' } : {}) } : {}) };
    }
    try { preservePendingReview(sessionStorage, storageKey, request); }
    catch { setMessage('This browser could not retain the retry request. No review was sent. Enable session storage before saving.'); return; }
    setPending(request); await send(request);
  };
  const reload = async () => {
    setBusy(true);
    try { const detail = await onRefresh(); applyBase(detail); sessionStorage.removeItem(storageKey); setPending(null); setRejected(false); setMessage('Review the refreshed record before saving. Your draft choices are retained.'); }
    catch { setMessage('The latest saved record could not be loaded. Keep this review and retry the refresh.'); }
    finally { setBusy(false); }
  };
  return <form onSubmit={submit} className="mt-4 space-y-3 border-t border-[#403729] pt-4" aria-label="Audited record review">
    <h3 className="text-[13px] font-medium text-[#F2EEE6]">Audited record review</h3>
    <p>Record independent observations and correct saved results. This form preserves the original cycle and its audit history.</p>
    <p>Reviewing cycle revision {base.cycle.revision}. {changed && <strong className="text-[#D6B775]">A newer revision is available. Refresh before changing it.</strong>}</p>
    {pending && <div className="text-[#D6B775]"><p>Pending review {pending.id}. Retry sends the identical saved values and identifiers.</p><details><summary className="cursor-pointer">Pending review values</summary><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all text-[10px]">{JSON.stringify(pending,null,2)}</pre></details></div>}
    {invalidSaved && <p role="alert">The saved retry draft is unreadable. No request has been sent from it. <button type="button" className={buttonStyle} onClick={()=>{sessionStorage.removeItem(storageKey);setInvalidSaved(false);}}>Clear unreadable draft</button></p>}
    <fieldset disabled={busy || Boolean(pending) || !available || invalidSaved} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label>Author ID<input required pattern={idPattern} maxLength={120} value={author} onChange={e=>setAuthor(e.target.value)} placeholder="operator-name" className={inputStyle}/></label>
        <label>Cycle outcome<select value={outcome} onChange={e=>setOutcome(e.target.value)} className={inputStyle}>
          <option value="">Keep current outcome</option><option value="correct">Confirmed correct</option><option value="failed">Failed</option><option value="aborted">Aborted</option><option value="unverified">Unverified</option>
        </select></label>
      </div>
      <label className="block">Reason for this review<textarea required maxLength={4000} value={reason} onChange={e=>setReason(e.target.value)} className={inputStyle}/></label>
      <label className="flex gap-2"><input type="checkbox" checked={changeLabel} onChange={e=>setChangeLabel(e.target.checked)}/> Add or correct independent reference label</label>
      {changeLabel && <div className="grid gap-3 sm:grid-cols-2">
        <label>Reference quality<select value={quality} onChange={e=>setQuality(e.target.value as 'good' | 'defective')} className={inputStyle}><option value="good">Good</option><option value="defective">Defective</option></select></label>
        <label>Independent labeling method<input required value={method} onChange={e=>setMethod(e.target.value)} placeholder="Describe independent inspection" className={inputStyle}/></label>
      </div>}
      <label className="flex gap-2"><input type="checkbox" checked={addConfirmation} onChange={e=>setAddConfirmation(e.target.checked)}/> Add operator confirmation / late confirmation</label>
      {addConfirmation && <div className="space-y-3">
        <label className="block">Actual observation time (ISO 8601 with timezone)<input required value={confirmedAt} onChange={e=>setConfirmedAt(e.target.value)} placeholder="2026-11-14T12:30:00-08:00" className={inputStyle}/></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label>Commanded physical result observed<select required value={success} onChange={e=>setSuccess(e.target.value)} className={inputStyle}><option value="">Select observed result</option><option value="yes">Achieved</option><option value="no">Not achieved</option></select></label>
          <label>Observed destination<select value={destination} onChange={e=>setDestination(e.target.value)} className={inputStyle}><option value="">Unavailable</option><option value="good_bin">Good bin</option><option value="defective_bin">Defective bin</option><option value="other">Other location</option></select></label>
          <label>Confirmed attempt<select value={attemptId} onChange={e=>setAttemptId(e.target.value)} className={inputStyle}><option value="">Cycle observation only</option>{base.attempts.filter(a=>a.endedAt).map(a=><option key={a.id} value={a.id}>{a.id} · {a.outcome}</option>)}</select></label>
          {attemptId && <label>Attempt outcome<select value={attemptOutcome} onChange={e=>setAttemptOutcome(e.target.value)} className={inputStyle}><option value="">Keep current outcome</option><option value="successful">Confirmed successful</option><option value="failed">Failed</option><option value="aborted">Aborted</option><option value="unverified">Unverified</option></select></label>}
        </div>
      </div>}
      {(changeLabel || addConfirmation) && <div><p>Attach existing evidence for this cycle (optional for operator observations)</p>{evidenceIds.length ? evidenceIds.map(id=><label key={id} className="mt-1 flex gap-2 break-all"><input type="checkbox" checked={selectedEvidence.includes(id)} onChange={e=>setSelectedEvidence(v=>e.target.checked?[...v,id]:v.filter(x=>x!==id))}/>{id}</label>):<p>No attachable evidence recorded.</p>}</div>}
    </fieldset>
    <div className="flex flex-wrap gap-2">
      <button type="submit" disabled={busy || !available || rejected || invalidSaved} className={buttonStyle}>{busy ? 'Saving…' : pending ? 'Retry identical review' : 'Save audited review'}</button>
      {(rejected || (!pending && changed)) && <button type="button" disabled={busy} onClick={()=>void reload()} className={buttonStyle}>Refresh review record</button>}
    </div>
    {!available && <p>Reviewing requires current connected records. Replay remains read-only.</p>}
    {message && <p role="status" aria-live="polite" className="text-[#D6B775]">{message}</p>}
  </form>;
}
