interface PlaceholderSectionProps {
  title: string;
  description: string;
  phaseLabel: string;
}

export function PlaceholderSection({ title, description, phaseLabel }: PlaceholderSectionProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold text-slate-900">{title}</h1>
        <span className="rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
          Sắp mở ở {phaseLabel}
        </span>
      </div>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p>
    </div>
  );
}
