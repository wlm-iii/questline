export type TripStatsProps = {
  mainCount: number
  total?: number
  budget?: number
  completed: number
  /** Replaces `$total`, e.g. "$30–60". */
  totalLabel?: string
  /** Replaces "Of your $budget daily budget". */
  budgetLabel?: string
}
export function TripStats({
  mainCount,
  total = 0,
  budget = 0,
  completed,
  totalLabel,
  budgetLabel,
}: TripStatsProps) {
  return (
    <div className="stats-grid">
      <article>
        <span>ON THE MAIN QUEST</span>
        <strong>{mainCount}</strong>
        <p>Stops worth making time for</p>
      </article>
      <article>
        <span>ESTIMATE / PERSON</span>
        <strong>{totalLabel ?? `$${total}`}</strong>
        <p>{budgetLabel ?? `Of your $${budget} daily budget`}</p>
      </article>
      <article>
        <span>ADVENTURE PROGRESS</span>
        <strong>
          {completed}/{mainCount}
        </strong>
        <p>Main quests completed</p>
      </article>
    </div>
  )
}
