import { useState, type ReactNode } from "react"

interface Props {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  badge?: string
}

export function CollapsiblePanel({ title, children, defaultOpen = true, badge }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border-b border-ground-300 shrink-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300 hover:bg-ground-300 text-left"
      >
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          {title}
        </span>
        {badge && (
          <span className="ml-2 font-data text-[10px] text-ink-300">{badge}</span>
        )}
        <span className="ml-auto font-data text-[11px] text-ink-300 leading-none">
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && children}
    </div>
  )
}
