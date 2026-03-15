# Baymax Avatar — Design Spec

**Date:** 2026-03-15
**Status:** Approved

## Overview

A persistent, animated Baymax avatar that lives in the bottom-right corner of every page. It delivers personality quotes and contextual page-aware tips through a speech bubble. Built as a reusable React Context + component pair that can be dropped into any Next.js/React project.

## Goals

- Add charm and personality to the site
- Deliver contextual tips to guide users through the product flow
- Be reusable across other projects with minimal configuration
- Stay unobtrusive — never block content, never demand attention

## Architecture

Two files in `frontend/components/`:

```
BaymaxContext.tsx   — React context, provider, and useBaymax() hook
BaymaxAvatar.tsx    — Visual bubble, animations, speech bubble, tip config
```

**Integration in `layout.tsx`:**
```tsx
<BaymaxProvider>
  <BaymaxAvatar />
  {children}
</BaymaxProvider>
```

Any page or component can call `useBaymax()` to interact with the avatar. Baymax has no knowledge of the rest of the app — it only responds to what is pushed to it.

## Public API (`useBaymax()`)

```ts
say(message: string): void
// Pushes a one-off message into the speech bubble.

setPage(page: string): void
// Tells Baymax which page the user is on.
// Triggers the contextual tip for that page after a 2s delay.

setMood(mood: BaymaxMood): void
// 'idle' | 'happy' | 'thinking' | 'excited'
// Future hook for mood-based visual variation (not implemented in v1).
```

## Visual Design

- **Shape:** 64×64px circle, `overflow: hidden`, `border-radius: 50%`
- **Image:** `/public/baymax.png` as `<img>`, `object-fit: cover`
- **Position:** Fixed, `bottom: 24px`, `right: 24px`, `z-index: 50`
- **Idle animation:** Float + glow pulse (CSS keyframes, 3s loop)
  - Vertical float: `translateY(0)` → `translateY(-8px)` → back
  - Glow: `drop-shadow(0 0 12px rgba(165,180,252,0.35))` at midpoint
- **Cursor:** `pointer` — clicking always does something

## Speech Bubble

**Unified style** (used for both quotes and contextual tips):

```
background:  #0e0e2a
border:      1px solid #4f46e5 (indigo)
border-radius: 14px 14px 4px 14px
padding:     10px 14px
max-width:   220px
position:    above-left of the Baymax bubble
```

**Label:** Small `"Tip"` label in `#818cf8` above the message text (applied to all messages for visual consistency).

**Entry animation:** Scale + fade in (`scale(0.85)` → `scale(1)`, 250ms ease-out).

**Dismissal:**
- Auto-dismisses after 4 seconds
- Clicking the bubble immediately dismisses it

## Interaction Model

### On page load
1. Baymax appears in idle state (float + glow)
2. After 2 seconds, the contextual tip for the current page appears
3. Tip auto-dismisses after 4 seconds → back to idle

### On click
1. A random quote from the pool is shown in the speech bubble
2. Quote auto-dismisses after 4 seconds
3. Clicking the bubble dismisses immediately

### Page-specific tips

| Page key      | Tip text |
|---------------|----------|
| `home`        | "Paste an Amazon URL to analyze a product directly." |
| `preview`     | "I'm scanning products. This may take a moment." |
| `confirm`     | "Select the right product and I'll dig into the reviews." |
| `results`     | "Scroll down to see what customers really think." |
| `url-analysis`| "I'm analyzing reviews and price history for you." |

### Quote pool

- "I am not fast. But I am thorough."
- "On a scale of one to ten, how would you rate your pain?"
- "I will always be there for you."
- "Hairy baby."
- "Your health is my only concern."

## Reusability

To use in another project:

1. Copy `BaymaxContext.tsx` and `BaymaxAvatar.tsx`
2. Wrap root layout with `<BaymaxProvider><BaymaxAvatar />{children}</BaymaxProvider>`
3. Edit the `PAGE_TIPS` config object at the top of `BaymaxAvatar.tsx` with project-specific tips
4. Replace `/public/baymax.png` with the desired avatar image
5. Call `useBaymax().setPage('pagename')` from each page

No external dependencies beyond React and Tailwind (which are already present in any target project using this stack).

## Out of Scope (v1)

- Mood-based visual expressions (different images per mood)
- Backend-driven messages or dynamic tips
- Sound effects
- Mobile-specific behavior differences
