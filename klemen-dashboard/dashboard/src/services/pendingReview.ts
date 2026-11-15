import type { CycleReviewRequest } from '@morph/station-client';

type ReviewStorage = Pick<Storage, 'getItem' | 'setItem'>;
const identifier = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(value);
const qualifiedTime = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const revision = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const ids = (value: unknown): value is string[] => Array.isArray(value) && value.every(identifier);

/** Validate stored retry metadata before offering any submission; reading it never sends a request. */
export function loadPendingReview(storage: ReviewStorage, key: string): { request: CycleReviewRequest | null; invalid: boolean } {
  try {
    const raw = storage.getItem(key);
    if (raw === null) return { request: null, invalid: false };
    if (raw.length > 65536) throw new Error();
    const value: unknown = JSON.parse(raw);
    if (!object(value) || !identifier(value.id) || !identifier(value.eventId) || !identifier(value.authorId) || !revision(value.expectedRevision) ||
      !qualifiedTime(value.createdAt) || typeof value.reason !== 'string' || !value.reason.trim()) throw new Error();
    if (value.label !== undefined) {
      const label = value.label;
      if (!object(label) || !identifier(label.id) || !['good','defective'].includes(String(label.quality)) ||
        typeof label.method !== 'string' || !ids(label.evidenceIds) || (label.expectedRevision !== undefined && !revision(label.expectedRevision))) throw new Error();
    }
    if (value.confirmation !== undefined) {
      const confirmation = value.confirmation;
      if (!object(confirmation) || !identifier(confirmation.id) || confirmation.source !== 'operator' || !qualifiedTime(confirmation.confirmedAt) ||
        typeof confirmation.physicalSuccess !== 'boolean' || !ids(confirmation.evidenceIds) ||
        ![null,'good_bin','defective_bin','other'].includes(confirmation.observedDestination as string | null) ||
        (confirmation.attemptId !== undefined && (!identifier(confirmation.attemptId) || !revision(confirmation.expectedAttemptRevision)))) throw new Error();
    }
    return { request: value as unknown as CycleReviewRequest, invalid: false };
  } catch { return { request: null, invalid: true }; }
}
export function preservePendingReview(storage: ReviewStorage, key: string, request: CycleReviewRequest): void {
  const payload = JSON.stringify(request);
  storage.setItem(key,payload);
  if (storage.getItem(key) !== payload) throw new Error('The exact retry payload could not be retained.');
}
