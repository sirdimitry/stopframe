# StopFrame artwork

Generated using the built-in `image_gen` tool (not the API/CLI fallback). Source outputs are retained under the generating Codex session's `generated_images` directory; all shipping assets are copied into this repository.

Files:

- `assets/branding/app-icon.png`: original generated transparent icon.
- `assets/branding/StopFrame.icns`: iconset conversion via macOS `sips` and `iconutil` in the build script.
- `assets/branding/banner.png`: generated banner displayed in About.
- `docs/branding/readme-banner.png`: same artwork for GitHub's relative image link.
- `assets/branding/dmg-background.png`: generated DMG artwork resized to its 720 × 460 Finder window with `sips`.

## Icon prompt

Use case: logo-brand. Create a final production macOS app icon for StopFrame, a local tool that extracts the best still frames from video. Square 1024x1024 PNG with genuine transparent background outside the icon. One large macOS rounded-square squircle tile centered, occupying about 86% of canvas, bright saturated coral-orange (#F36B3F) with a subtle warm amber top-left to coral bottom-right gradient. Inside: an exceptionally simple bold ivory-white landscape picture-frame outline with softly rounded corners; in its center two bold vertical pause bars, a tiny four-point sparkle at the frame's upper-right corner indicates a perfect captured still. Clear silhouette, high legibility at 32px, crisp geometrical precise shapes, minimal flat premium macOS aesthetic, just a little depth on the orange tile, no busy ornamentation. No words, no letters, no camera lens, no film perforations, no surrounding presentation, no ground plane. This is the actual icon asset, not a mockup.

## Banner prompt

Use case: ads-marketing. Create a final clean wide 3:1 banner image for the StopFrame macOS app README and About panel. Use the supplied icon as the brand reference, preserve its recognizable coral orange rounded-square tile, ivory image frame with pause bars and sparkle. Graphite near-black #101113 background with restrained soft coral ambient glow only on the right. On the left: exact large beautifully typeset ivory title 'StopFrame', under it exact smaller muted ivory line 'Find the frame worth keeping.' Under that, a quiet small uppercase line 'SHARP FRAMES. LESS REPETITION. ALL LOCAL.' Large elegant typographic hierarchy and lots of clear space. On the right the referenced app icon occupies about half the height, front-facing, surrounded behind by only two thin coral landscape frame outlines subtly offset, suggesting frames extracted from a timeline. Minimal premium product identity, bright coral focus, crisp editorial typography, no screenshots, no people, no extra marks, no version numbers, no author credit. Banner should be immediately usable as a 1800x600 header and readable scaled down.

Final cleanup prompt: Precise cleanup of this banner. Preserve its exact layout, colors, icon, dimensions, typography and all three text lines. Remove the small stray white specks/artifacts immediately below and overlapping the word 'Find' at the left end of the subtitle, restoring the clean graphite background there. Make the subtitle read crisply and exactly 'Find the frame worth keeping.' with no stray marks or specks around it. Do not add any new content; keep everything else unchanged.

## DMG background prompt

Use case: ui-mockup. Asset type: actual background wallpaper for a macOS DMG installer window, not a screenshot or mockup. Create a clean premium 1440x920 landscape graphic (aspect ratio 36:23), matte very dark graphite #101113, matching a bright coral-orange macOS app called StopFrame. Top left with 110px margins: exact ivory title 'StopFrame', about 78px tall, below exact light gray subtitle 'Your best frames. One drag away.' 28px. Top right only a small subtle coral outline of a landscape photo frame and tiny sparkle. Center area from y=280 to y=660 MUST be nearly empty and dark: two actual Finder icons will be placed on top later at x=400,y=480 and x=1040,y=480; DO NOT draw icons, circles, boxes, slots or text under those icon positions. Only draw a clean coral right-pointing arrow from x=650 to x=800 at y=480, indicating drag-to-install. Bottom center at y=760 exact text 'Drag StopFrame into Applications' in ivory sans-serif 30px. At y=825 much smaller muted text 'LOCAL BY DESIGN'. Restrained subtle warm coral glow at lower corners, generous negative space, flat precise typography, no fake window chrome, no cursor, no app icon, no folder icon, no version number.


Final DMG contrast edit: Preserve all existing artwork, text, arrow, layout and background. Add two empty pale warm peach (#F5C8AF) rounded capsules behind the Finder filename positions, centered near x=27.78% and x=72.22%, y=65%, about 18% of canvas wide and 6.5% high. No text or icons in the capsules. Actual Finder icon locations are aligned in `packaging/dmg_settings.py`. The result is exported at 1× and 2× for Retina Finder windows.
