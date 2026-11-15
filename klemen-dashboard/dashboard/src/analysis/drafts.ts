type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
function browserStorage(): DraftStorage | undefined {
  try { return typeof window === "undefined" ? undefined : window.sessionStorage; } catch { return undefined; }
}
const key = (scope: string) => `morph.analysis.question.v1:${scope}`;

/** Questions are independent per evidence selection and survive local navigation in this tab. */
export function readQuestionDraft(scope: string, storage = browserStorage()): string {
  try {
    const draft = storage?.getItem(key(scope));
    return typeof draft === "string" && draft.length <= 500 ? draft : "";
  } catch { return ""; }
}

export function saveQuestionDraft(scope: string, question: string, storage = browserStorage()): void {
  try {
    if (question.length > 500) return;
    if (question) storage?.setItem(key(scope), question);
    else storage?.removeItem(key(scope));
  } catch { /* An unavailable browser store does not prevent editing the in-memory draft. */ }
}
