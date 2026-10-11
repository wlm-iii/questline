export type TripStatsProps = {
  mainCount: number
  total: number
  budget: number
  completed: number
}
export function TripStats({
  mainCount,
  total,
  budget,
  completed,
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
        <strong>${total}</strong>
        <p>Of your ${budget} daily budget</p>
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
