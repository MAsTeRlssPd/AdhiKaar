# Product

## Register

product

## Platform

web

## Users

The person operating AdhiKaar is usually not the person whose rights are at stake. The primary user is an **intermediary**: an NGO worker, paralegal, ASHA worker, or panchayat elder running the tool on behalf of someone sitting next to them. They have higher literacy than the citizen they're helping, they may be doing this for several people in a row, and they are reading the screen out loud as much as reading it themselves. The citizen is co-present and is who the output is ultimately for, but they rarely touch the device.

Context of use is genuinely mixed and no single scene dominates: a budget Android in bright sunlight on a patchy connection, a shared kiosk in a panchayat office with people watching, and a desktop at an aid office with a keyboard and a long session are all real. The interface has to hold up across all three without being optimized for any one of them.

The job: take a messy, half-told situation and turn it into a legal position the helper understands well enough to explain back - to the citizen, to an elder, to a room.

## Product Purpose

AdhiKaar explains Indian citizens' legal rights and options in plain language across 11 languages, running entirely on local infrastructure: Gemma via Ollama for inference, ChromaDB for retrieval over IPC/BNS mappings and rights knowledge, Tesseract.js for OCR in the browser, and localStorage for case files. It covers the chat helper, the IPC↔BNS converter, legal aid lookup, document translation, drafting, case workspaces, the virtual courtroom, and kiosk voice mode.

Success is **comprehension**. A session is worth it when the person can explain their own legal position in their own words. Whether they then act on it is their choice, not the product's scorecard. This is a deliberately narrower bar than "user files the complaint", and it changes what the interface optimizes for: an answer isn't finished when the model stops typing, it's finished when it can be restated.

## Positioning

Legal help that never leaves the device. Local inference, in-browser OCR, cases on disk - the only legal AI a person can use for a domestic violence case, a police matter, or a dispute with their employer without the situation touching anyone's server.

## Brand Personality

Calm, plain-spoken, steady. The voice of someone who has seen this exact situation a hundred times and isn't rattled by it. It never alarms and never postures. Legalese gets translated, not flattened into baby talk - the user is an adult in trouble, not a child. Because a helper is frequently reading screens aloud to a distressed person, the writing has to survive being spoken: short sentences, no nested clauses, no jargon that needs a second explanation.

## Anti-references

Three families are ruled out:

- **The government portal.** Dense blue tables, Times New Roman, marquee notices, unclear hierarchy, forms that assume you already know the process. It inherits institutional distrust by association, which is fatal for a tool whose users may be in conflict with an institution.
- **The ChatGPT wrapper.** A bare chat box and a blinking cursor as the entire product. Generic assistant chrome, message bubbles, regenerate buttons. Signals a thin AI reskin rather than a legal instrument.
- **The NGO charity brochure.** Stock photography of hopeful faces, soft-focus warmth, donation-appeal tone. Casts the user as an object of pity rather than a holder of rights.

## Design Principles

**Privacy you can point at.** The positioning is only real if it's visible at the moment it matters - when a photo of an FIR is uploaded, when a domestic violence situation is typed out. Local-by-architecture is worthless as a claim in a footer.

**Explainable out loud.** The primary user reads the screen to someone else. Every output is a script for a conversation, not a document to be skimmed. If it can't be spoken, it doesn't ship.

**Comprehension is the deliverable.** The session ends when the person can restate their position, not when the response finishes rendering. Interfaces that confirm understanding beat interfaces that emit more text.

**Calm under duress.** The situation arrives urgent; the interface must not add to it. No alarm-red by reflex, no urgency theatre, no countdown pressure. Gravity is carried by clarity.

**Legible at both ends.** Sunlight on a cheap panel and a desk monitor at arm's length are both the design target. Contrast and touch targets are sized for the worse end; density is earned only where the better end is certain.

## Accessibility & Inclusion

No formal WCAG level is committed. Accessibility here is practical and judged case by case: an 18px+ base size, large touch targets, voice-first input and TTS output via the Web Speech API, and 11 languages with Devanagari and regional scripts treated as first-class rather than fallback. The governing constraint is users who may read slowly, or not at all, in any script - which is why voice and iconography carry real load rather than decorating a text UI.
