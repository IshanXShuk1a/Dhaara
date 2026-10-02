"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { ClassifierPreset, QuadClassificationResult, TrafficClassificationResult } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

interface ApproachInputSlot {
  file: File | null;
  previewUrl: string | null;
  label: string;
}

const DEFAULT_APPROACH_LABELS = [
  "Approach 1 (North)",
  "Approach 2 (South)",
  "Approach 3 (East)",
  "Approach 4 (West)",
];

export default function TrafficClassifierPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const quadFileInputRef = useRef<HTMLInputElement | null>(null);
  const slotInputRefs = [
    useRef<HTMLInputElement | null>(null),
    useRef<HTMLInputElement | null>(null),
    useRef<HTMLInputElement | null>(null),
    useRef<HTMLInputElement | null>(null),
  ];

  // Mode: "quad" (4-Approach Comparative) or "single" (Single Image / Video)
  const [activeMode, setActiveMode] = useState<"quad" | "single">("quad");

  // Quad Mode States
  const [quadPresets, setQuadPresets] = useState<ClassifierPreset[]>([]);
  const [selectedQuadPresetId, setSelectedQuadPresetId] = useState<string | null>(null);
  const [quadSlots, setQuadSlots] = useState<ApproachInputSlot[]>([
    { file: null, previewUrl: null, label: "Approach 1 (North)" },
    { file: null, previewUrl: null, label: "Approach 2 (South)" },
    { file: null, previewUrl: null, label: "Approach 3 (East)" },
    { file: null, previewUrl: null, label: "Approach 4 (West)" },
  ]);
  const [quadResult, setQuadResult] = useState<QuadClassificationResult | null>(null);
  const [isQuadAnalyzing, setIsQuadAnalyzing] = useState(false);
  const [quadError, setQuadError] = useState<string | null>(null);
  const [isQuadDragOver, setIsQuadDragOver] = useState(false);

  // Single Mode States
  const [presets, setPresets] = useState<ClassifierPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TrafficClassificationResult | null>(null);
  const [viewMode, setViewMode] = useState<"annotated" | "original">("annotated");
  const [originalImageUrl, setOriginalImageUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // Initial Data Fetching
  useEffect(() => {
    // Load Quad Presets
    api
      .getQuadClassifierPresets()
      .then((data) => {
        setQuadPresets(data);
        if (data.length > 0 && !quadResult) {
          handleSelectQuadPreset(data[0].id);
        }
      })
      .catch(() => {
        setQuadPresets([
          {
            id: "preset_quad_asymmetric",
            title: "Asymmetric Rush Hour (Dominant Northbound Bottleneck)",
            description: "Approach 1 (North) is heavily congested (12 vehicles, 78% density) while East/West cross-streets are light.",
            expected_state: "ASYMMETRIC_BOTTLENECK",
            icon: "⚡",
          },
          {
            id: "preset_quad_emergency",
            title: "Emergency Vehicle Preemption (Ambulance in Southbound Queue)",
            description: "Approach 2 (South) has an approaching ambulance, demanding immediate green wave priority corridor.",
            expected_state: "EMERGENCY_PREEMPTION",
            icon: "🚨",
          },
          {
            id: "preset_quad_peak_gridlock",
            title: "Peak Hour Uniform Gridlock (All 4 Approaches Saturated)",
            description: "High saturation across North, South, East, and West (> 75% density) requiring maximum cycle splits.",
            expected_state: "UNIFORM_GRIDLOCK",
            icon: "🛑",
          },
          {
            id: "preset_quad_balanced_flow",
            title: "Off-Peak Balanced Flow (Uniform Moderate Demand)",
            description: "Evenly distributed light-to-moderate volume (2-4 vehicles per approach, 25% density).",
            expected_state: "BALANCED_MODERATE",
            icon: "🟢",
          },
        ]);
      });

    // Load Single Presets
    api
      .getClassifierPresets()
      .then((data) => setPresets(data))
      .catch(() => {});
  }, []);

  // --- Quad Mode Handlers ---
  const handleSelectQuadPreset = async (presetId: string) => {
    setSelectedQuadPresetId(presetId);
    setIsQuadAnalyzing(true);
    setQuadError(null);

    try {
      const data = await api.classifyQuadPreset(presetId);
      setQuadResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to run quad comparative analysis";
      setQuadError(msg);
    } finally {
      setIsQuadAnalyzing(false);
    }
  };

  const handleQuadBatchUpload = (files: FileList | File[]) => {
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (f.type.startsWith("image/")) {
        validFiles.push(f);
      }
    }

    if (validFiles.length === 0) {
      setQuadError("Please provide image files (JPEG, PNG, WebP) for the four approaches.");
      return;
    }

    const updated = [...quadSlots];
    validFiles.slice(0, 4).forEach((file, idx) => {
      updated[idx] = {
        file,
        previewUrl: URL.createObjectURL(file),
        label: updated[idx].label || DEFAULT_APPROACH_LABELS[idx],
      };
    });
    setQuadSlots(updated);
    setSelectedQuadPresetId(null);
    setQuadError(null);

    // If 4 images are provided, automatically trigger comparative analysis
    if (updated.every((s) => s.file !== null)) {
      triggerQuadAnalysis(updated);
    }
  };

  const handleSlotFileChange = (index: number, file: File | null) => {
    if (!file) return;
    const updated = [...quadSlots];
    updated[index] = {
      file,
      previewUrl: URL.createObjectURL(file),
      label: updated[index].label,
    };
    setQuadSlots(updated);
    setSelectedQuadPresetId(null);
    setQuadError(null);
  };

  const handleSlotLabelChange = (index: number, newLabel: string) => {
    const updated = [...quadSlots];
    updated[index].label = newLabel;
    setQuadSlots(updated);
  };

  const triggerQuadAnalysis = async (slotsToAnalyze = quadSlots) => {
    const filesToUpload: File[] = [];
    const labels: string[] = [];

    slotsToAnalyze.forEach((slot, idx) => {
      if (slot.file) {
        filesToUpload.push(slot.file);
        labels.push(slot.label || DEFAULT_APPROACH_LABELS[idx]);
      }
    });

    if (filesToUpload.length < 2) {
      setQuadError("Please provide images for all four intersection approaches (or select a 4-way scenario preset).");
      return;
    }

    setIsQuadAnalyzing(true);
    setQuadError(null);

    try {
      const data = await api.classifyQuadImages(filesToUpload, labels);
      setQuadResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to run quad comparative analysis";
      setQuadError(msg);
    } finally {
      setIsQuadAnalyzing(false);
    }
  };

  // --- Single Mode Handlers ---
  const handleSelectPreset = async (presetId: string) => {
    setSelectedPresetId(presetId);
    setIsAnalyzing(true);
    setError(null);
    setOriginalImageUrl(null);

    try {
      const data = await api.classifyPreset(presetId);
      setResult(data);
      setViewMode("annotated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to classify traffic footage";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    const isImage = file.type.startsWith("image/");
    const isVideo = file.type.startsWith("video/") || /\.(mp4|mov|avi|webm|mkv)$/i.test(file.name);

    if (!isImage && !isVideo) {
      setError("Please select a valid image (JPEG, PNG, WebP) or video (MP4, MOV, AVI) file.");
      return;
    }

    setSelectedPresetId(null);
    setIsAnalyzing(true);
    setError(null);

    if (isImage) {
      setOriginalImageUrl(URL.createObjectURL(file));
    } else {
      setOriginalImageUrl(null);
    }

    try {
      const data = await api.classifyImage(file);
      setResult(data);
      setViewMode("annotated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to analyze media file";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getBadgeStyle = (color: string) => {
    switch (color) {
      case "emerald":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "amber":
        return "bg-amber-500/15 text-amber-400 border-amber-500/30";
      case "orange":
        return "bg-orange-500/15 text-orange-400 border-orange-500/30";
      case "rose":
        return "bg-rose-500/15 text-rose-400 border-rose-500/30";
      case "red":
        return "bg-red-600/25 text-red-400 border-red-500/50 shadow-lg shadow-red-500/20 animate-pulse";
      default:
        return "bg-surface-pill text-text-primary border-surface-border";
    }
  };

  const getRankBadgeStyle = (rank: number) => {
    switch (rank) {
      case 1:
        return "bg-rose-500 text-white font-extrabold shadow-md shadow-rose-500/30";
      case 2:
        return "bg-orange-500 text-white font-bold";
      case 3:
        return "bg-amber-500 text-slate-900 font-bold";
      default:
        return "bg-emerald-600 text-white font-medium";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Mode Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-surface-border pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-text-primary">
              AI Traffic Image & Approach Classifier
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/30 uppercase tracking-widest font-bold">
              Multi-Camera ITS
            </span>
          </div>
          <p className="text-xs text-text-muted mt-1">
            Simultaneously ingest four approach images to compute comparative density, directional traffic imbalance, and automated relative signal splits.
          </p>
        </div>

        {/* Mode Toggle Pills */}
        <div className="flex items-center gap-1.5 p-1 bg-surface-pill border border-surface-border rounded-xl self-start">
          <button
            onClick={() => setActiveMode("quad")}
            className={clsx(
              "px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-2",
              activeMode === "quad"
                ? "bg-accent/15 text-accent border border-accent/30 shadow-sm"
                : "text-text-muted hover:text-text-primary border border-transparent"
            )}
          >
            <span>🔲</span>
            <span>4-Approach Comparative Analysis</span>
          </button>
          <button
            onClick={() => setActiveMode("single")}
            className={clsx(
              "px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-2",
              activeMode === "single"
                ? "bg-accent/15 text-accent border border-accent/30 shadow-sm"
                : "text-text-muted hover:text-text-primary border border-transparent"
            )}
          >
            <span>📹</span>
            <span>Single Feed / Video Stream</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MODE 1: 4-APPROACH COMPARATIVE TRAFFIC CLASSIFIER (PRIMARY REQUIREMENT)   */}
      {/* ========================================================================= */}
      {activeMode === "quad" && (
        <div className="space-y-6">
          {/* 4-Way Scenario Presets Bar */}
          <div className="card p-4 bg-surface-card border-surface-border space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-2">
                <span>⚡</span> 1-Click Realistic 4-Way Scenario Presets
              </span>
              <span className="text-[11px] text-text-muted font-mono">
                Click any preset to load 4 synchronized approach feeds
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
              {quadPresets.map((preset) => {
                const isSelected = selectedQuadPresetId === preset.id;
                return (
                  <button
                    key={preset.id}
                    onClick={() => handleSelectQuadPreset(preset.id)}
                    disabled={isQuadAnalyzing}
                    className={clsx(
                      "text-left p-3 rounded-xl border transition-all flex flex-col justify-between gap-2 group relative overflow-hidden",
                      isSelected
                        ? "bg-accent/15 border-accent/60 shadow-lg shadow-accent/10"
                        : "bg-surface-pill border-surface-border hover:border-accent/40 hover:bg-surface-raised"
                    )}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="text-lg">{preset.icon}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-border text-text-muted group-hover:text-text-primary transition-colors">
                        {preset.expected_state.replace("QUAD_", "")}
                      </span>
                    </div>
                    <div>
                      <div className="font-bold text-xs text-text-primary group-hover:text-accent transition-colors leading-tight">
                        {preset.title}
                      </div>
                      <div className="text-[10px] text-text-muted line-clamp-2 mt-1 leading-snug">
                        {preset.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 4-Approach Simultaneous Ingestion Slots */}
          <div className="card p-5 bg-surface-card border-surface-border space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-surface-border pb-3">
              <div>
                <h2 className="text-sm font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
                  <span>📸</span> Synchronous 4-Approach Ingestion Slots
                </h2>
                <p className="text-[11px] text-text-muted">
                  Upload four separate camera snapshots (North, South, East, West) or drag and drop 4 images at once.
                </p>
              </div>

              {/* Master Upload & Action Controls */}
              <div className="flex items-center gap-2">
                <input
                  ref={quadFileInputRef}
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files) handleQuadBatchUpload(e.target.files);
                  }}
                />
                <button
                  onClick={() => quadFileInputRef.current?.click()}
                  className="px-3.5 py-1.5 rounded-xl border border-surface-border bg-surface-pill hover:bg-surface-raised text-xs font-semibold text-text-primary transition-colors flex items-center gap-1.5"
                >
                  <span>📁</span> Select 4 Files at Once
                </button>
                <button
                  onClick={() => triggerQuadAnalysis()}
                  disabled={isQuadAnalyzing || quadSlots.every((s) => s.file === null && !selectedQuadPresetId)}
                  className={clsx(
                    "px-4 py-1.5 rounded-xl text-xs font-extrabold transition-all flex items-center gap-2 shadow-lg",
                    isQuadAnalyzing
                      ? "bg-accent/50 text-slate-900 cursor-wait"
                      : "bg-accent text-slate-900 hover:bg-accent/90 shadow-accent/25 hover:shadow-accent/40 active:scale-95"
                  )}
                >
                  {isQuadAnalyzing ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                      <span>Comparing 4 Approaches...</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Run Comparative Analysis</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Error Banner */}
            {quadError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-center justify-between">
                <span>⚠️ {quadError}</span>
                <button onClick={() => setQuadError(null)} className="text-rose-400 hover:text-rose-200">
                  ✕
                </button>
              </div>
            )}

            {/* 4 Image Slots Grid */}
            <div
              className={clsx(
                "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-3 rounded-2xl border-2 border-dashed transition-all",
                isQuadDragOver ? "border-accent bg-accent/5" : "border-surface-border bg-surface-raised/40"
              )}
              onDragOver={(e) => {
                e.preventDefault();
                setIsQuadDragOver(true);
              }}
              onDragLeave={() => setIsQuadDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsQuadDragOver(false);
                if (e.dataTransfer.files) handleQuadBatchUpload(e.dataTransfer.files);
              }}
            >
              {quadSlots.map((slot, idx) => {
                const analysisItem = quadResult?.approaches.find((a) => a.index === idx);
                return (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border border-surface-border bg-surface-card flex flex-col justify-between space-y-3 relative group"
                  >
                    {/* Header: Approach Label & Rank if analyzed */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-accent" />
                        <span className="text-xs font-bold text-text-primary uppercase tracking-tight">
                          CAM-0{idx + 1}
                        </span>
                      </div>
                      {analysisItem ? (
                        <span className={clsx("text-[10px] px-2 py-0.5 rounded-full", getRankBadgeStyle(analysisItem.rank))}>
                          RANK #{analysisItem.rank}
                        </span>
                      ) : (
                        <span className="text-[10px] text-text-muted font-mono">
                          Slot {idx + 1}/4
                        </span>
                      )}
                    </div>

                    {/* Editable Approach Name */}
                    <input
                      type="text"
                      value={slot.label}
                      onChange={(e) => handleSlotLabelChange(idx, e.target.value)}
                      className="w-full text-xs font-semibold bg-surface-pill px-2.5 py-1 rounded-lg border border-surface-border text-text-primary focus:outline-none focus:border-accent"
                      placeholder={`Approach ${idx + 1}`}
                    />

                    {/* Dropzone / Preview Image */}
                    <div
                      onClick={() => slotInputRefs[idx].current?.click()}
                      className={clsx(
                        "relative w-full aspect-video rounded-xl overflow-hidden border border-surface-border cursor-pointer flex flex-col items-center justify-center transition-all bg-surface-raised group-hover:border-accent/50",
                        slot.previewUrl || analysisItem ? "p-0" : "p-4 hover:bg-surface-pill"
                      )}
                    >
                      <input
                        ref={slotInputRefs[idx]}
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            handleSlotFileChange(idx, e.target.files[0]);
                          }
                        }}
                      />

                      {/* Render either annotated result from analysis or user preview */}
                      {analysisItem?.annotated_image ? (
                        <img
                          src={analysisItem.annotated_image}
                          alt={slot.label}
                          className="w-full h-full object-cover"
                        />
                      ) : slot.previewUrl ? (
                        <img
                          src={slot.previewUrl}
                          alt={slot.label}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="text-center space-y-1">
                          <span className="text-2xl block text-text-muted">📷</span>
                          <span className="text-[11px] font-semibold text-text-primary block">
                            Click to upload
                          </span>
                          <span className="text-[9px] text-text-muted block">
                            JPEG, PNG or WebP
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Quick Metric Preview if Analyzed */}
                    {analysisItem ? (
                      <div className="space-y-1.5 pt-1 border-t border-surface-border text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-text-muted text-[11px]">Relative Share:</span>
                          <span className="font-mono font-bold text-accent">
                            {analysisItem.relative_share_percentage}%
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-text-muted text-[11px]">Density / Veh:</span>
                          <span className="font-mono font-bold text-text-primary">
                            {analysisItem.density_percentage}% ({analysisItem.total_vehicles})
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-text-muted text-[11px]">Signal Allotment:</span>
                          <span className="font-mono font-extrabold text-emerald-400">
                            {analysisItem.recommended_green_s}s Green
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-[10px] text-center text-text-muted pt-1">
                        {slot.file ? `Loaded: ${slot.file.name}` : "Awaiting image input..."}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ========================================================================= */}
          {/* COMPARATIVE ANALYSIS RESULTS DASHBOARD                                    */}
          {/* ========================================================================= */}
          {quadResult && (
            <div className="space-y-6">
              {/* Executive Summary Card: Imbalance Index + Classification Badge */}
              <div className="card p-6 bg-surface-card border-surface-border space-y-5">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-surface-border pb-4">
                  <div className="space-y-1">
                    <div className="text-xs font-mono text-text-muted uppercase tracking-wider">
                      Intersection Comparative Evaluation
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={clsx(
                          "text-xs px-3 py-1 rounded-full font-bold border uppercase tracking-wider",
                          getBadgeStyle(quadResult.comparative_summary.overall_badge_color)
                        )}
                      >
                        {quadResult.comparative_summary.overall_label}
                      </span>
                      <span className="text-xs text-text-muted font-mono">
                        Latency: {quadResult.latency_ms}ms • Cycle: {quadResult.comparative_summary.cycle_length_s}s
                      </span>
                    </div>
                  </div>

                  {/* Summary Metric Stats */}
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-[10px] uppercase font-bold text-text-muted tracking-wide">
                        Traffic Imbalance Index
                      </div>
                      <div className="text-2xl font-mono font-extrabold text-accent">
                        {quadResult.comparative_summary.imbalance_percentage}%
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] uppercase font-bold text-text-muted tracking-wide">
                        Total Vehicles
                      </div>
                      <div className="text-2xl font-mono font-extrabold text-text-primary">
                        <AnimatedNumber value={quadResult.comparative_summary.total_intersection_vehicles} />
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] uppercase font-bold text-text-muted tracking-wide">
                        Avg Density
                      </div>
                      <div className="text-2xl font-mono font-extrabold text-emerald-400">
                        {quadResult.comparative_summary.average_density_percentage}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* AI Tactical Recommendation Banner */}
                <div className="p-4 rounded-xl bg-accent/10 border border-accent/30 flex items-start gap-3">
                  <span className="text-xl">🤖</span>
                  <div className="space-y-1">
                    <div className="text-xs font-bold text-accent uppercase tracking-wide">
                      AI Traffic Controller Recommendation & Signal Split Strategy
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {quadResult.comparative_summary.ai_recommendation}
                    </p>
                  </div>
                </div>

                {/* Relative Traffic Volume Share Continuous Progress Bar */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold text-text-primary">
                    <span>Relative Traffic Share Across Approaches (% of Intersection Demand)</span>
                    <span className="text-text-muted font-mono text-[11px]">Total: 100%</span>
                  </div>
                  <div className="h-4 w-full bg-surface-raised rounded-full overflow-hidden flex border border-surface-border">
                    {quadResult.approaches.map((app) => {
                      const colors = [
                        "bg-rose-500",
                        "bg-orange-500",
                        "bg-amber-400",
                        "bg-emerald-500",
                      ];
                      const col = colors[app.index % colors.length];
                      return (
                        <div
                          key={app.index}
                          style={{ width: `${Math.max(4, app.relative_share_percentage)}%` }}
                          className={clsx("h-full transition-all flex items-center justify-center text-[9px] font-bold text-slate-900 overflow-hidden", col)}
                          title={`${app.label}: ${app.relative_share_percentage}%`}
                        >
                          {app.relative_share_percentage > 10 ? `${app.relative_share_percentage}%` : ""}
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px]">
                    {quadResult.approaches.map((app) => (
                      <div key={app.index} className="flex items-center gap-1.5">
                        <span
                          className={clsx(
                            "w-2.5 h-2.5 rounded-sm",
                            app.index === 0
                              ? "bg-rose-500"
                              : app.index === 1
                              ? "bg-orange-500"
                              : app.index === 2
                              ? "bg-amber-400"
                              : "bg-emerald-500"
                          )}
                        />
                        <span className="text-text-secondary font-medium">{app.label}:</span>
                        <span className="font-mono font-bold text-text-primary">
                          {app.relative_share_percentage}% ({app.recommended_green_s}s Green)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 4-Panel Detailed Approach Breakdown (Grid) */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
                    <span>🔍</span> Detailed Approach Vision & Metrics Breakdown
                  </h3>
                  <span className="text-xs text-text-muted">
                    Ranked by comparative urgency and vehicle queue demand
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  {/* Sorted by rank from #1 to #4 */}
                  {[...quadResult.approaches]
                    .sort((a, b) => a.rank - b.rank)
                    .map((approach) => (
                      <div
                        key={approach.index}
                        className={clsx(
                          "card p-4 bg-surface-card border transition-all flex flex-col justify-between space-y-3.5",
                          approach.rank === 1
                            ? "border-rose-500/50 shadow-lg shadow-rose-500/10"
                            : "border-surface-border"
                        )}
                      >
                        {/* Card Header */}
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-[10px] font-mono text-text-muted uppercase">
                              CAM-0{approach.index + 1}
                            </div>
                            <div className="font-extrabold text-xs text-text-primary">
                              {approach.label}
                            </div>
                          </div>
                          <span
                            className={clsx(
                              "text-xs px-2.5 py-0.5 rounded-full font-bold",
                              getRankBadgeStyle(approach.rank)
                            )}
                          >
                            RANK #{approach.rank}
                          </span>
                        </div>

                        {/* Annotated Feed Image */}
                        <div className="relative w-full aspect-video rounded-xl overflow-hidden border border-surface-border bg-black">
                          <img
                            src={approach.annotated_image}
                            alt={approach.label}
                            className="w-full h-full object-cover"
                          />
                        </div>

                        {/* Relative Status Badge */}
                        <div>
                          <span
                            className={clsx(
                              "text-[10px] px-2.5 py-1 rounded-lg font-bold border uppercase tracking-wide block text-center",
                              getBadgeStyle(approach.relative_badge_color)
                            )}
                          >
                            {approach.relative_status_label}
                          </span>
                        </div>

                        {/* Approach Specific Traffic Gauges */}
                        <div className="space-y-2 p-3 rounded-xl bg-surface-pill border border-surface-border text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-text-muted text-[11px]">Traffic Share:</span>
                            <span className="font-mono font-extrabold text-accent text-sm">
                              {approach.relative_share_percentage}%
                            </span>
                          </div>
                          <div className="w-full h-1.5 bg-surface-border rounded-full overflow-hidden">
                            <div
                              style={{ width: `${Math.min(100, approach.relative_share_percentage * 2)}%` }}
                              className="h-full bg-accent rounded-full"
                            />
                          </div>

                          <div className="flex items-center justify-between pt-1">
                            <span className="text-text-muted text-[11px]">Density Level:</span>
                            <span className="font-mono font-bold text-text-primary">
                              {approach.density_percentage}%
                            </span>
                          </div>
                          <div className="w-full h-1.5 bg-surface-border rounded-full overflow-hidden">
                            <div
                              style={{ width: `${approach.density_percentage}%` }}
                              className={clsx(
                                "h-full rounded-full",
                                approach.density_percentage > 60
                                  ? "bg-rose-500"
                                  : approach.density_percentage > 35
                                  ? "bg-orange-500"
                                  : "bg-emerald-400"
                              )}
                            />
                          </div>

                          <div className="flex items-center justify-between pt-1 border-t border-surface-border">
                            <span className="text-text-muted text-[11px]">Recommended Green:</span>
                            <span className="font-mono font-extrabold text-emerald-400 text-sm">
                              {approach.recommended_green_s}s
                            </span>
                          </div>
                        </div>

                        {/* Vehicle Classification Breakdown */}
                        <div className="pt-1">
                          <div className="text-[10px] uppercase font-bold text-text-muted mb-1.5">
                            Vehicle Classes ({approach.total_vehicles} total):
                          </div>
                          <div className="grid grid-cols-4 gap-1 text-center">
                            <div className="p-1 rounded bg-surface-raised">
                              <span className="text-[9px] text-text-muted block">Cars</span>
                              <span className="font-mono font-bold text-xs text-text-primary">
                                {approach.vehicle_counts["car"] || 0}
                              </span>
                            </div>
                            <div className="p-1 rounded bg-surface-raised">
                              <span className="text-[9px] text-text-muted block">Bikes</span>
                              <span className="font-mono font-bold text-xs text-text-primary">
                                {approach.vehicle_counts["motorcycle"] || 0}
                              </span>
                            </div>
                            <div className="p-1 rounded bg-surface-raised">
                              <span className="text-[9px] text-text-muted block">Buses</span>
                              <span className="font-mono font-bold text-xs text-text-primary">
                                {approach.vehicle_counts["bus"] || 0}
                              </span>
                            </div>
                            <div className="p-1 rounded bg-surface-raised">
                              <span className="text-[9px] text-text-muted block">Trucks</span>
                              <span className="font-mono font-bold text-xs text-text-primary">
                                {approach.vehicle_counts["truck"] || 0}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Safety Alerts / Emergency Warnings */}
                        {approach.emergency_detected && (
                          <div className="p-2 rounded-lg bg-red-600/20 border border-red-500/40 text-[11px] text-red-400 font-bold flex items-center gap-1.5 animate-pulse">
                            <span>🚨</span>
                            <span>EMERGENCY VEHICLE DETECTED</span>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* Comparative Matrix Table */}
              <div className="card p-5 bg-surface-card border-surface-border space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
                    <span>📊</span> Comparative Traffic & Signal Split Allocation Matrix
                  </h3>
                  <span className="text-[11px] text-text-muted font-mono">
                    Cycle Length: 120s • Yellow/All-Red: 20s • Green Pool: 100s
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-surface-border text-[11px] text-text-muted uppercase font-mono">
                        <th className="py-2.5 px-3">Approach</th>
                        <th className="py-2.5 px-3">Priority Rank</th>
                        <th className="py-2.5 px-3">Relative Status</th>
                        <th className="py-2.5 px-3 text-right">Density %</th>
                        <th className="py-2.5 px-3 text-right">Vehicles</th>
                        <th className="py-2.5 px-3 text-right">Traffic Share</th>
                        <th className="py-2.5 px-3 text-right">Allocated Green</th>
                        <th className="py-2.5 px-3 text-center">Emergency</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      {quadResult.approaches.map((app) => (
                        <tr key={app.index} className="hover:bg-surface-raised/50 transition-colors">
                          <td className="py-3 px-3 font-bold text-text-primary">
                            {app.label}
                          </td>
                          <td className="py-3 px-3">
                            <span className={clsx("text-[10px] px-2 py-0.5 rounded-full font-bold", getRankBadgeStyle(app.rank))}>
                              Rank #{app.rank}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={clsx("text-[10px] px-2 py-0.5 rounded border font-semibold", getBadgeStyle(app.relative_badge_color))}>
                              {app.relative_status_label}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right font-mono font-bold text-text-primary">
                            {app.density_percentage}%
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-text-secondary">
                            {app.total_vehicles}
                          </td>
                          <td className="py-3 px-3 text-right font-mono font-extrabold text-accent">
                            {app.relative_share_percentage}%
                          </td>
                          <td className="py-3 px-3 text-right font-mono font-extrabold text-emerald-400">
                            {app.recommended_green_s}s
                          </td>
                          <td className="py-3 px-3 text-center">
                            {app.emergency_detected ? (
                              <span className="text-red-400 font-extrabold animate-pulse">🚨 YES</span>
                            ) : (
                              <span className="text-text-muted">None</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE 2: SINGLE IMAGE / VIDEO STREAM CLASSIFIER                            */}
      {/* ========================================================================= */}
      {activeMode === "single" && (
        <div className="space-y-6">
          {/* Preset Buttons */}
          <div className="card p-4 bg-surface-card border-surface-border space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary uppercase tracking-wide">
                Single Feed Demo Scenarios
              </span>
              <span className="text-[11px] text-text-muted font-mono">
                Quick test realistic intersection footage
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
              {presets.map((preset) => {
                const isSelected = selectedPresetId === preset.id;
                return (
                  <button
                    key={preset.id}
                    onClick={() => handleSelectPreset(preset.id)}
                    disabled={isAnalyzing}
                    className={clsx(
                      "text-left p-3 rounded-xl border transition-all flex flex-col justify-between gap-2 group",
                      isSelected
                        ? "bg-accent/15 border-accent/60 shadow-md shadow-accent/10"
                        : "bg-surface-pill border-surface-border hover:border-accent/40 hover:bg-surface-raised"
                    )}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="text-lg">{preset.icon}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-border text-text-muted group-hover:text-text-primary transition-colors">
                        {preset.expected_state}
                      </span>
                    </div>
                    <div>
                      <div className="font-bold text-xs text-text-primary group-hover:text-accent transition-colors leading-tight">
                        {preset.title}
                      </div>
                      <div className="text-[10px] text-text-muted line-clamp-2 mt-1 leading-snug">
                        {preset.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Upload Dropzone */}
          <div
            className={clsx(
              "card p-6 border-2 border-dashed transition-all text-center flex flex-col items-center justify-center gap-3 cursor-pointer",
              isDragOver ? "border-accent bg-accent/5" : "border-surface-border hover:border-accent/50 bg-surface-card"
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
              }
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/avi"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />

            <div className="w-12 h-12 rounded-2xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent text-2xl">
              📹
            </div>
            <div>
              <div className="text-sm font-bold text-text-primary">
                Upload image or video for AI Traffic Evaluation
              </div>
              <div className="text-xs text-text-muted mt-1">
                Drag and drop files here, or click to browse. Supports JPEG, PNG, WebP, MP4, MOV, AVI (up to 60MB).
              </div>
            </div>
          </div>

          {/* Single Result Viewer */}
          {result && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-8 card p-4 bg-surface-card border-surface-border space-y-3">
                <div className="flex items-center justify-between border-b border-surface-border pb-3">
                  <span className="text-xs font-bold text-text-primary uppercase">
                    Feed Preview: {result.filename}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setViewMode("annotated")}
                      className={clsx(
                        "px-2.5 py-1 rounded-lg text-xs font-bold transition-all",
                        viewMode === "annotated" ? "bg-accent text-slate-900" : "bg-surface-pill text-text-muted"
                      )}
                    >
                      Annotated
                    </button>
                    {originalImageUrl && (
                      <button
                        onClick={() => setViewMode("original")}
                        className={clsx(
                          "px-2.5 py-1 rounded-lg text-xs font-bold transition-all",
                          viewMode === "original" ? "bg-accent text-slate-900" : "bg-surface-pill text-text-muted"
                        )}
                      >
                        Original
                      </button>
                    )}
                  </div>
                </div>

                <div className="relative w-full aspect-video rounded-xl overflow-hidden border border-surface-border bg-black">
                  <img
                    src={viewMode === "annotated" ? result.annotated_image : originalImageUrl || result.annotated_image}
                    alt="Analyzed Traffic"
                    className="w-full h-full object-contain"
                  />
                </div>
              </div>

              {/* Single Mode Right Panel */}
              <div className="lg:col-span-4 space-y-4">
                <div className="card p-4 bg-surface-card border-surface-border space-y-3">
                  <span className="text-xs font-bold text-text-primary uppercase tracking-wide block">
                    Classification Status
                  </span>
                  <span className={clsx("text-xs px-3 py-1 rounded-full font-bold border uppercase block text-center", getBadgeStyle(result.classification.badge_color))}>
                    {result.classification.label}
                  </span>

                  <div className="grid grid-cols-2 gap-2 text-xs pt-2">
                    <div className="p-2.5 rounded-xl bg-surface-pill border border-surface-border">
                      <span className="text-text-muted text-[10px] block">Vehicles</span>
                      <span className="text-xl font-mono font-extrabold text-text-primary">
                        {result.classification.total_vehicles}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-surface-pill border border-surface-border">
                      <span className="text-text-muted text-[10px] block">Density</span>
                      <span className="text-xl font-mono font-extrabold text-accent">
                        {result.classification.density_percentage}%
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-text-secondary leading-relaxed pt-2">
                    {result.classification.ai_reasoning}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
