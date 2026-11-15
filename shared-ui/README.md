# Morph shared chat style

Version 1.0 · November 15, 2026. A plain CSS handoff for Jose's chat interface, aligned with Klemen's current dashboard. No React, Tailwind, package installation or JavaScript is required. This package adds a style reference; it does not modify either running application or establish chat/robot integration.

**Send the ZIP for the complete visual match.** `morph-chat.css` is the main style file. The included `fonts/` directory supplies the same fonts as the dashboard; system fallbacks work if only the CSS is copied. `assets/` contains the existing Morph mark and orbital graphic. Font licenses are preserved beside the fonts. `preview.html` is a static example that can be opened directly in a browser.

## Include it

Keep these paths together when copying to a public/static asset directory:

```text
morph-chat.css
fonts/
assets/
```

```html
<link rel="stylesheet" href="/morph/morph-chat.css">

<main class="morph-theme">
  <section class="morph-conversation" aria-labelledby="chat-title">
    <header>
      <span class="morph-eyebrow">Morph / operator workspace</span>
      <h1 class="morph-title" id="chat-title">Your next instruction<em>.</em></h1>
    </header>
    <article class="morph-message">
      <div class="morph-avatar" aria-hidden="true">M</div>
      <div class="morph-message-content">
        <div class="morph-message-meta"><span class="morph-message-author">Morph</span></div>
        <div class="morph-message-body"><p>Message text from your application.</p></div>
      </div>
    </article>
    <div class="morph-composer">
      <label class="morph-sr-only" for="message">Message to Morph</label>
      <textarea class="morph-textarea" id="message" placeholder="Describe the next task..."></textarea>
      <div class="morph-composer-toolbar">
        <span class="morph-composer-hint">Review the proposed action before sending.</span>
        <button class="morph-button morph-button--primary" type="button">Send message</button>
      </div>
    </div>
  </section>
</main>
```

For React, import the CSS through the app's asset pipeline and use `className` instead of `class`. Preserve the relative font URLs when bundling. Apply `.morph-theme` to the outer wrapper or `<body>`; tokens and components are scoped to that wrapper. Each bundled font uses a `Morph`-prefixed family name to avoid overriding another application's font registration. No external CDN is used.

## Visual contract

| Element | Shared value / rule |
| --- | --- |
| Canvas / panel / raised | `#080808` / `#101010` / `#171715` |
| Border / main text / muted text | `#252421` / `#F2EEE6` / `#A7A39A` |
| Bronze / success / warning / error | `#C7A477` / `#91B99C` / `#D6B775` / `#E36363` |
| Body and controls | Inter, 14px base; chat messages have a 1.7 line-height |
| IDs, timestamps, model names, measured values | Space Mono, tabular numerals |
| Short masthead accent only | Italic Cormorant Garamond |
| Corners | Panels/messages 9px; controls 5px; badges 4px |
| Spacing | 4, 8, 12, 16, 20, 24, 32px tokens; panel headers use dashboard geometry |
| Primary action | Bronze fill and dark text; one main action per group |
| Motion / focus | Subtle 160ms transitions, visible bronze focus, reduced-motion support |

The chat-specific layout is an adaptation: wider reading line-height, a composer, distinct operator/assistant surfaces, 40px controls (44px on narrow screens), a 212px sidebar and an optional 280px context column. It is not a second copy of dashboard layout rules. Keep the palette, fonts and restrained geometry consistent when adapting to Jose's application.

## Component map

| Class | Use |
| --- | --- |
| `.morph-theme` | Required token and style scope |
| `.morph-shell`, `.morph-sidebar`, `.morph-main` | Optional application frame |
| `.morph-masthead`, `.morph-topbar` | Brand line and real connection/session state |
| `.morph-chat-layout`, `.morph-conversation`, `.morph-context` | Responsive conversation and context columns |
| `.morph-message`, `.morph-message--operator`, `.morph-message--system` | Assistant, operator and neutral system entries |
| `.morph-message-meta`, `.morph-message-body`, `.morph-message-actions` | Message provenance, content and secondary actions |
| `.morph-composer`, `.morph-textarea`, `.morph-composer-toolbar` | Message entry area |
| `.morph-button` with `--primary`, `--outline`, `--ghost`, `--danger`, `--icon` | Controls; modifier classes must accompany the base class |
| `.morph-status` with `--success`, `--warning`, `--error`, `--bronze` | Visible status text; omit modifier for neutral/unavailable |
| `.morph-panel`, `.morph-panel-heading`, `.morph-panel-body` | Context, tool-result and evidence cards |
| `.morph-definition-list`, `.morph-evidence`, `.morph-details` | Actual values, source references and optional disclosures |
| `.morph-field`, `.morph-label`, `.morph-input`, `.morph-select` | Standard labeled form inputs |
| `.morph-typing` with three decorative `<i>` children | Optional response-in-progress visual; supply accessible status text |

Color is always paired with visible text. Proposed, sent, acknowledged, finished and physically confirmed remain distinct. Use success styling for the specific confirmed status named in the label; an assistant response or completed controller command does not establish a successful physical outcome. Missing data stays unavailable. Voice listening and model activity need their actual source status; do not animate them permanently.

CSS only styles state. The app owns authentication, message submission, disabled behavior, keyboard handling, focus restoration and live announcements. Use native `disabled` where applicable; `aria-disabled` alone does not block clicks. Use labeled form controls, `type="button"` for non-submit buttons, `aria-pressed` for toggles, and `aria-current="page"` for selected navigation. For streaming chat, choose announcements that avoid repeatedly reading the full transcript; the example is static and has no live region.

## Provenance and verification

Palette, fonts, badges and surfaces were read from `klemen-dashboard/dashboard/src/index.css` and `src/components/DesignLanguageView.tsx` in the same Morph repository. Assets and font licenses are exact copies of the dashboard's bundled files. Chat layout rules are new. Original package source manifests and the dashboard upgrade inventory remain unchanged.

`STYLE_MANIFEST.json` records original dashboard references and portable-file hashes. The style preview contains only illustrative text; its controls do not send messages or commands. Browser checks cover desktop/narrow layout, local font/assets, focus, native disclosures and stylesheet parsing. This is visual handoff evidence, not proof of Jose integration or physical operation.
