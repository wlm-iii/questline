import type { ReactNode } from 'react'
import { SetupHeader } from '../../components/AppHeader'

export type SetupPageProps = {
  children: ReactNode
  onBuildPlan: () => void
}
export function SetupPage({ children, onBuildPlan }: SetupPageProps) {
  return (
    <main className="setup-page">
      <SetupHeader />
      <section className="setup-intro">
        <span className="eyebrow">A LITTLE PLANNING. A BETTER ADVENTURE.</span>
        <h1>Where will your quest take you?</h1>
        <p>
          Set the essentials first. Then explore your route, rank the
          possibilities, and let everyone weigh in.
        </p>
      </section>
      <form
        className="setup-grid"
        onSubmit={(e) => {
          e.preventDefault()
          onBuildPlan()
        }}
      >
        {children}
      </form>
    </main>
  )
}
