const COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  plan_pending_approval: "bg-amber-100 text-amber-800",
  plan_approved: "bg-blue-100 text-blue-800",
  preview_pending_approval: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  running: "bg-indigo-100 text-indigo-800",
  published: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  succeeded: "bg-green-100 text-green-800",
};

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
