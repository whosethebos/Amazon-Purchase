"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { analyzeUrl, fetchSimilarProducts } from "@/lib/api";
import type { AnalyzeUrlResponse, Histogram, Review, SimilarProduct } from "@/lib/types";
import { useBaymax } from "@/components/BaymaxContext";

// ─── ScoreCard ─────────────────────────────────────────────────────────────────

function ScoreCard({ score }: { score: number | null }) {
  if (score === null || score < 1 || score > 10) return null;

  const color =
    score >= 7 ? "text-emerald-400" : score >= 4 ? "text-yellow-400" : "text-red-400";
  const label =
    score >= 7 ? "Good buy" : score >= 4 ? "Mixed bag" : "Avoid";

  return (
    <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 flex items-center gap-5">
      <div className={`text-5xl font-bold tabular-nums ${color}`}>
        {score}<span className="text-2xl text-[#9898b8] font-normal">/10</span>
      </div>
      <div>
        <p className={`text-lg font-semibold ${color}`}>{label}</p>
        <p className="text-[#9898b8] text-xs mt-0.5">Overall score based on reviews & analysis</p>
      </div>
    </div>
  );
}

// ─── SimilarProductCard ────────────────────────────────────────────────────────

function SimilarProductCard({ product }: { product: SimilarProduct }) {
  return (
    <a
      href={product.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-4 hover:border-[#818cf8] transition-colors"
    >
      <div className="flex gap-3 items-start">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt={product.title}
            width={64}
            height={64}
            className="object-contain rounded-lg shrink-0 w-16 h-16"
          />
        ) : (
          <div className="w-16 h-16 bg-[#1a1a2e] rounded-lg shrink-0" />
        )}
        <div className="min-w-0 space-y-1">
          <p className="text-[#ebebf5] text-sm font-medium line-clamp-2 leading-snug">
            {product.title}
          </p>
          {product.price != null && (
            <p className="text-[#f97316] font-bold text-sm">
              {product.currency ?? "USD"} {product.price.toFixed(2)}
            </p>
          )}
          {product.rating != null && (
            <p className="text-[#9898b8] text-xs">
              ★ {product.rating.toFixed(1)}
              {product.review_count != null && (
                <span> ({product.review_count.toLocaleString()})</span>
              )}
            </p>
          )}
        </div>
      </div>
    </a>
  );
}

// ─── SimilarProductSkeleton ────────────────────────────────────────────────────

function SimilarProductSkeleton() {
  return (
    <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-4 animate-pulse">
      <div className="flex gap-3 items-start">
        <div className="w-16 h-16 bg-[#1a1a2e] rounded-lg shrink-0" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 bg-[#1a1a2e] rounded w-full" />
          <div className="h-3 bg-[#1a1a2e] rounded w-3/4" />
          <div className="h-3 bg-[#1a1a2e] rounded w-1/2" />
        </div>
      </div>
    </div>
  );
}

// ─── ReviewCard ────────────────────────────────────────────────────────────────

function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const TRUNCATE = 300;
  const isLong = review.body.length > TRUNCATE;
  const displayed = expanded ? review.body : review.body.slice(0, TRUNCATE);

  return (
    <div className="rounded-lg bg-[#1a1a2e] border border-[#2a2a45] p-4 mb-3">
      <div className="text-[#f97316] text-sm mb-1">
        {"★".repeat(review.stars)}{"☆".repeat(Math.max(0, 5 - review.stars))}
      </div>
      <p className="text-[#ebebf5] font-semibold text-sm">
        {review.author} — {review.title}
      </p>
      <p className="text-[#9898b8] text-sm mt-1">
        {displayed}{isLong && !expanded ? "…" : ""}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-[#818cf8] text-xs mt-1 underline"
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </div>
  );
}

// ─── HistogramBar ──────────────────────────────────────────────────────────────

function HistogramBar({ star, pct }: { star: number; pct: number }) {
  const barClass =
    star >= 4 ? "bg-emerald-400" : star === 3 ? "bg-yellow-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-8 text-[#9898b8] text-xs shrink-0">{star}★</span>
      <div className="flex-1 h-2 bg-[#1a1a2e] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barClass}`}
          style={{ width: `${pct.toFixed(1)}%` }}
        />
      </div>
      <span className="w-12 text-right text-[#9898b8] text-xs shrink-0">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ─── UrlAnalysisContent ────────────────────────────────────────────────────────

function UrlAnalysisContent() {
  const searchParams = useSearchParams();
  const asin = searchParams.get("asin");
  const urlParam = searchParams.get("url");
  const resolvedUrl = urlParam ?? (asin ? `https://www.amazon.com/dp/${asin}` : null);
  const { setPage } = useBaymax();
  useEffect(() => { setPage("url-analysis"); }, [setPage]);

  const [data, setData] = useState<AnalyzeUrlResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [modelElapsed, setModelElapsed] = useState(0);
  const [similarProducts, setSimilarProducts] = useState<SimilarProduct[] | null>(null);
  const stepTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const STEPS = [
    { label: "Resolving URL", detail: "Following redirects to get full product link" },
    { label: "Launching browser", detail: "Starting headless Chromium" },
    { label: "Loading product page", detail: "Fetching Amazon product page" },
    { label: "Reading product details", detail: "Extracting title, price, rating & images" },
    { label: "Loading reviews", detail: "Scrolling page to load customer reviews" },
    { label: "Formatting review data", detail: "Building prompt from scraped reviews" },
    { label: "Querying AI model (qwen3:14b)", detail: null },  // elapsed counter shown here
  ];

  // Advance steps on a schedule that roughly mirrors real backend timing
  const STEP_DELAYS = [0, 1500, 4000, 9000, 12000, 16000, 16800];

  // Start elapsed counter when AI model query step becomes active
  const AI_MODEL_STEP = 6;

  useEffect(() => {
    if (stepIndex === AI_MODEL_STEP) {
      setModelElapsed(0);
      elapsedTimer.current = setInterval(() => {
        setModelElapsed((s) => s + 1);
      }, 1000);
    } else if (elapsedTimer.current) {
      clearInterval(elapsedTimer.current);
      elapsedTimer.current = null;
    }
  }, [stepIndex]);

  useEffect(() => {
    if (!resolvedUrl) {
      setError("Invalid product URL");
      return;
    }

    const controller = new AbortController();

    // Schedule step advances
    STEP_DELAYS.forEach((delay, i) => {
      const t = setTimeout(() => setStepIndex(i), delay);
      stepTimers.current.push(t);
    });

    analyzeUrl(resolvedUrl, controller.signal)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Analysis failed");
      });

    return () => {
      controller.abort();
      stepTimers.current.forEach(clearTimeout);
      stepTimers.current = [];
      if (elapsedTimer.current) {
        clearInterval(elapsedTimer.current);
        elapsedTimer.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedUrl]);

  useEffect(() => {
    if (!data) return;
    fetchSimilarProducts(data.product.asin, data.product.title)
      .then(setSimilarProducts)
      .catch(() => setSimilarProducts([]));
  }, [data]);

  // ── Loading ──
  if (!data && !error) {
    return (
      <main className="min-h-screen bg-[#07070d] flex items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-6">
          <div className="text-center">
            <div className="w-10 h-10 border-2 border-[#f97316] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-[#ebebf5] font-semibold text-sm">Analyzing product</p>
          </div>
          <div className="space-y-2">
            {STEPS.map((step, i) => {
              const done = i < stepIndex;
              const active = i === stepIndex;
              return (
                <div
                  key={i}
                  className={`flex items-start gap-3 rounded-lg px-3 py-2 transition-all duration-300 ${
                    active ? "bg-[#1a1a2e] border border-[#2a2a45]" : ""
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {done ? (
                      <span className="text-emerald-400 text-sm">✓</span>
                    ) : active ? (
                      <div className="w-3.5 h-3.5 border border-[#f97316] border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border border-[#2a2a45]" />
                    )}
                  </div>
                  <div>
                    <p className={`text-sm font-medium ${done ? "text-[#9898b8]" : active ? "text-[#ebebf5]" : "text-[#3a3a5a]"}`}>
                      {step.label}
                    </p>
                    {active && (
                      <p className="text-xs text-[#9898b8] mt-0.5">
                        {i === AI_MODEL_STEP
                          ? `Waiting for response… ${modelElapsed}s`
                          : step.detail}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <main className="min-h-screen bg-[#07070d] flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-red-400 text-sm">{error}</p>
          <Link href="/" className="text-[#818cf8] text-sm underline">
            ← Try again
          </Link>
        </div>
      </main>
    );
  }

  const { product, histogram, analysis, reviews } = data!;
  const featuredReviews = analysis.featured_review_indices
    .map((idx) => reviews[idx])
    .filter(Boolean) as Review[];

  return (
    <main className="min-h-screen bg-[#07070d]">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-8">

        {/* Back link */}
        <Link href="/" className="text-[#818cf8] text-sm hover:text-indigo-300 transition-colors">
          ← New Search
        </Link>

        {/* Score */}
        <ScoreCard score={analysis.score} />

        {/* Section A — Product Header */}
        <div className="flex gap-4 items-start bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5">
          {product.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.image_url}
              alt={product.title}
              width={120}
              height={120}
              className="object-contain rounded-lg shrink-0"
            />
          ) : (
            <div className="w-[120px] h-[120px] bg-[#1a1a2e] rounded-lg shrink-0" />
          )}
          <div className="space-y-1 min-w-0">
            <p className="text-lg font-semibold text-[#ebebf5] leading-snug">{product.title}</p>
            {product.price != null && (
              <p className="text-[#f97316] font-bold text-xl">
                {product.currency ?? "USD"} {product.price.toFixed(2)}
              </p>
            )}
            {product.rating != null && (
              <p className="text-[#9898b8] text-sm">
                ★ {product.rating.toFixed(1)}{" "}
                {product.review_count != null && (
                  <span>({product.review_count.toLocaleString()} reviews)</span>
                )}
              </p>
            )}
            {asin && (
              <a
                href={`https://camelcamelcamel.com/product/${asin}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#818cf8] text-xs underline hover:text-indigo-300"
              >
                Price history ↗
              </a>
            )}
          </div>
        </div>

        {/* Section B — Rating Breakdown */}
        <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 space-y-3">
          <h2 className="text-[#ebebf5] font-semibold mb-3">Rating Breakdown</h2>
          {([5, 4, 3, 2, 1] as const).map((star) => (
            <HistogramBar
              key={star}
              star={star}
              pct={histogram[`${star}` as keyof Histogram]}
            />
          ))}
        </div>

        {/* Section C — AI Analysis */}
        <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 space-y-4">
          <h2 className="text-[#ebebf5] font-semibold">AI Analysis</h2>
          {analysis.summary && (
            <p className="text-[#9898b8] text-sm leading-relaxed">{analysis.summary}</p>
          )}
          {analysis.pros.length > 0 && (
            <div>
              <p className="text-emerald-400 text-xs font-bold uppercase tracking-wider mb-2">Pros</p>
              <ul className="space-y-1">
                {analysis.pros.map((pro, i) => (
                  <li key={i} className="flex gap-2 text-sm text-[#9898b8]">
                    <span className="text-emerald-400 shrink-0">✓</span>
                    {pro}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.cons.length > 0 && (
            <div>
              <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-2">Cons</p>
              <ul className="space-y-1">
                {analysis.cons.map((con, i) => (
                  <li key={i} className="flex gap-2 text-sm text-[#9898b8]">
                    <span className="text-red-400 shrink-0">✗</span>
                    {con}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Section D — Featured Reviews */}
        {featuredReviews.length > 0 && (
          <div>
            <h2 className="text-[#ebebf5] font-semibold mb-3">Featured Reviews</h2>
            {featuredReviews.map((review, i) => (
              <ReviewCard key={i} review={review} />
            ))}
          </div>
        )}

        {/* Section E — Similar Products */}
        {(similarProducts === null || similarProducts.length > 0) && (
          <div>
            <h2 className="text-[#ebebf5] font-semibold mb-3">Similar Products</h2>
            <div className="grid grid-cols-1 gap-3">
              {similarProducts === null
                ? Array.from({ length: 4 }).map((_, i) => <SimilarProductSkeleton key={i} />)
                : similarProducts.map((p) => <SimilarProductCard key={p.asin} product={p} />)
              }
            </div>
          </div>
        )}

      </div>
    </main>
  );
}

// ─── Page (Suspense shell) ─────────────────────────────────────────────────────

export default function UrlAnalysisPage() {
  return (
    <Suspense fallback={null}>
      <UrlAnalysisContent />
    </Suspense>
  );
}
