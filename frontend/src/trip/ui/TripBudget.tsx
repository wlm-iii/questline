import type { Estimate } from '../adapters'

export type TripBudgetProps = { estimate: Estimate; scope: string }

export function TripBudget({ estimate, scope }: TripBudgetProps) {
  return (
    <>
      <div className="budget">
        <div>
          <small>EST. FOOD + ACTIVITIES / PERSON</small>
          <strong>{estimate.amount}</strong>
        </div>
        <span className="budget-note">
          {scope}
          <br />
          Transport excluded
        </span>
      </div>
      {estimate.note && <p className="budget-warning">{estimate.note}</p>}
    </>
  )
}
