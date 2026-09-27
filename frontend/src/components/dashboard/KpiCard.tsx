interface Props {
  label: string;
  value: string;
  sublabel?: string;
}

export function KpiCard({ label, value, sublabel }: Props) {
  return (
    <div className="card p-4">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="text-2xl font-semibold text-text-primary mt-1 tabular-nums">{value}</div>
      {sublabel && <div className="text-xs text-text-muted mt-1">{sublabel}</div>}
    </div>
  );
}
