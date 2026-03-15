// frontend/app/search/preview/page.tsx
"use client";
import { Suspense, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getPreviewImages, startSearch } from "@/lib/api";
import { StepIndicator } from "@/components/StepIndicator";

function PreviewContent() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q")?.trim() ?? "";
  const router = useRouter();

  const [images, setImages] = useState<string[]>([]);
  const [isLoadingImages, setIsLoadingImages] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Guard: redirect if no query
  useEffect(() => {
    if (!q) router.replace("/");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch preview images
  useEffect(() => {
    if (!q) return;
    setIsLoadingImages(true);
    getPreviewImages(q)
      .then((result) => setImages(result.images))
      .catch(() => setImages([]))
      .finally(() => setIsLoadingImages(false));
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNo = () => {
    router.push(`/?q=${encodeURIComponent(q)}`);
  };

  const handleConfirm = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const { search_id } = await startSearch(q);
      router.push(`/search/${search_id}/confirm`);
    } catch {
      setIsSubmitting(false);
      setSubmitError("Something went wrong. Please try again.");
    }
  };

  const skeletonSlots = [0, 1, 2, 3];

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <button
        onClick={handleNo}
        className="text-sm text-[#818cf8] hover:text-indigo-300"
      >
        ← Back
      </button>

      <StepIndicator step={1} />

      {/* Query tag */}
      <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] p-3 flex items-center gap-3">
        <div>
          <p className="text-[10px] text-[#4a4a70] uppercase tracking-widest mb-0.5">Searching for</p>
          <p className="text-[15px] font-semibold text-[#ebebf5]">{q}</p>
        </div>
        <button
          onClick={handleNo}
          disabled={isSubmitting}
          className="ml-auto text-[11px] text-[#818cf8] underline underline-offset-2 hover:text-indigo-300 disabled:opacity-40"
        >
          edit query
        </button>
      </div>

      {/* Section label */}
      <p className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest">
        Web preview — is this the right product?
      </p>

      {/* Image grid */}
      <div className="grid grid-cols-4 gap-3">
        {isLoadingImages
          ? skeletonSlots.map((n) => (
              <div key={n} className="aspect-square rounded-xl bg-[#1f1f38] animate-pulse" />
            ))
          : skeletonSlots.map((n) => {
              const url = images[n];
              return url ? (
                <div key={n} className="relative aspect-square overflow-hidden rounded-xl bg-[#1f1f38]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={url} alt="" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div key={n} className="aspect-square rounded-xl bg-[#1f1f38]" />
              );
            })}
      </div>

      {!isLoadingImages && images.length === 0 && (
        <p className="text-[#4a4a70] text-sm text-center">
          Couldn&apos;t load preview images — but you can still proceed
        </p>
      )}

      {/* Confirm box */}
      <div
        className="border border-[#1f1f38] rounded-[14px] p-5"
        style={{ background: "linear-gradient(135deg, #0f0f1a, #131325)" }}
      >
        <p className="text-[15px] font-bold text-[#ebebf5] mb-1">Does this look right?</p>
        <p className="text-[12px] text-[#7878a0] mb-4">
          Confirming will start the Amazon search and AI analysis.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleConfirm}
            disabled={isLoadingImages || isSubmitting}
            className="flex-1 bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.3)] rounded-[10px] py-3 text-white font-bold flex items-center justify-center gap-2 disabled:opacity-40 transition-opacity"
          >
            {isSubmitting ? (
              <span className="inline-block animate-spin">⟳</span>
            ) : (
              "✓"
            )}{" "}
            Yes — Search Amazon for this
          </button>
          <button
            onClick={handleNo}
            disabled={isSubmitting}
            className="bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] py-3 px-5 text-[#818cf8] font-semibold disabled:opacity-40"
          >
            ✕ No, go back
          </button>
        </div>
        {submitError && (
          <p className="text-red-400 text-sm text-center mt-2">{submitError}</p>
        )}
      </div>
    </main>
  );
}

export default function PreviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#07070d]" />}>
      <PreviewContent />
    </Suspense>
  );
}
