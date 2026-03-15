# Baymax Avatar Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent animated Baymax avatar to the bottom-right corner of every page that shows personality quotes on click and contextual tips on page load.

**Architecture:** A `BaymaxProvider` wraps the app in `layout.tsx` and renders `<BaymaxAvatar />` once at the root. Any page calls `useBaymax().setPage('pagename')` to trigger its contextual tip. The avatar manages its own speech bubble state internally. Zero external dependencies.

**Tech Stack:** Next.js 15 (App Router), React, TypeScript, Tailwind CSS v4

---

## Chunk 1: Context + Provider

### Task 1: Create BaymaxContext.tsx

**Files:**
- Create: `frontend/components/BaymaxContext.tsx`

- [ ] **Step 1: Create the context file with full implementation**

```tsx
// frontend/components/BaymaxContext.tsx
"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type BaymaxMood = "idle" | "happy" | "thinking" | "excited";

interface BaymaxContextValue {
  message: string | null;
  mood: BaymaxMood;
  say: (message: string) => void;
  dismiss: () => void;
  setPage: (page: string) => void;
  setMood: (mood: BaymaxMood) => void;
  currentPage: string | null;
}

const BaymaxContext = createContext<BaymaxContextValue | null>(null);

export function BaymaxProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const [mood, setMoodState] = useState<BaymaxMood>("idle");
  const [currentPage, setCurrentPage] = useState<string | null>(null);

  const say = useCallback((msg: string) => {
    setMessage(msg);
  }, []);

  const dismiss = useCallback(() => {
    setMessage(null);
  }, []);

  const setPage = useCallback((page: string) => {
    setCurrentPage(page);
  }, []);

  const setMood = useCallback((mood: BaymaxMood) => {
    setMoodState(mood);
  }, []);

  return (
    <BaymaxContext.Provider value={{ message, mood, say, dismiss, setPage, setMood, currentPage }}>
      {children}
    </BaymaxContext.Provider>
  );
}

export function useBaymax() {
  const ctx = useContext(BaymaxContext);
  if (!ctx) throw new Error("useBaymax must be used within BaymaxProvider");
  return ctx;
}
```

- [ ] **Step 2: Verify the file has no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/components/BaymaxContext.tsx
git commit -m "feat: add BaymaxContext provider and useBaymax hook"
```

---

## Chunk 2: Avatar Component

### Task 2: Create BaymaxAvatar.tsx

**Files:**
- Create: `frontend/components/BaymaxAvatar.tsx`

- [ ] **Step 1: Create the avatar component**

```tsx
// frontend/components/BaymaxAvatar.tsx
"use client";
import { useEffect, useCallback, useRef } from "react";
import { useBaymax } from "./BaymaxContext";

// ─── Configurable content (edit for other projects) ───────────────────────
const PAGE_TIPS: Record<string, string> = {
  home: "Paste an Amazon URL to analyze a product directly.",
  preview: "I'm scanning products. This may take a moment.",
  confirm: "Select the right product and I'll dig into the reviews.",
  results: "Scroll down to see what customers really think.",
  "url-analysis": "I'm analyzing reviews and price history for you.",
};

const QUOTES = [
  "I am not fast. But I am thorough.",
  "On a scale of one to ten, how would you rate your pain?",
  "I will always be there for you.",
  "Hairy baby.",
  "Your health is my only concern.",
];
// ──────────────────────────────────────────────────────────────────────────

function randomQuote(): string {
  return QUOTES[Math.floor(Math.random() * QUOTES.length)];
}

export function BaymaxAvatar() {
  const { message, say, dismiss, currentPage } = useBaymax();
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-dismiss after 4 seconds whenever message changes
  useEffect(() => {
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
    if (message) {
      dismissTimer.current = setTimeout(() => dismiss(), 4000);
    }
    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current);
    };
  }, [message, dismiss]);

  // Show contextual tip 2s after page changes
  useEffect(() => {
    if (!currentPage) return;
    const tip = PAGE_TIPS[currentPage];
    if (!tip) return;
    const t = setTimeout(() => say(tip), 2000);
    return () => clearTimeout(t);
  }, [currentPage, say]);

  const handleClick = useCallback(() => {
    if (message) {
      dismiss();
    } else {
      say(randomQuote());
    }
  }, [message, dismiss, say]);

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
      {/* Speech bubble */}
      {message && (
        <div
          onClick={dismiss}
          className="cursor-pointer max-w-[220px] rounded-[14px_14px_4px_14px] border border-indigo-600 bg-[#0e0e2a] px-3.5 py-2.5 text-[13px] leading-snug text-[#e0e0f0] shadow-xl"
          style={{ animation: "baymax-speech-in 0.25s ease-out" }}
        >
          <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-indigo-400">
            Tip
          </span>
          {message}
        </div>
      )}

      {/* Avatar bubble */}
      <button
        onClick={handleClick}
        aria-label="Baymax assistant"
        className="h-16 w-16 rounded-full overflow-hidden bg-white shadow-lg cursor-pointer border-0 p-0"
        style={{ animation: "baymax-float-glow 3s ease-in-out infinite" }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/baymax.png"
          alt="Baymax"
          className="h-full w-full object-cover"
        />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/components/BaymaxAvatar.tsx
git commit -m "feat: add BaymaxAvatar component with float+glow animation and speech bubble"
```

---

## Chunk 3: CSS Keyframes

### Task 3: Add animations to globals.css

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add keyframes to the end of globals.css**

Add these two keyframe blocks at the end of `frontend/app/globals.css`:

```css
@keyframes baymax-float-glow {
  0%, 100% {
    transform: translateY(0);
    filter: drop-shadow(0 0 0px rgba(165, 180, 252, 0));
  }
  50% {
    transform: translateY(-8px);
    filter: drop-shadow(0 0 12px rgba(165, 180, 252, 0.35));
  }
}

@keyframes baymax-speech-in {
  from {
    opacity: 0;
    transform: scale(0.85) translateY(6px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
```

- [ ] **Step 2: Verify CSS is valid by running the dev server briefly**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds with no CSS errors

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: add Baymax float-glow and speech-in CSS keyframes"
```

---

## Chunk 4: Layout Integration

### Task 4: Wire BaymaxProvider and BaymaxAvatar into layout.tsx

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Update layout.tsx to include provider and avatar**

Replace the contents of `frontend/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { BaymaxProvider } from "@/components/BaymaxContext";
import { BaymaxAvatar } from "@/components/BaymaxAvatar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Amazon Research Tool",
  description: "AI-powered product research with review analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <BaymaxProvider>
          <BaymaxAvatar />
          {children}
        </BaymaxProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat: integrate BaymaxProvider and BaymaxAvatar into root layout"
```

---

## Chunk 5: Page Integration

### Task 5: Wire setPage() calls into each page

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/search/preview/page.tsx`
- Modify: `frontend/app/search/[id]/confirm/page.tsx`
- Modify: `frontend/app/search/[id]/results/page.tsx`
- Modify: `frontend/app/search/url-analysis/page.tsx`

Each page needs to call `useBaymax().setPage('pagename')` in a `useEffect` on mount.

- [ ] **Step 1: Add setPage to home page (frontend/app/page.tsx)**

Target component: `HomeContent` (inner client component, ~line 16).
`useEffect` is already imported — do not add a duplicate import.
Add to imports:
```tsx
import { useBaymax } from "@/components/BaymaxContext";
```
Add inside `HomeContent`, before the return statement:
```tsx
const { setPage } = useBaymax();
useEffect(() => { setPage("home"); }, [setPage]);
```

- [ ] **Step 2: Add setPage to preview page (frontend/app/search/preview/page.tsx)**

Target component: `PreviewContent` (~line 8).
`useEffect` is already imported — do not add a duplicate import.
Add to imports:
```tsx
import { useBaymax } from "@/components/BaymaxContext";
```
Add inside `PreviewContent`, before the return statement:
```tsx
const { setPage } = useBaymax();
useEffect(() => { setPage("preview"); }, [setPage]);
```

- [ ] **Step 3: Add setPage to confirm page (frontend/app/search/[id]/confirm/page.tsx)**

Target component: `ConfirmPage` (default export, ~line 90).
`useEffect` is already imported — do not add a duplicate import.
Add to imports:
```tsx
import { useBaymax } from "@/components/BaymaxContext";
```
Add inside `ConfirmPage`, before the return statement:
```tsx
const { setPage } = useBaymax();
useEffect(() => { setPage("confirm"); }, [setPage]);
```

- [ ] **Step 4: Add setPage to results page (frontend/app/search/[id]/results/page.tsx)**

Target component: `ResultsPage` (default export, ~line 9).
`useEffect` is already imported — do not add a duplicate import.
Add to imports:
```tsx
import { useBaymax } from "@/components/BaymaxContext";
```
Add inside `ResultsPage`, before the return statement:
```tsx
const { setPage } = useBaymax();
useEffect(() => { setPage("results"); }, [setPage]);
```

- [ ] **Step 5: Add setPage to url-analysis page (frontend/app/search/url-analysis/page.tsx)**

Target component: `UrlAnalysisContent` (~line 63).
`useEffect` is already imported — do not add a duplicate import.
Add to imports:
```tsx
import { useBaymax } from "@/components/BaymaxContext";
```
Add inside `UrlAnalysisContent`, before the return statement:
```tsx
const { setPage } = useBaymax();
useEffect(() => { setPage("url-analysis"); }, [setPage]);
```

- [ ] **Step 6: Verify no TypeScript errors across all modified pages**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx \
        frontend/app/search/preview/page.tsx \
        frontend/app/search/[id]/confirm/page.tsx \
        frontend/app/search/[id]/results/page.tsx \
        frontend/app/search/url-analysis/page.tsx
git commit -m "feat: wire setPage() into all pages for Baymax contextual tips"
```

---

## Chunk 6: Manual Verification

### Task 6: End-to-end smoke test

**Files:** None (verification only)

- [ ] **Step 1: Start the dev server**

Run: `cd frontend && npm run dev`
Expected: Server starts on http://localhost:3000

- [ ] **Step 2: Verify avatar appears on home page**

Open http://localhost:3000. Confirm:
- Baymax bubble appears bottom-right
- It floats up and down with a soft indigo glow
- After ~2 seconds, a speech bubble appears with: "Paste an Amazon URL to analyze a product directly."
- Speech bubble auto-dismisses after 4 seconds

- [ ] **Step 3: Verify click behavior**

Click the Baymax bubble:
- If no message showing: a random quote appears in the speech bubble
- If message showing: clicking the bubble OR the speech bubble dismisses it immediately

- [ ] **Step 4: Verify contextual tips on other pages**

Note: the preview page redirects back to `/` if the backend is not running. Start the backend (`cd backend && python main.py`) before testing these pages, or trigger a real search from the home page to navigate naturally.

Navigate to `/search/preview?q=test` (with backend running). Confirm:
- Tip changes to "I'm scanning products. This may take a moment."

Navigate to a results page. Confirm:
- Tip changes to "Scroll down to see what customers really think."

- [ ] **Step 5: Final build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors or warnings about the Baymax components
