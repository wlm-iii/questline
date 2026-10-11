import { useMemo, useState } from 'react'
import { navigateHome, tripUrl, useTrip } from '../state'
import { PlannerHeader } from '../components/AppHeader'
import { TripHeading } from '../components/TripHeading'
import { AppFooter } from '../components/AppFooter'
import { Notice } from '../components/Notice'
import { PartyCard } from '../features/overview/PartyCard'
import { tripHeadingFromSnapshot } from './tripHeadingAdapter'
import { TripWorkspace } from './TripWorkspace'

/** The live trip shell. Must render inside `<TripProvider>`. */
export function TripApp() {
  const { session, snapshot, error } = useTrip()
  const [notice, setNotice] = useState('')
  const heading = useMemo(
    () => (snapshot ? tripHeadingFromSnapshot(snapshot, session.memberId) : null),
    [snapshot, session.memberId],
  )
  const status = snapshot ? (error ? 'Reconnecting…' : 'Live') : error ? 'Connecting…' : 'Loading…'

  function shareTrip() {
    const link = tripUrl(session.tripId)
    if (!navigator.clipboard) return setNotice(`Share this link with your party: ${link}`)
    navigator.clipboard
      .writeText(link)
      .then(() => setNotice('Trip link copied. Anyone with the link can see this trip and join it.'))
      .catch(() => setNotice(`Share this link with your party: ${link}`))
  }

  return (
    <div className="app">
      <div className="workspace">
        <PlannerHeader status={status} planSetupLabel="New trip" onPlanSetup={navigateHome} onShare={shareTrip} />
        {heading ? (
          <>
            <TripHeading
              trip={{ name: heading.name, destination: heading.destination }}
              dateLabel={heading.dateLabel}
              members={heading.members}
            />
            <TripWorkspace />
            <section className="overview">
              <div className="overview-grid">
                <PartyCard
                  members={heading.members.map((member) => ({
                    id: member.id,
                    initials: member.initials,
                    name: member.name,
                    role: member.isMe ? 'You, on this device' : 'Party member',
                  }))}
                />
              </div>
            </section>
          </>
        ) : (
          <section className="overview">
            <article className="overview-card" aria-busy={!error}>
              <p className="overview-copy mb-0">
                {error ? "Can't reach the Questline server. Still trying…" : 'Opening your trip…'}
              </p>
            </article>
          </section>
        )}
        <AppFooter />
        {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
      </div>
    </div>
  )
}
