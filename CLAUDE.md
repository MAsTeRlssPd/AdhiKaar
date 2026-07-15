# AdhiKaar

## Design Context

Read [PRODUCT.md](PRODUCT.md) before changing anything user-facing, and [DESIGN.md](DESIGN.md) before touching `static/style.css` or `static/index.html`.

**Register:** product — design serves the task, not the pitch.
**Platform:** web — vanilla SPA in `static/`, served by Flask at `localhost:5000`. No build step.
**Positioning:** Legal help that never leaves the device. Local Ollama inference, in-browser OCR, cases in localStorage.

The primary user is an **intermediary** (NGO worker, paralegal, panchayat elder) operating the tool for a citizen sitting beside them, reading the screen out loud. Success is comprehension — the person being helped can restate their own legal position — not task completion.

Five principles, expanded in PRODUCT.md: privacy you can point at · explainable out loud · comprehension is the deliverable · calm under duress · legible at both ends.

Anti-references, expanded in DESIGN.md's Don'ts: never a government portal, never a ChatGPT wrapper, never an NGO charity brochure.

Visual system: Deep Indigo `#4338CA` (action / you-are-here), Turmeric `#F59E0B` (attention), Bone `#FAF9F6` paper, Ink `#1C1917`. One type family (Noto Sans + Devanagari) for all 11 languages. 1.125rem body floor, 52px touch minimum, full dark theme at role parity.
