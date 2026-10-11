export type BudgetSummaryProps = { total: number; budget: number }
export function BudgetSummary({ total, budget }: BudgetSummaryProps) {
  return (
    <>
      <div className="budget">
        <div>
          <small>EST. FOOD + ACTIVITIES / PERSON</small>
          <strong>
            ${total}
            <span> / day</span>
          </strong>
        </div>
        <span className="budget-note">
          Budget ${budget}
          <br />
          Transport excluded
        </span>
      </div>
      <div className={`budget-meter ${total > budget ? 'over' : ''}`}>
        <div style={{ width: `${Math.min(100, (total / budget) * 100)}%` }} />
      </div>
      {total > budget && (
        <p className="budget-warning">
          ${total - budget} above your daily budget. Consider moving a stop to a
          side quest.
        </p>
      )}
    </>
  )
}
