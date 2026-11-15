# Morph asset inventory

**Prepared November 14, 2026.** All files in this package are local. No CDN is needed to open the reference. Original graphics are design proposals for this project; the robot scene is an illustration, not a hardware photograph or calibration diagram.

| File | Origin | Intended use |
| --- | --- | --- |
| [morph-mark.svg](assets/morph-mark.svg) | Original articulated-M drawing authored for Morph | App mark, favicon, wordmark companion; editable vector |
| [morph-wordmark.png](assets/morph-wordmark.png) | Original transparent Morph lockup, drawn with the included Inter font | Portable raster wordmark; use the SVG mark plus live text in the app |
| [orbital.svg](assets/orbital.svg) | Original decorative Copernican orbital study | Subtle masthead; no measured coordinates or calibration meaning |
| [inspection-scene.svg](assets/inspection-scene.svg) | Original schematic illustration of a robot/brick sorting fixture | Explicitly labeled simulation only; replace with real camera media in live operation |
| [copernicus-scriven.jpg](assets/copernicus-scriven.jpg) | Historical engraving, Wellcome Collection, Public Domain Mark | Decorative low-opacity masthead crop; preserve attribution below |
| [inter.ttf](assets/inter.ttf) | Google Fonts source repository | Inter interface font |
| [space-mono.ttf](assets/space-mono.ttf) | Google Fonts source repository | Space Mono technical font |
| [cormorant-italic.ttf](assets/cormorant-italic.ttf) | Google Fonts source repository | Cormorant Garamond Italic accent font |

## Historical engraving attribution

**Nicolaus Copernicus. Engraving by E. Scriven. Wellcome Collection. Public Domain Mark.**

- Record: <https://wellcomecollection.org/works/n6ut6uxr>
- Downloaded source: <https://iiif.wellcomecollection.org/image/V0001271EL/full/760,/0/default.jpg>
- The supplied JPEG retains the historical original. Cropping, grayscale/sepia styling, masking and opacity are applied in CSS.

The portrait was not created by image generation. The UI references are browser-rendered screenshots of the supplied code. No generative image API was used; the logo, orbital drawing and scene remain editable SVG assets.

## Font provenance and licenses

Sources were downloaded from the Google Fonts repository on November 14, 2026:

- Inter: <https://github.com/google/fonts/tree/main/ofl/inter>; [bundled license](assets/inter-OFL.txt).
- Space Mono: <https://github.com/google/fonts/tree/main/ofl/spacemono>; [bundled license](assets/spacemono-OFL.txt).
- Cormorant Garamond: <https://github.com/google/fonts/tree/main/ofl/cormorantgaramond>; [bundled license](assets/cormorantgaramond-OFL.txt).

Keep the corresponding SIL Open Font License notices with the font files. The exact downloaded files are the reproducible source for this handoff; `main` links may change later.

## Exported references

The `references/` PNGs are exported from [index.html](index.html) at a 1600 CSS-pixel desktop width and a 2× device scale. Mobile is 390 CSS pixels wide. Full-page images have varying heights; dialog captures use a desktop viewport to avoid showing an undimmed page below the modal backdrop. Animation is disabled during export through the reduced-motion preference.

[tools/render-references.cjs](tools/render-references.cjs) rebuilds the screenshots with Playwright and a locally available Chrome/Chromium executable. It also performs a small interaction check. The render script's local default is the Chrome installation used in this workspace; use `MORPH_BROWSER_EXECUTABLE` on another machine.
