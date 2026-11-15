# Morph — reference sources and visual rationale

**Verified on November 14, 2026.** This reference sheet distinguishes Junction's published visual material, the owner's supplied Stitch concepts, and the design decisions proposed for Morph. It is not an official Junction brand manual. The canonical project facts and corrections are in [PROJECT_AUDIT.md](PROJECT_AUDIT.md); the proposed product interfaces are in [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).

## 1. Primary reference register

| Reference | What was verified | How to use it |
| --- | --- | --- |
| [Junction 2026 official site](https://2026.hackjunction.com/) | The page explicitly describes its story as the European Tech Renaissance. Its story section pairs a contemporary Copernicus image with a Mona Lisa image. The narrative uses a change in the center of gravity as its central idea. | Use the historical-scientific atmosphere and editorial hierarchy as inspiration. Morph should retain its own identity. |
| [Junction site stylesheet](https://2026.hackjunction.com/_next/static/css/5d91d4904846016b.css?dpl=dpl_4KdWUeWENW5bEuLLUo6rxzd4oKwi) | The served CSS defines warm, dark surfaces, parchment/sand tones, restrained borders, and explicit main/display/mono type stacks. | This is evidence of the implementation inspected on this date, not a permanent brand specification. The hashed URL may change after deployment. |
| [Junction font stylesheet](https://2026.hackjunction.com/_next/static/css/8f7be9f82bdc7e78.css?dpl=dpl_4KdWUeWENW5bEuLLUo6rxzd4oKwi) | Font-face declarations include Titillium Web, Inter, and Space Mono. | Reproduce a related typographic character through Morph's own licensed font files and tokens. |
| [Junction Copernicus artwork](https://2026.hackjunction.com/images/copernicus-builder.jpg) | The official page identifies this as Copernicus at a desk with an armillary sphere, laptop, and star charts. | Mood reference for the relationship between old scientific instruments and present-day building. This review did not establish a reuse license for Junction's modified artwork. |
| [Junction hero artwork](https://2026.hackjunction.com/images/venus-hero.png) and [technical art treatment](https://2026.hackjunction.com/images/venus-cv.jpg) | Both asset paths appear in the official page. The hero and manifesto use art as large atmospheric layers. | The handoff adapts this layering into a small decorative header. Never put these paintings in Morph's camera evidence panel. |
| [Copernicus engraving, Wellcome Collection](https://wellcomecollection.org/works/n6ut6uxr) | The collection credits Edward Scriven and labels the work Public Domain Mark. The record offers full-size and 760-pixel image downloads. | Preferred historical portrait source for a subtle engraving treatment, with attribution retained in the asset notes. |
| [Build apps in Google AI Studio](https://aistudio.google.com/docs/aistudio-build-mode) | The current documentation describes web Build mode, React as the default frontend, a Node.js server, code editing, GitHub synchronization and ZIP export. | Build and inspect the reference UI, then export or synchronize it for integration with the actual station application. |
| [Develop full-stack apps in Google AI Studio](https://aistudio.google.com/docs/aistudio-fullstack) | The documented server runtime can handle external API calls and secrets. Third-party credentials belong in Settings → Secrets and server-side code. | Keep provider credentials out of the browser. Use the station architecture in the integration contract. |

The earlier Google URLs `https://ai.google.dev/gemini-api/docs/aistudio-build-mode` and `https://ai.google.dev/gemini-api/docs/aistudio-fullstack` redirected to the corresponding `aistudio.google.com/docs/` pages during this review. No AI Studio account, model entitlement, deployment, or physical device connection was tested.

## 2. Observed Junction style and the Morph adaptation

The following exact tokens were read from the site's served stylesheet. They are a dated observation of that page, not requirements for our product:

| Observed Junction implementation | Value |
| --- | --- |
| Main background | `--bg: #1b1710` |
| Secondary background | `--bg-2: #262216` |
| Sand | `--sand: #ead5a5` |
| Parchment / cream | `#e0d8be` |
| Hero background | `#05050a` |
| Main type | Titillium Web |
| Display type | Inter |
| Monospaced type | Space Mono |

Morph's **neutral black background, muted bronze identity, quiet line drawing, and restrained operational green** are our design interpretation of the reference and the owner's requests. Do not describe the Morph palette as Junction's official palette. A green computer-vision box in an image is not evidence of a required official green design token.

For Morph, the strongest connection is the relationship between careful observation and useful action. Express it through a precise drawing, a small orbital motif, measured spacing, and a calm type hierarchy. The visual layer should help the interface feel considered while allowing the actual brick, selected task, and outcome to remain dominant.

## 3. What to keep and improve from the supplied Stitch images

The supplied screenshots are the owner's visual references. Their generated numerical captions and hardware claims were not verified by the screenshots.

| Reference idea | Keep | Improve for the final dashboard |
| --- | --- | --- |
| Black technical interface | Strong contrast and an intentional dark atmosphere. | Use neutral black/charcoal surfaces consistently. Avoid the blue cast, excessive panel levels, and glowing outlines. |
| Morph identity | A memorable name and a geometric `M`. | Use one readable wordmark in the sidebar or masthead. Reduce tiny subtitles, repeated project names, and invented version badges. |
| Renaissance graphic at the top | A distinctive but quiet identity layer. | Keep the artwork above the operational content, with a modest height. Avoid technical-sounding decorative telemetry. |
| Copernicus sketch | A human, scientific connection to the event theme. | Use a low-emphasis crop or engraving in the brand area. Remove the large independent portrait card beside the camera. |
| Camera as the largest panel | Immediate understanding of the current object. | Show the real robot workspace and brick. Keep the exact analyzed snapshot separate from the changing stream. |
| Large red stop control | Easy recognition and reach. | Name the implemented action `Stop process` or `Software stop`; show its actual acknowledgment state. A web control does not prove physical emergency-stop hardware. |
| Left navigation | Stable access to three related views. | Use clear names: `Live inspection`, `Robot & system`, and `Quality & history`. Keep the stop control available in every view. |
| Large numerical summaries | Quick assessment of the run. | Use a small number of meaningful metrics with visible counts and denominators. No invented forces, FPS, heartbeat bpm, or optimization claims. |
| Technical overlays | A useful connection between an object and an observation. | Draw only recorded overlays linked to the displayed frame. Keep labels outside the object where possible and make anomaly overlays optional. |
| Pipeline | An understandable current stage. | Reflect the selected Duplo workflow and preserve the distinction between a command, an execution, and verified physical outcome. |

Do not use Renaissance paintings as pretend camera feeds or decorate a portrait with `J2000`, calibration accuracy, controller synchronization, or other labels that imply measurements. Decorative art should be marked as such in the asset inventory and hidden from the accessibility tree when it communicates no operational information.

## 4. Copernicus engraving asset

Preferred source: [Wellcome Collection, record 2075i](https://wellcomecollection.org/works/n6ut6uxr).

Suggested asset credit:

> Nicolaus Copernicus. Engraving by E. Scriven. Wellcome Collection. Public Domain Mark.

The source record links a [760-pixel JPEG](https://iiif.wellcomecollection.org/image/V0001271EL/full/760,/0/default.jpg). This is an existing historical engraving, not a newly generated portrait or a photograph. Retain the source URL and credit in the asset metadata even when the UI does not display a caption.

Suggested Morph treatment is a crop, neutralization of the paper, gentle bronze recoloring, and reduced opacity on a black masthead. Preserve recognizable line work; avoid turning the portrait into a bright parchment rectangle that competes with the camera. Any final asset should be visually checked at the actual display size. A header treatment is decorative and should not carry scene evidence, control state, or essential instructions.

An alternative line engraving is available in [Wellcome record m5d3chbs](https://wellcomecollection.org/works/m5d3chbs). It was identified during the earlier research pass; the preferred Scriven record above was independently rechecked for this handoff.

## 5. Applying the package in Google AI Studio

The current Google documentation supports creating a web app from a prompt, inspecting its generated files in the Code view, and refining the UI through chat or annotation. React is the documented default frontend. ZIP export and GitHub synchronization provide a route to continue work with the team. These are tool capabilities; they do not establish Morph's hardware connectivity.

Recommended handoff procedure:

1. Use this package's screen images as composition references and its design tokens as the styling source of truth. Supply the project requirements and prepared build prompt together so the builder has both the visual target and the functional constraints.
2. Build the three views against the proposed simulation adapter. Keep every fixture clearly labeled `Simulation`; do not make provider badges look verified merely because the layout is complete.
3. Inspect the generated components, state handling, accessibility, and responsive layout. Compare the camera, current-object, voice, stop, and result states with the reference screens.
4. Export the code or synchronize it to the team's repository. Implement the actual station integration through [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).
5. Add provider credentials only through the selected server's secret configuration. Google documents a server-side secret facility; the deployed Intel application needs its own equivalent environment configuration.
6. Verify the actual intended model IDs and account access before marking an integration active. Using Gemini to build the interface does not satisfy Morph's requirement to use Gemini for online product decisions.

The proposed production boundary is a local station application that owns persisted records and validated dispatch. Building or hosting a frontend in AI Studio does not, by itself, connect to the Intel machine's USB devices, private network, or local robot runtime. Treat any cloud-to-station bridge as explicit implementation work.

## 6. Verification boundaries

- The official event page, its referenced CSS, the preferred Wellcome record, and the two Google documentation pages were read on November 14, 2026.
- Junction page and CSS observations are source inspection. The user's supplied screenshots are the direct evidence for their requested Morph direction.
- No user Safari window was opened, navigated, or changed for this research.
- No remote service account, API key, model entitlement, deployment, camera, or robot was tested.
- Refer to the dated audit for current project implementation status. Design references and synthetic examples must never become evidence of physical reliability or model performance.
