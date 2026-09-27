"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";

interface ConfigData {
  detection: Record<string, number>;
  signal_timings: Record<string, number>;
  fairness: Record<string, number>;
  lane_thresholds: Record<string, number>;
  pressure_weights: Record<string, number>;
}

export default function SettingsPage() {
  const { role } = useAuth();
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [edited, setEdited] = useState<ConfigData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (role !== "ADMIN") return;
    api
      .getConfig()
      .then((c) => {
        setConfig(c);
        setEdited(JSON.parse(JSON.stringify(c)));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load config"));
  }, [role]);

  if (role !== "ADMIN") {
    return (
      <div className="card p-6 text-sm text-text-muted max-w-xl">
        <div className="text-base font-semibold text-text-primary mb-1">Access Restricted</div>
        Configuration settings require <span className="font-semibold text-accent">ADMIN</span> credentials. Sign in as
        admin to view or modify system thresholds.
      </div>
    );
  }

  function handleFieldChange(section: keyof ConfigData, key: string, value: string) {
    if (!edited) return;
    const num = Number(value);
    setEdited({
      ...edited,
      [section]: {
        ...edited[section],
        [key]: isNaN(num) ? 0 : num,
      },
    });
    setSaveSuccess(null);
  }

  async function handleSave() {
    if (!edited) return;
    setIsSaving(true);
    setError(null);
    setSaveSuccess(null);
    try {
      const res = await api.updateConfig(edited);
      setConfig(res);
      setEdited(JSON.parse(JSON.stringify(res)));
      setSaveSuccess("Configuration safely applied live across all running intersection controllers!");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save configuration");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xl font-bold text-text-primary">System Configuration</div>
          <div className="text-xs text-text-muted mt-1">
            Tune YOLO confidence, signal timing state machine bounds, fairness rules, and pressure calculation weights live.
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={isSaving || !edited}
          className="text-xs px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors shadow-sm"
        >
          {isSaving ? "Saving..." : "Save Configuration"}
        </button>
      </div>

      {saveSuccess && (
        <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 flex items-center gap-2">
          <span className="status-dot bg-status-online" />
          <span>{saveSuccess}</span>
        </div>
      )}

      {error && <div className="text-xs text-status-congested p-3 rounded-lg bg-status-congested/10 border border-status-congested/30">{error}</div>}
      {!edited && !error && <div className="text-sm text-text-muted">Loading backend configuration...</div>}

      {edited && (
        <div className="space-y-4">
          <EditableSection
            title="Signal Timings (Seconds)"
            description="Controls the Signal FSM minimum safety clearances and maximum green phases"
            sectionKey="signal_timings"
            values={edited.signal_timings}
            onChange={handleFieldChange}
          />

          <EditableSection
            title="Detection Thresholds"
            description="Confidence cutoffs for YOLO vehicle tracking, helmet safety, and ambulance confirmation"
            sectionKey="detection"
            values={edited.detection}
            onChange={handleFieldChange}
          />

          <EditableSection
            title="Lane Status Classification (Pressure Thresholds)"
            description="Pressure boundary scores (0-100) determining FREE, LOW, MODERATE, HIGH, and CONGESTED"
            sectionKey="lane_thresholds"
            values={edited.lane_thresholds}
            onChange={handleFieldChange}
          />

          <EditableSection
            title="Traffic Pressure Formula Weights"
            description="Formula: pressure = w_occ*occupancy + w_queue*queue + w_count*count + w_wait*wait - w_speed*speed"
            sectionKey="pressure_weights"
            values={edited.pressure_weights}
            onChange={handleFieldChange}
          />

          <EditableSection
            title="Fairness Protection"
            description="Prevents high-density arteries from starving cross-streets (maximum consecutive priority wins)"
            sectionKey="fairness"
            values={edited.fairness}
            onChange={handleFieldChange}
          />
        </div>
      )}
    </div>
  );
}

function EditableSection({
  title,
  description,
  sectionKey,
  values,
  onChange,
}: {
  title: string;
  description: string;
  sectionKey: keyof ConfigData;
  values: Record<string, number>;
  onChange: (section: keyof ConfigData, key: string, value: string) => void;
}) {
  return (
    <div className="card p-4 space-y-3">
      <div>
        <div className="text-sm font-semibold text-text-primary">{title}</div>
        <div className="text-[11px] text-text-muted mt-0.5">{description}</div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs pt-1">
        {Object.entries(values).map(([key, val]) => (
          <div key={key} className="space-y-1">
            <label className="text-[11px] text-text-muted font-mono">{key}</label>
            <input
              type="number"
              step="any"
              value={val}
              onChange={(e) => onChange(sectionKey, key, e.target.value)}
              className="w-full bg-surface-card border border-surface-border rounded px-2.5 py-1.5 text-xs text-text-primary tabular-nums focus:outline-none focus:border-accent"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
