# DESIGN.md — Visual & UI Rules

Read this before writing or changing any UI. These rules are mandatory. Goal: a spotless, fluid, simple site that looks designed by a person, not generated. The "AI look" is the absence of decisions; every rule below forces one. When unsure, choose the plainer option.

Final check for every screen: if someone would immediately guess an AI made it, keep iterating. Copy check: cover the logo and read the page. If the copy would still work for a competitor, rewrite it.

## 1. Hard bans
- `border-radius` on anything. Every corner is sharp: no pills, rounded cards, avatars or inputs.
- Gradients of any kind (backgrounds, buttons, borders, text). Gradient text / `background-clip: text`.
- Glassmorphism, `backdrop-filter: blur`, frosted panels. Glows, neon, coloured `box-shadow`.
- Soft drop shadows on cards.
- Large icons in coloured circles/squares above headings. Emoji as icons. Sparkles, "AI-powered" or "New" badges.
- Three or four identical feature cards in a row. "Hero metric" blocks with gradient accents.
- Bounce, elastic, spring or overshoot easing. Animating width, height, top, left, margin, padding.
- Fade-in-on-scroll everywhere. Dark glowing default theme. Centering every block of text.
- Cards inside cards. Modals as the default way to show content.
- Lorem ipsum or vague copy ("Unlock your potential", "Seamless experience").
- Removing features on mobile instead of adapting them.

## 2. Typography
Banned as primary fonts: Inter, Roboto, Arial, Open Sans, Poppins, Montserrat, Space Grotesk, Geist, system-ui alone. Monospace only for real code.

| Role | Options |
|---|---|
| Body / UI | IBM Plex Sans, Public Sans, Instrument Sans, Hanken Grotesk, Libre Franklin, Atkinson Hyperlegible |
| Headings | Schibsted Grotesk, Archivo, Familjen Grotesk, Instrument Sans; serif: Source Serif 4, Newsreader |
| Code | IBM Plex Mono, JetBrains Mono |
| Chinese (this project) | fall back to PingFang SC, Microsoft YaHei, Noto Sans SC |

Default pairing: Schibsted Grotesk (headings) + IBM Plex Sans (body). Max 2 families.

- Type scale only: 13 / 14 / 16 / 20 / 28 / 40 / 56 px.
- Body ≥ 16px, line-height 1.55. Headings line-height 1.1–1.2, letter-spacing -0.02em at ≥ 28px.
- Max 3 weights (400, 500, 600). Paragraphs `max-width: 65ch`.
- Emphasis = weight or colour. `text-wrap: balance` on headings, `pretty` on paragraphs.
- Max 2 font files, `font-display: swap`.

## 3. Shape & surfaces
- Global reset: `*, *::before, *::after { border-radius: 0 !important; }`
- Separate with 1px lines, not shadows. Only add a container when it is needed. Never nest bordered boxes.
- Depth, if needed: a solid unblurred offset (`box-shadow: 4px 4px 0 var(--fg)`) on one or two key elements.
- Icons: Lucide/Phosphor style, 1.5px stroke, 16–20px, text colour, no background tiles.
- Images: sharp corners, fixed size or `aspect-ratio`.

## 4. Colour
- Design in grayscale first. One accent, used only for primary actions, links, focus, key states.
- No pure `#000` / `#fff`; tint neutrals. Contrast: body ≥ 4.5:1, large text and UI borders ≥ 3:1.
- Light theme is default; a dark theme must be designed on purpose, with no glows.

```css
:root { --bg:#FAFAF7; --surface:#F2F1EC; --fg:#121211; --muted:#5B5B57; --line:#D9D8D2;
        --accent:#1F4FFF; --accent-fg:#FAFAF7; --danger:#B42318; }
```

## 5. Layout & spacing
- Spacing scale (4px base): 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128.
- Tight inside groups (8–16), generous between sections. Never uniform spacing.
- Left-align by default. 12-column grid, ~1200px max, 24px gutters. Prefer 7/5 or 8/4 over 6/6.
- Vary weight: one large item plus smaller ones, or a plain list with dividers. Say each thing once.

## 6. Motion
- Animate only `transform` and `opacity` (plus colours on hover).
- Easing `cubic-bezier(0.2, 0, 0, 1)`. Hover/press 120–180ms; panels 200–300ms; nothing over 400ms.
- At most one meaningful motion moment per page. Respect `prefers-reduced-motion`.
- Prefer inline expansion or slide-out panels over modals.

## 7. Buttons, inputs, interaction
- One primary (solid) button per view; secondary = outlined; tertiary = text link.
- Buttons, inputs, selects all 44px tall (40px dense). Hit area ≥ 44×44px.
- Hover: invert fill ↔ outline. Press: `translateY(1px)`.
- Focus: `outline: 2px solid var(--accent); outline-offset: 2px` on `:focus-visible`. Never remove it.
- Links underlined, `text-underline-offset: 3px`, 1px thickness.
- Inputs: 1px border, label above, error text below in `--danger`. Disabled: lower contrast, `not-allowed`. Loading: short text, stable width.

## 8. Content
- Headlines say something specific: a real number, name or concrete claim.
- Show the real product. Real photos and names. Specifics: numbers, dates, versions.
- Plain short sentences. No "seamless", "revolutionary", "unlock", "elevate", "supercharge".

## 9. Performance & code
- Minimal JavaScript; HTML-first. Semantic HTML, no clickable `<div>`s.
- Images have size, `alt`, and `loading="lazy"` below the fold. No layout shift.
- Colours, spacing and fonts come from CSS variables.
- Mobile-first; test at 375 / 768 / 1280 / 1600px, keeping every feature.

## 10. Review checklist (run before finishing any UI task)
- [ ] Zero rounded corners (grep `rounded`, `border-radius`).
- [ ] Zero gradients, blurs, glows, soft shadows (grep `gradient`, `blur`, `shadow`).
- [ ] No banned fonts; max 2 families, max 3 weights.
- [ ] Only scale values for font sizes and spacing.
- [ ] Exactly one primary button per view.
- [ ] Text left-aligned; paragraphs ≤ 65ch.
- [ ] No identical card grids, nested boxes, icon-in-circle headings.
- [ ] Motion: transform/opacity only, ≤ 300ms, smooth easing, reduced motion respected.
- [ ] Contrast passes. Visible focus. Targets ≥ 44px.
- [ ] Copy passes the cover-the-logo test.
- [ ] Works at 375px with nothing removed.
- [ ] Would someone guess an AI made this? If yes, keep going.

References: pbakaus/impeccable, kamranahmedse/awesome-minimal-sites, eliancodes/brutal, GOV.UK Design System.
