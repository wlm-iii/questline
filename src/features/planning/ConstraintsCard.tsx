import type { Constraints } from '../../demo/types'

export type ConstraintsCardProps = {
  constraints: Constraints
  onConstraintsChange: (constraints: Constraints) => void
}
export function ConstraintsCard({
  constraints,
  onConstraintsChange,
}: ConstraintsCardProps) {
  return (
    <article className="desk-card">
      <div className="section-title">
        <h3>Restrictions & limits</h3>
        <span>Party constraints</span>
      </div>
      <label>
        Back by
        <input
          type="time"
          value={constraints.returnBy}
          onChange={(e) =>
            onConstraintsChange({ ...constraints, returnBy: e.target.value })
          }
        />
      </label>
      <label>
        Max walking per leg (minutes)
        <input
          type="number"
          min="0"
          max="240"
          value={constraints.maxWalk}
          onChange={(e) =>
            onConstraintsChange({
              ...constraints,
              maxWalk: Number(e.target.value),
            })
          }
        />
      </label>
      <label>
        Food preferences
        <input
          value={constraints.dietary}
          onChange={(e) =>
            onConstraintsChange({ ...constraints, dietary: e.target.value })
          }
        />
      </label>
      <label>
        Accessibility & mobility
        <input
          value={constraints.mobility}
          onChange={(e) =>
            onConstraintsChange({ ...constraints, mobility: e.target.value })
          }
        />
      </label>
      <p className="desk-footnote">
        Saved preferences for the group to review. Automatic route validation is
        not connected.
      </p>
    </article>
  )
}
