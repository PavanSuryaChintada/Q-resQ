import { useState } from "react"
import { CollapsiblePanel } from "./CollapsiblePanel"

const KIND_COLOR: Record<string, string> = {
  ambulance: "#5C8A6E",
  rescue_team: "#C9A227",
  truck: "#9A968D",
  excavator: "#6B6862",
  helicopter: "#4A7C59",
  boat: "#4A6B9A",
}

interface Resource {
  id: number
  kind: string
  available: number
  total: number
  updated_at: string
}

export function UnitsPanel() {
  const [resources, setResources] = useState<Resource[]>([
    { id: 1, kind: "ambulance", available: 5, total: 8, updated_at: new Date().toISOString() },
    { id: 2, kind: "rescue_team", available: 12, total: 15, updated_at: new Date().toISOString() },
    { id: 3, kind: "truck", available: 3, total: 5, updated_at: new Date().toISOString() },
    { id: 4, kind: "excavator", available: 2, total: 3, updated_at: new Date().toISOString() },
    { id: 5, kind: "helicopter", available: 1, total: 2, updated_at: new Date().toISOString() },
    { id: 6, kind: "boat", available: 4, total: 6, updated_at: new Date().toISOString() },
  ])
  const [editing, setEditing] = useState<number | null>(null)
  const [editValues, setEditValues] = useState<{ available: number; total: number } | null>(null)

  const handleEdit = (id: number, current: Resource) => {
    setEditing(id)
    setEditValues({ available: current.available, total: current.total })
  }

  const handleSave = (id: number) => {
    if (!editValues) return
    setResources(resources.map(r =>
      r.id === id ? { ...r, ...editValues, updated_at: new Date().toISOString() } : r
    ))
    setEditing(null)
    setEditValues(null)
  }

  const handleCancel = () => {
    setEditing(null)
    setEditValues(null)
  }

  const totalAvailable = resources.reduce((sum, r) => sum + r.available, 0)
  const totalCapacity = resources.reduce((sum, r) => sum + r.total, 0)

  return (
    <CollapsiblePanel title="Resource Pool" badge={`${totalAvailable}/${totalCapacity} available`}>
      <div className="max-h-[320px] overflow-y-auto">
        {resources.map((r) => (
          <div key={r.id} className="px-3 py-2 border-b border-ground-300/50">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="w-2 h-2 inline-block shrink-0"
                style={{ background: KIND_COLOR[r.kind] ?? "#6B6862" }}
              />
              <span className="text-ink-000 text-[13px] font-medium capitalize">{r.kind.replace('_', ' ')}</span>
              {editing === r.id ? (
                <div className="ml-auto flex gap-1">
                  <button
                    onClick={() => handleSave(r.id)}
                    className="text-[10px] px-1.5 py-0.5 bg-ground-200 border border-ground-300"
                  >
                    Save
                  </button>
                  <button
                    onClick={handleCancel}
                    className="text-[10px] px-1.5 py-0.5 bg-ground-200 border border-ground-300"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleEdit(r.id, r)}
                  className="ml-auto text-[10px] px-1.5 py-0.5 bg-ground-200 border border-ground-300"
                >
                  Edit
                </button>
              )}
            </div>
            {editing === r.id && editValues ? (
              <div className="flex gap-2 text-[11px]">
                <div className="flex-1">
                  <label className="text-ink-300">Available</label>
                  <input
                    type="number"
                    value={editValues.available}
                    onChange={(e) => setEditValues({ ...editValues, available: parseInt(e.target.value) || 0 })}
                    className="w-full mt-0.5 p-1 border border-ground-300 bg-ground-000"
                    min="0"
                    max={editValues.total}
                  />
                </div>
                <div className="flex-1">
                  <label className="text-ink-300">Total</label>
                  <input
                    type="number"
                    value={editValues.total}
                    onChange={(e) => setEditValues({ ...editValues, total: parseInt(e.target.value) || 0 })}
                    className="w-full mt-0.5 p-1 border border-ground-300 bg-ground-000"
                    min={editValues.available}
                  />
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-[11px] text-ink-300">
                <span>Available: {r.available}</span>
                <span className="text-ground-400">|</span>
                <span>Total: {r.total}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </CollapsiblePanel>
  )
}
