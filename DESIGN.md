---
name: अधिKaar (AdhiKaar)
description: A local-first legal assistant that explains Indian citizens' rights in 11 languages, built to be read aloud.
colors:
  indigo-deep: "#4338CA"
  indigo-dark: "#3730A3"
  indigo-darker: "#312E81"
  indigo-light: "#6366F1"
  indigo-subtle: "#E0E7FF"
  indigo-wash: "#EEF2FF"
  turmeric: "#F59E0B"
  turmeric-dark: "#D97706"
  turmeric-wash: "#FEF3C7"
  bone: "#FAF9F6"
  bone-surface: "#FFFFFF"
  bone-input: "#F4F2ED"
  bone-hover: "#F0EEE8"
  ink: "#1C1917"
  ink-muted: "#57534E"
  ink-faint: "#746D68"
  border: "#E9E6E0"
  border-strong: "#D8D4CC"
  success: "#10B981"
  warning: "#F59E0B"
  danger: "#EF4444"
  info: "#3B82F6"
  on-primary: "#FFFFFF"
  primary-ink: "#3730A3"
  accent-ink: "#451A03"
  danger-ink: "#991B1B"
  success-ink: "#065F46"
  warning-ink: "#78350F"
  info-ink: "#1E40AF"
typography:
  display:
    fontFamily: "Noto Sans, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "clamp(2rem, 5vw, 3.5rem)"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "normal"
  headline:
    fontFamily: "Noto Sans, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Noto Sans, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Noto Sans, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Noto Sans, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    letterSpacing: "0.05em"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
  full: "9999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
  2xl: "3rem"
components:
  button-primary:
    backgroundColor: "linear-gradient(135deg, {colors.indigo-deep}, {colors.indigo-dark})"
    textColor: "{colors.on-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "14px 28px"
    height: "52px"
  button-secondary:
    backgroundColor: "{colors.bone-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "14px 28px"
    height: "52px"
  button-secondary-hover:
    backgroundColor: "{colors.indigo-wash}"
    textColor: "{colors.indigo-dark}"
  button-accent:
    backgroundColor: "linear-gradient(135deg, {colors.turmeric}, {colors.turmeric-dark})"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.md}"
    padding: "14px 28px"
    height: "52px"
  button-danger:
    backgroundColor: "#FEE2E2"
    textColor: "{colors.danger-ink}"
    rounded: "{rounded.md}"
  button-icon:
    rounded: "{rounded.full}"
    width: "48px"
    height: "48px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "14px 16px"
    height: "52px"
  nav-item-active:
    backgroundColor: "{colors.indigo-wash}"
    textColor: "{colors.indigo-dark}"
  input-field:
    backgroundColor: "{colors.bone-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
---

# Design System: अधिKaar (AdhiKaar)

## 1. Overview

**Creative North Star: "The Patient Clerk's Desk"**

This is the counter of someone who knows every form, has all day, and will not make you feel stupid for asking. The system is orderly without being bureaucratic. Warm paper under dark ink, one official-blue stamp, a marigold-yellow tab for the thing that needs attention today. Nothing on the desk is there to impress; everything on it is there because a person in trouble needed it within reach.

The interface is operated by a helper — an NGO worker, a paralegal, a panchayat elder — with the person whose case it is sitting beside them. That single fact governs the visual system more than any other. Type is large because it is read across a desk and out loud. Contrast is high because the desk might be outdoors. Components are quiet because the legal content is the only thing on screen that deserves attention. The system is bilingual at the type level, not as an afterthought: Devanagari and Latin sit in the same family and the same optical size.

It explicitly rejects three things. It is not a **government portal** — no dense blue tables, no Times New Roman, no marquee notices, no hierarchy you must already understand to navigate; the users may be in conflict with an institution and the interface must not wear that institution's uniform. It is not a **ChatGPT wrapper** — no bare chat box and blinking cursor as the whole product, no generic assistant chrome. It is not an **NGO charity brochure** — no stock photography of hopeful faces, no soft-focus warmth, no donation-appeal tone; the user is a holder of rights, not an object of pity.

**Key Characteristics:**
- Paper-warm neutrals (Bone `#FAF9F6`) rather than cold gray, with a full dark theme at parity
- A single type family (Noto Sans + Noto Sans Devanagari) carrying all 11 languages
- 1.125rem body as the *floor*, not a large-text option
- 52px minimum interactive height everywhere — thumbs, sunlight, shaky hands
- Restrained accent use: indigo means action or location, turmeric means attention
- Ambient elevation — shadows soften, they don't stack-rank

## 2. Colors

A paper-and-ink palette with two civic pigments: an official indigo for authority the user *borrows*, and a turmeric yellow for what needs attention now.

### Primary
- **Deep Indigo** (`#4338CA`): The stamp. Used for primary actions, the active navigation item, focus rings, and links — the color of "this is the thing to press" and "you are here." Never decorative. Its darker steps (`#3730A3`, `#312E81`) carry hover states and text-on-wash; `#6366F1` is the light step used inside gradients and in the dark theme's primary role.
- **Indigo Wash** (`#EEF2FF`) and **Indigo Subtle** (`#E0E7FF`): The tint the stamp leaves. Backs the active nav item, secondary-button hover, and informational surfaces. Carries indigo's meaning without indigo's weight.

### Secondary
- **Turmeric** (`#F59E0B`): Attention, deadlines, and warning states. The accent CTA. Doubles as `--warning` deliberately — in this product, "notice this" and "this is a risk" are the same signal. `#D97706` is the hover step; **Turmeric Wash** (`#FEF3C7`) backs warning banners.

### Neutral
- **Bone** (`#FAF9F6`): The body surface. Unbleached paper, not cream-by-default — it is warm because ink on true white is harsh under bright light, not because warmth is a brand adjective.
- **Bone Surface** (`#FFFFFF`): Cards, sidebar, modals. The sheet on the desk, one step above the desk itself.
- **Bone Input** (`#F4F2ED`) / **Bone Hover** (`#F0EEE8`): The recessed and touched states of the neutral layer.
- **Ink** (`#1C1917`): Body text. Near-black with a warm cast so it sits on Bone as ink sits on paper.
- **Ink Muted** (`#57534E`): Secondary text, labels, inactive navigation. 6.82:1 at its worst.
- **Ink Faint** (`#746D68`): Placeholders, metadata, timestamps, empty-state text. The lightest step on this hue that still clears 4.5:1 on Bone, Bone Surface *and* Bone Input. It was `#A8A29E` (2.25:1) and carried every placeholder in the app.
- **Border** (`#E9E6E0`) / **Border Strong** (`#D8D4CC`): Hairlines and emphasized dividers. 1–1.5px only.

### Tertiary
- **Success** `#10B981`, **Danger** `#EF4444`, **Info** `#3B82F6`: Semantic states only. Never brand, never decoration. Each is a **wash**, never a label — see the Ink Rule.

### Inks
Every coloured surface has a matching ink. The semantic hue is never legible on its own wash, and `--primary` inverts between themes, so a hard-coded `white` label breaks the moment the theme flips.

- **On Primary** (`#FFFFFF` light / `#1E1B4B` dark): The label on any primary-gradient surface — buttons, send button, user message bubbles, active toggles, the logo tile.
- **Primary Ink** (`#3730A3` light / `#C7D2FE` dark): Text on Indigo Wash / Indigo Subtle.
- **Accent Ink** (`#451A03`, both themes): The label on turmeric. `--accent` is not re-themed, so neither is its ink.
- **Danger Ink** (`#991B1B` / `#FCA5A5`), **Success Ink** (`#065F46` / `#6EE7B7`), **Warning Ink** (`#78350F` / `#FCD34D`), **Info Ink** (`#1E40AF` / `#93C5FD`): Text on the matching wash.

### Named Rules

**The Borrowed Authority Rule.** Indigo is the color of the state, used *on the citizen's behalf*. It appears on the action the user is taking, never on the institution being described. An FIR summary, a court notice, a police matter: those render in ink on paper like any other content. The moment indigo decorates institutional content, the interface starts wearing the government's uniform and the anti-reference is live.

**The Two-Signal Rule.** Only two colors mean anything: indigo means *act or you-are-here*, turmeric means *attend to this*. Every other color in the file is either paper, ink, or a semantic state. A third meaningful accent is forbidden.

**The Dark Theme Is Not A Mode Rule.** The dark theme is a full palette inversion at role parity, not a dimmed variant. It exists because this tool gets used at night in rooms without good light. Every new token added to `:root` must ship its dark counterpart in the same commit.

**The Ink Rule.** A colour that is a background is never also a label. Every coloured surface pairs with a declared `*-ink` token, and text on that surface uses the ink — never `white`, never the semantic hue itself. The reason is mechanical: `--primary` is a dark indigo in light mode and a pale lavender in dark, so `color: white` on a primary surface silently drops to 2.98:1 the moment someone toggles the theme. If you are writing `color: white` or `color: var(--danger)` on top of a `background`, you want an ink token instead.

## 3. Typography

**Display Font:** Noto Sans (800 weight)
**Body Font:** Noto Sans / Noto Sans Devanagari (300–800)
**Label/Mono Font:** None — deliberately

**Character:** One family, eleven languages, no pairing. Noto exists precisely so Devanagari, Latin, and the regional scripts share a skeleton, an optical size, and a vertical rhythm; pairing a display face against it would break exactly the thing that makes the system work multilingually. Personality here comes from size and weight, never from a second face. The result reads as competent and unadorned — the clerk's handwriting, not the clerk's letterhead.

### Hierarchy
- **Display** (800, `clamp(2rem, 5vw, 3.5rem)`, 1.15): The home hero only. The single fluid step in the system.
- **Headline** (700, 1.875rem, 1.25): View titles.
- **Title** (700, 1.5rem, 1.2): Section headings, the app name in the sidebar, card headings.
- **Body** (400, 1.125rem, 1.6): All prose, all AI output, all form input. Cap prose at 65–75ch. This is 18px — the floor, not an accessibility toggle.
- **Label** (600, 0.8125rem, 0.05em tracking, uppercase): Form labels and the language selector only.

### Named Rules

**The Read-Aloud Rule.** Every string is a script for a conversation, not a document to be skimmed. If a sentence cannot be read aloud to a distressed person in one breath, it is too long. This is a typographic rule because it decides measure, line-height (1.6, not 1.4), and the ban on dense multi-column prose.

**The Fixed-Scale Rule.** The rem scale is fixed; only `.hero-title` is fluid. Product UI is viewed at consistent DPI and a clamped heading that shrinks inside a panel looks worse, not better. Do not add `clamp()` to any new heading inside the app views.

**The 18px Floor Rule.** `--font-size-base: 1.125rem` is the smallest size prose may ever be. `--font-size-sm` (0.9375rem) and `--font-size-xs` (0.8125rem) are for labels and metadata — never for a sentence a user must understand.

## 4. Elevation

Ambient. Shadows in this system are softness, not structure — they give surfaces a gentle physical presence, like sheets of paper resting on a desk rather than windows floating in z-space. The scale is four steps plus a glow, all low-opacity and widely diffused (`0.04`–`0.08` alpha in light theme, `0.3`–`0.5` in dark, where shadows must work harder against a dark ground). Depth is carried as much by the Bone→White tonal step between desk and sheet as by the shadows themselves.

### Shadow Vocabulary
- **`--shadow-sm`** (`0 1px 2px rgba(0,0,0,0.05)`): The sidebar, and anything that is merely *not flush*.
- **`--shadow-md`** (`0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)`): Buttons and cards at rest.
- **`--shadow-lg`** (`0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04)`): Hover response.
- **`--shadow-xl`** (`0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04)`): Modals and the kiosk overlay.
- **`--shadow-glow`** (`0 0 20px rgba(67,56,202,0.15)`): Indigo bloom under primary actions on hover only.

### Named Rules

**The Soft-Light Rule.** No shadow in this system exceeds `0.08` alpha in light theme. If a shadow reads as a hard edge or a dark band, it is wrong — the light source is a room, not a spotlight. A shadow you can *see* rather than merely feel is a bug.

## 5. Components

Steady and unfussy. Components recede so the legal content carries the screen; nothing draws attention to itself. They are sized for a thumb in sunlight and quiet in every other respect.

### Buttons
- **Shape:** Softly rounded (`0.75rem` / `--radius-md`), 52px minimum height, `14px 28px` padding.
- **Primary:** Indigo gradient (`135deg`, `#4338CA` → `#3730A3`), white text, `--shadow-md` at rest. The gradient is inherited, not doctrine — see Don'ts.
- **Hover / Focus:** `translateY(-2px)` with `--shadow-lg` plus indigo glow; returns to `0` on `:active`. Transitions run 0.2s.
- **Secondary:** White surface, ink text, 1.5px border. Hover shifts border and text to indigo and the background to Indigo Wash.
- **Accent:** Turmeric gradient. Reserved for the one action that is time-sensitive on a given screen.
- **Danger:** Danger wash background, danger text, 1px danger border. Never a gradient — destructive actions must not look pressable-and-fun.
- **Small** (`.btn-sm`, 40px) is permitted only in toolbars and card footers, never as a primary path.
- **Icon** (`.btn-icon`, 48px circle): Voice, theme toggle, close.

### Cards / Containers
- **Corner Style:** `1rem` (`--radius-lg`) for content cards, `1.25rem` for feature surfaces.
- **Background:** Bone Surface (`#FFFFFF`) on the Bone desk.
- **Shadow Strategy:** `--shadow-md` at rest, `--shadow-lg` on hover for interactive cards only. Static cards do not respond.
- **Border:** 1px `--border` hairline. Full borders only.
- **Internal Padding:** `--space-lg` (1.5rem) standard.

### Inputs / Fields
- **Style:** 1.5px `--border` stroke, `--radius-sm`, Bone Surface or Bone Input ground, body-size text (1.125rem — inputs are prose).
- **Focus:** Border shifts to Deep Indigo plus a 3px `rgba(67,56,202,0.12)` ring. The ring is the accessibility contract; it is never removed, only restyled.
- **Chat input:** `:focus-within` on the wrapper, not the textarea — the whole composer lights up as one object.
- **Placeholder:** Currently Ink Faint. Non-compliant; see Don'ts.

### Navigation
- **Style:** 280px fixed sidebar on the Bone Surface layer, hairline right border, `--shadow-sm`. Items are 52px, `--radius-md`, Ink Muted at rest.
- **Hover:** Bone Hover background, Ink text.
- **Active:** Indigo Wash background, Indigo Dark text, weight 500 → 600. The weight shift matters — color alone must not carry state.
- **Mobile:** Collapses below 900px.

### Kiosk Overlay (signature)
A fullscreen voice-first surface with one large central microphone. It is the system's only drenched moment and the only place where a component is allowed to dominate the screen — because at that moment the component *is* the interface. Everything else recedes to nothing.

## 6. Do's and Don'ts

### Do:
- **Do** use `--font-size-base` (1.125rem) as the smallest size any sentence is ever set in. Labels may go smaller; prose may not.
- **Do** give every interactive element a 52px minimum touch height. The design target is a thumb in sunlight, not a mouse.
- **Do** ship a dark-theme counterpart in the same commit as any new `:root` token. The dark palette (`style.css:1963`) is at role parity and must stay that way.
- **Do** carry state with weight or shape in addition to color — the active nav item shifts 500 → 600, not just indigo.
- **Do** keep indigo on the user's action and off the institution's content. **The Borrowed Authority Rule.**
- **Do** self-host Noto. `style.css:7` currently `@import`s from `fonts.googleapis.com`, which contradicts "legal help that never leaves the device" and blocks first render on exactly the patchy connections this product targets.
- **Do** name transitions by property. `--transition: all 0.2s ease` animates `all`, which invites layout thrash; prefer `transform 0.2s, box-shadow 0.2s`.

### Don't:
- **Don't** make it look like **a government portal**: no dense tables, no Times New Roman, no marquee notices, no hierarchy that assumes you already know the process.
- **Don't** make it look like **a ChatGPT wrapper**: no bare chat box as the whole product, no generic assistant chrome, no regenerate-button furniture.
- **Don't** make it look like **an NGO charity brochure**: no stock photography of hopeful faces, no soft-focus warmth, no donation-appeal tone. The user holds rights; they are not receiving a favour.
- **Don't** put `color: white` on any surface painted with `--primary`. It is 7.90:1 in light mode and **2.98:1 in dark**, because the dark theme flips primary to a pale lavender. Use `--on-primary`. **The Ink Rule.**
- **Don't** set text in a semantic hue on that hue's own wash (`--danger` on `--danger-bg` is 3.08:1, `--success` on `--success-bg` is 2.24:1). Use the matching `*-ink` token.
- **Don't** ship gradient text. `.hero-title .highlight` (`style.css:355`) uses `background-clip: text` with an indigo gradient. It is decorative, it degrades in high-contrast modes, and it is the one element on the home view that reads as a startup rather than a clerk. Solid `--primary`; emphasis via weight.
- **Don't** extend the button gradient to new surfaces. It is grandfathered on primary and accent buttons only. Cards, headers, badges, and panels are flat fills — **The Soft-Light Rule** governs depth, gradients don't.
- **Don't** use a colored `border-left`/`border-right` over 1px as an accent stripe on advisories, cards, or callouts. The Protective Advisory is a full-bordered turmeric-wash surface, not a stripe.
- **Don't** add `clamp()` to headings inside app views. **The Fixed-Scale Rule** — the hero is the only fluid step.
- **Don't** introduce a third meaningful accent color. **The Two-Signal Rule.**
- **Don't** put a display face next to Noto. One family carries eleven languages; a pairing breaks the multilingual skeleton that makes the system work.
