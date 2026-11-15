# Inspect the saved Intel analyst demonstration — November 15, 2026

This is the producing Intel team’s saved-report walkthrough for its reported v12 preview on November 15, 2026. Publishing this document does not install the v12 implementation, start its services or transfer its runtime database/reports. Read the [portable publication scope](README.md#portable-publication-scope) and later operating-status report before use.

The original walkthrough starts: Open **http://127.0.0.1:50139** on this Intel computer. Select **Quality & history**, **Simulation**, and session `m16-recovery:session`. The loopback URL refers to the producing Intel host. Inspect the existing saved reports only when its current owner confirms that this preview is available; this document does not request a service or receiver restart, login, or new provider call.

Choose **Explain this cycle** and the saved `m16-recovery` cycle. The recorded facts show:

- One correct finished cycle out of one.
- One successful finished attempt out of two.
- One retry, one recovered cycle and zero first-attempt successes.

Select saved report **`95a78f92-95fb-402f-99a6-546f76f796ca`** to inspect the actual v12 explanation without another provider call. It explains why the final correct cycle coexists with a retained failed attempt and successful retry, distinguishes the three recovery counts, and cites late confirmation. Its measured provider latency is **9.64 seconds**; the producing team’s UI peer review reports support for all ten model-authored propositions. This is a selected-simulation peer assessment; the Mac’s independently checked subset and its limits are recorded in the README.

Inspect **Saved correction records** above the explanation. Destination and outcome changes remain separate: `observedDestination` changes from `null` to `"good_bin"`, while outcome records have their own exact values. Open a correction to inspect its captured source fields and revision. The fixed **Application audit summary** is supplied by the application and is not counted as model-authored interpretation. It does not paraphrase or combine field transitions.

The historical v11 reports `6c812ccf-f39a-4555-8fee-76ce2d55178c` and `b1e4ca05-ca6e-4943-95ad-7c30eebe9bd5` remain preserved. Their audit prose contains a documented ambiguity/error and fails the new v12 audit contract when revalidated. Their original saved status and evidence freshness are historical metadata, not a current-policy verdict. See the [review and regression evidence](README.md).

The following original instruction concerns a separate, deliberately authorized provider evaluation; it is not part of inspecting saved reports or adopting these documents: To exercise a new inference, use **Generate cycle explanation** explicitly. A reply can be rejected if it fails evidence checks; the recorded facts remain available. Changing selection, browsing existing reports, refreshing and replay do not create a provider job. An uncertain transport retry preserves the original request identity.

Choose **Compare sessions**, with baseline `m16-recovery:session` and adaptive `gemma-eval-classification-mismatch:session`. Select saved report **`9216914f-b6ba-402f-bca6-7b13230d72d2`**. It correctly states **insufficient evidence** because the sessions lack reviewed matching protocol, population, settings and timing boundaries. Its provider latency is **3.35 seconds**, with all four checked limitations reported supported by the producing team’s UI peer review. No performance winner or physical benefit is claimed.

This demonstration uses saved simulation only. The existing main Morph services on 3001/8000, current Mac dashboard ownership, native Studio 3000, container Studio 7860 and physical diagnostics remain separately owned.

A later Intel report, `be57f4f6-4f20-479e-bcb6-2164b85bae1b`, records the automatic receiver stop at **06:17:23.644558 UTC** and logout at **06:18:13 UTC** on **November 15, 2026**, with no restart authorized. It separately reports the GET-only worker, passive watcher and main API preserved. The receiver and analyst preview are different processes; neither this report nor this walkthrough proves the preview’s current availability. Preserve the reported stop and use the README’s dated operating context.

A subsequent handoff, `334eb852-954d-49e6-a7c7-90e250b27c85`, observed **November 15, 2026 at 06:45:47.972916 UTC**, reports the main API shutdown timeout, a **06:39:33 UTC** host check with no **8000** listener or health, and controlled recovery still being prepared. See the README's [later operating-status reports](README.md#later-operating-status-reports) for the separate **06:36:26.816413 UTC** `SIGTERM` event and earlier observations. These reported main-API conditions do not establish the preview's current availability.
