// frontend/components/StepIndicator.tsx
"use client";

const STEPS = ["Preview", "Select from Amazon", "AI Analysis"];

export function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((label, i) => (
        <div key={label} className="contents">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                i < step - 1
                  ? "bg-[#0a2818] text-emerald-400"
                  : i === step - 1
                  ? "bg-[#f97316] text-white"
                  : "bg-[#1a1a2e] border border-[#2a2a45] text-[#4a4a6a]"
              }`}
            >
              {i < step - 1 ? "✓" : i + 1}
            </div>
            <span
              className={`text-[11px] ${
                i < step - 1
                  ? "text-[#2e2e50]"
                  : i === step - 1
                  ? "text-[#ebebf5] font-semibold"
                  : "text-[#4a4a6a]"
              }`}
            >
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className="flex-1 h-px bg-[#1a1a2e] max-w-[48px]" />
          )}
        </div>
      ))}
    </div>
  );
}
