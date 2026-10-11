import { useMemo, useState } from 'react'
import { navigateHome, tripUrl, useTrip } from '../state'
import { PlannerHeader } from '../components/AppHeader'
import { NavigationRail } from '../components/NavigationRail'
import { TripHeading } from '../components/TripHeading'
import { ViewNavigation } from '../components/ViewNavigation'
import { AppFooter } from '../components/AppFooter'
import { Notice } from '../components/Notice'
import { copyText } from '../lib/copyText'
import { useSaved } from '../lib/useSaved'
import { PartyCard } from '../features/overview/PartyCard'
import { workspaceView } from './adapters'
import { ImportChat } from './ImportChat'
import { tripHeadingFromSnapshot } from './tripHeadingAdapter'
import { TripWorkspace } from './TripWorkspace'
import type { BoardTab } from './ui/TripBoard'
import { TripOverview } from './ui/TripOverview'
import { TripPlanningDesk } from './ui/TripPlanningDesk'

type View = 'Map' | 'Overview' | 'Planning desk'
const views: View[] = ['Map', 'Overview', 'Planning desk']

function readView(tripId: string): View {
  try {
    const saved = localStorage.getItem(`questline-view:${tripId}`)
    return views.includes(saved as View) ? (saved as View) : 'Map'
  } catch {
    return 'Map'
  }
}

function writeView(tripId: string, view: View) {
  try {
    localStorage.setItem(`questline-view:${tripId}`, view)
  } catch {
    /* Storage may be unavailable in private sessions. */
  }
}

/** The live trip shell. Must render inside `<TripProvider>`. */
export function TripApp() {
  const { session, snapshot, error } = useTrip()
  const [notice, setNotice] = useState('')
  const [view, setViewState] = useState<View>(() => readView(session.tripId))
  const [tab, setTab] = useState<BoardTab>('Waypoints')
  const [importOpen, setImportOpen] = useState(false)
  const [travelMode, setTravelMode] = useSaved('questline-device-travel', 'Drive')
  const heading = useMemo(
    () => (snapshot ? tripHeadingFromSnapshot(snapshot, session.memberId) : null),
    [snapshot, session.memberId],
  )
  const live = useMemo(
    () => (snapshot ? workspaceView(snapshot, null, null, session.memberId) : null),
    [snapshot, session.memberId],
  )
  const status = snapshot ? (error ? 'Reconnecting…' : 'Live') : error ? 'Connecting…' : 'Loading…'
  const me = heading?.members.find(member => member.isMe)
  const party = (heading?.members ?? []).map(member => ({
    id: member.id,
    initials: member.initials,
    name: member.name,
    role: member.isMe ? 'You, on this device' : 'Party member',
  }))

  function setView(next: string) {
    if (!views.includes(next as View)) return
    setViewState(next as View)
    writeView(session.tripId, next as View)
  }

  function openOnMap(nextTab: BoardTab) {
    setTab(nextTab)
    setView('Map')
  }

  function shareTrip() {
    const link = tripUrl(session.tripId)
    void copyText(link).then((copied) =>
      setNotice(
        copied
          ? 'Trip link copied. Anyone with the link can see this trip and join it.'
          : `Share this link with your party: ${link}`,
      ),
    )
  }

  /**
   * Copies the link command with the bare trip ID. Messages splits a pasted text that ends in a URL
   * into two messages, so `@questline link <share link>` would reach the relay without its link.
   */
  function linkChat() {
    const command = `@questline link ${session.tripId}`
    void copyText(command).then((copied) =>
      setNotice(
        copied
          ? 'Copied. Paste it into your iMessage group and send it to link the chat to this trip.'
          : `Send this in your iMessage group: ${command}`,
      ),
    )
  }

  return (
    <div className="app">
      <NavigationRail view={view} initials={me?.initials} onViewChange={setView} onQuestLog={() => openOnMap('Quest log')} />
      <div className="workspace">
        <PlannerHeader status={status} planSetupLabel="New trip" onPlanSetup={navigateHome} onShare={shareTrip} onLinkChat={linkChat} />
        {heading && live && snapshot ? (
          <>
            <TripHeading
              trip={{ name: heading.name, destination: heading.destination }}
              dateLabel={heading.dateLabel}
              members={heading.members}
              onImport={() => setImportOpen(true)}
            />
            <ViewNavigation
              view={view}
              accepted={live.build.plan?.accepted ?? false}
              status={`${live.build.plan?.accepted ? '✓ Questline accepted' : '◌ Draft questline'} · Shared with your party`}
              onViewChange={setView}
            />
            {view === 'Overview' && (
              <TripOverview
                tripId={session.tripId}
                view={live}
                party={party}
                travelMode={travelMode}
                onExplore={() => setView('Map')}
                onReviewRoute={() => openOnMap('Questline')}
              />
            )}
            {view === 'Planning desk' && (
              <TripPlanningDesk
                tripId={session.tripId}
                snapshot={snapshot}
                view={live}
                myName={me?.name ?? ''}
                travelMode={travelMode}
                onTravelModeChange={setTravelMode}
                onImport={() => setImportOpen(true)}
                onShowPlace={() => openOnMap('Waypoints')}
                onReviewRoute={() => openOnMap('Questline')}
                onError={setNotice}
              />
            )}
            <div className={view === 'Map' ? '' : 'hidden'}>
              <TripWorkspace tab={tab} onTabChange={setTab} onImport={() => setImportOpen(true)} />
            </div>
            {view === 'Map' && (
              <section className="overview">
                <div className="overview-grid">
                  <PartyCard members={party} />
                </div>
              </section>
            )}
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
        <ImportChat open={importOpen} onClose={() => setImportOpen(false)} />
        {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
      </div>
    </div>
  )
}
