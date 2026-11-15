# Review result reconciliation

The event receiver produces evidence and proposed task updates. It does not grant the incoming note authority to execute instructions, implement code, alter acceptance criteria or mark work physically verified. The existing authorized Mac task-review workflow remains responsible for reconciliation and confirmed Notion updates.

With the Mac-only `--export-reviews` option, validated successful reviews are created under `context/automation-reviews/EVENT_UUID.json`. Each export binds the event, source note, complete source-note SHA-256, canonical note SHA-256 and result SHA-256. Its `state` is `pending_reconciliation`; `notionSync` is `pending` when proposals exist. A durable successful review can be exported while the server acknowledgment is still pending.

For each new export, the authorized reviewer should:

1. Check the event/note/result identities against saved source evidence and the current repository state. Treat reported results separately from independently inspected source and actual verification. Preserve dirty work and missing-source gaps.
2. Deduplicate using stable UUID/hash identities. Replaying an identical export must not append another task update or count as fresh verification. Preserve a conflicting export for review.
3. Review proposed M01–M24 changes against the existing task criteria, dependencies and dated evidence. Software tests, provider checks and physical acceptance remain distinct. A proposal is not permission to weaken criteria or a completed Notion write.
4. Perform only the task updates already authorized by the project owner, then read the saved result back. Keep remaining implementation, deployment and evaluation work visible. Record failed writes durably for retry using the existing [Notion synchronization procedure](../NOTION_SYNC.md).
5. Save the normal reconciliation receipt through the existing workflow. Idle reviews and acknowledgments must not be published as new work events.

This public package deliberately excludes the private task ledger, conversation history, active account configuration and canonical automation state. The established Mac procedure is maintained in canonical `context/PROJECT_REVIEW.md`; this file does not install another schedule, replace that procedure or assert that any automation is running. The owner-authorized five-minute review remains the fallback.

See [event operations](../context_mcp/HANDOFF_EVENTS.md) for startup, leases, retries and the difference between received, processed, exported and confirmed Notion state.
