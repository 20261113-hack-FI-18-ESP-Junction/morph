# Morph — dashboard handoff

**Ready for design review and AI Studio implementation · November 14, 2026.** This package turns the supplied Stitch ideas and the current Physical AI project requirements into a consistent visual direction, an inspectable reference and a practical implementation brief.

**Handing this to a builder?** Follow [HANDOVER_GUIDE.md](HANDOVER_GUIDE.md), send [MESSAGE_TO_BUILDER.md](MESSAGE_TO_BUILDER.md) with the complete archive, and check [PACKAGE_FILES.txt](PACKAGE_FILES.txt) for its exact contents.

**Visual start:** open [01-live.png](references/01-live.png), then [DESIGN_SPEC.md](DESIGN_SPEC.md). To build with AI Studio, copy [AI_STUDIO_MASTER_PROMPT.txt](AI_STUDIO_MASTER_PROMPT.txt), use the staged instructions in [AI_STUDIO_PROMPT.md](AI_STUDIO_PROMPT.md), and supply the images and [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).

## What to give the dashboard builder

| Material | Purpose |
| --- | --- |
| [Design specification](DESIGN_SPEC.md) | Palette, typography, spacing, artwork, three views, responsive behavior and exceptional states |
| [AI Studio prompt](AI_STUDIO_PROMPT.md) | Paste-ready master prompt, staged follow-ups and acceptance criteria |
| [Integration contract](INTEGRATION_CONTRACT.md) | Proposed architecture, TypeScript records, events, API routes, model adapters and implementation order |
| [Project audit](PROJECT_AUDIT.md) | Actual project status and corrections to unsupported Stitch claims |
| [Sources and references](REFERENCES.md) | Verified Junction inspiration, current AI Studio guidance and historical artwork provenance |
| [Asset inventory](ASSETS.md) | Editable SVGs, font files, licenses and attribution |
| [Interactive reference](index.html) | Inspect the layout, navigation, camera/map toggle, filters, trace and software-stop status |

The package is in English so the same instructions can go directly to the builder and AI Studio.

## Screen references

| Reference | What it demonstrates |
| --- | --- |
| [01 — Live inspection](references/01-live.png) | Main composition: camera, same-frame analysis, task selection, local execution state and operator goal |
| [02 — Robot & system](references/02-system.png) | Integration readiness and unavailable telemetry without fictional readings |
| [03 — Quality & history](references/03-quality.png) | Separate operational/detection metrics, confusion matrix, history and empty benchmark |
| [04 — Cycle evidence](references/04-cycle-detail.png) | One failed grasp and a successful retry within the same cycle |
| [05 — Software stop](references/05-stop.png) | Request acknowledgment and physical confirmation kept separate |
| [06 — Design language](references/06-design-system.png) | Morph identity, colors, type and controls |
| [07 — Disconnected](references/07-disconnected.png) | Live mode without a station, records or enabled robot controls |
| [08 — Mobile layout](references/08-mobile.png) | Narrow-screen reflow and reachable software-stop control |
| [Overview sheet](references/00-overview.png) | Six core references together |

![Morph live inspection reference](references/01-live.png)

## Quick use in AI Studio

1. Review the main image and the design language image. Start a new app build in Google AI Studio.
2. Supply the eight primary state images and the text of the master prompt, in stages as described in the handover guide. Add the design and integration documents so the images cannot override the actual data and robot rules. If the tool does not accept an artifact type, paste the relevant text and upload the supported PNG references.
3. Ask it to build the persisted domain model and an explicit simulation adapter before counters and charts. Then implement the three views and the exceptional states.
4. Refine one phase at a time with the supplied follow-up prompts. Require a working keyboard path, readable small screens and visible simulation labels.
5. Export the source ZIP or synchronize the project to the team's repository. Connect the frontend to the local Intel station application through the contract. Add secrets only to the chosen server configuration.
6. Verify actual provider access, exact model IDs, Studio/policy interfaces and physical outcomes. A Gemini-assisted build does not replace the product's required online Gemini decision integration.

Current tool capabilities and official links are in [REFERENCES.md](REFERENCES.md). No account, deployment or hardware connection was established for this handoff.

## Open the reference locally

Open `index.html` in a browser. All fonts and assets are included and the reference makes no network requests. For a local HTTP preview, run this from the extracted `Morph-Handoff` folder or the original workspace root:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory design/morph-handoff
```

Then open `http://127.0.0.1:4173`. Use any installed Python 3; the owner's workspace activation is not required or included. A Windows command is in [HANDOVER_GUIDE.md](HANDOVER_GUIDE.md). This serves a presentation prototype, not the station API.

## What is implemented in this reference

The local HTML/CSS/JavaScript supports three-view navigation, overview/wrist illustration switching, a schematic anomaly-map toggle, a disconnected state, outcome filtering, a recovery trace, a software-stop status dialog and summary fixture exports. The decorative top graphic animates slowly and respects reduced-motion settings. No robot is connected and no provider is called.

Important scope boundaries:

- The fixture lives in memory. It is not a persisted session database and refreshing it does not test production reconnect semantics.
- The voice preview describes the capture/finalization/goal states. It does not record a microphone or call ElevenLabs.
- C-007 has a detailed illustrative trace. Other cycles show summary evidence; the full trace UI and audit editor remain implementation work.
- The history initially shows five matching examples without pagination. Exports contain all twelve summary fixture records, not a complete event/frame/model archive.
- The OpenVINO comparison correctly has no measured values. The robot, target hardware, trained skills and required cloud access remain unverified.
- The scene is an original illustration and the historical portrait is a public-domain engraving. Neither is a real inspection image.

The integration contract and build prompt define the complete product requirements. They must not be replaced by the intentionally smaller reference implementation.

## Validation and source context

The screenshots were rendered and visually inspected. A Playwright check exercised the primary navigation and fixture interactions; results are recorded in [verification.json](references/verification.json). An independent review checked the fixture arithmetic, physical-vs-task outcomes, destination separation and unknown-state behavior. These checks validate the handoff, not the physical workflow.

The workspace root was not a Git repository during this work. Canonical project documents and prepared dependencies were preserved. The distributable ZIP includes this folder under `design/morph-handoff/` and selected canonical documents at its root so their relative links resolve. Read [PROJECT_AUDIT.md](PROJECT_AUDIT.md) to see which source is authoritative and which capabilities remain proposed or unverified.
