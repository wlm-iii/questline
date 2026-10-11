import { useCallback, useState } from 'react'
import { PlanningDesk } from './features/planning/PlanningDesk'
import { ConversationReader } from './features/planning/ConversationReader'
import { RouteGraph } from './features/planning/RouteGraph'
import { ConstraintsCard } from './features/planning/ConstraintsCard'
import { TravelCosts } from './features/planning/TravelCosts'
import { LocationCard } from './features/planning/LocationCard'
import { Overview } from './features/overview/Overview'
import { OverviewHero } from './features/overview/OverviewHero'
import { TripStats } from './features/overview/TripStats'
import { PartyCard } from './features/overview/PartyCard'
import { PreparationCard } from './features/overview/PreparationCard'
import { SetupPage } from './features/trip-setup/SetupPage'
import { TripSetupFields } from './features/trip-setup/TripSetupFields'
import { StartingPlaces } from './features/trip-setup/StartingPlaces'
import { NavigationRail } from './components/NavigationRail'
import { TripHeading } from './components/TripHeading'
import { ViewNavigation } from './components/ViewNavigation'
import { AppFooter } from './components/AppFooter'
import { Notice } from './components/Notice'
import { DialogHost } from './components/dialogs/DialogHost'
import { ImportChatDialog } from './components/dialogs/ImportChatDialog'
import { TripSettingsDialog } from './components/dialogs/TripSettingsDialog'
import { WaypointDialog } from './components/dialogs/WaypointDialog'
import { PlaceDetailsDialog } from './components/dialogs/PlaceDetailsDialog'
import { RemoveWaypointDialog } from './components/dialogs/RemoveWaypointDialog'
import type { Stop, Trip, WaypointInput } from './demo/types'
import { initialStops, sampleCoords } from './demo/data'
import { useSaved } from './lib/useSaved'
import { PlaceCard } from './features/map/PlaceCard'
import { EmptyMap } from './features/map/EmptyMap'
import { PlannerHeader } from './components/AppHeader'
import { QuestBoard } from './features/quest-board/QuestBoard'
import { TierList } from './components/TierList'
import { tiers, type Tier } from './components/tiers'
import { MapPanel } from './features/map/MapPanel'
import { googleMapsEnabled } from './features/map/config'

function App() {
  const [stops, setStops] = useSaved<Stop[]>('questline-stops', initialStops)
  const [selected, setSelected] = useState(1)
  const [tab, setTab] = useState('Waypoints')
  const [filter, setFilter] = useState('All')
  const [partyVotes, setPartyVotes] = useSaved<
    Record<number, Record<string, string>>
  >('questline-party-votes', {})
  const [voter, setVoter] = useSaved('questline-voter', 'Jerry')
  const votes = Object.fromEntries(
    Object.entries(partyVotes).map(([id, members]) => [
      id,
      members[voter] ?? '',
    ]),
  )
  const [done, setDone] = useSaved<number[]>('questline-done', [])
  const [accepted, setAccepted] = useSaved('questline-accepted', false)
  const [modal, setModal] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [notice, setNotice] = useState('')
  const [zoom, setZoom] = useState(1)
  const [trip, setTrip] = useSaved<Trip>('questline-trip', {
    name: 'A day in San Francisco',
    date: '2026-10-17',
    destination: 'San Francisco, CA',
    budget: 65,
  })
  const [notes, setNotes] = useSaved<Record<number, string>>(
    'questline-notes',
    {},
  )
  const [owners, setOwners] = useSaved<Record<number, string>>(
    'questline-owners',
    {},
  )
  const [constraints, setConstraints] = useSaved('questline-constraints', {
    returnBy: '18:00',
    maxWalk: 30,
    dietary: 'Vegetarian options',
    mobility: 'Avoid steep hikes',
  })
  const [travelMode, setTravelMode] = useSaved('questline-travel', 'Drive')
  const [gasPrice, setGasPrice] = useSaved('questline-gas', 4.5)
  const [chatDraft, setChatDraft] = useState(
    'Alex: Tartine Bakery is a must.\nMorgan: Mission Dolores Park after coffee?\nSam: Keep it under $65 each.\nJerry: We need to be back by 6.',
  )
  const [messages, setMessages] = useSaved<string[]>('questline-messages', [])
  const [ranks, setRanks] = useSaved<Record<number, Tier>>(
    'questline-tiers',
    {},
  )
  const effectiveRanks = Object.fromEntries(
    stops.map((stop) => [stop.id, ranks[stop.id] ?? (stop.side ? 'C' : 'A')]),
  ) as Record<number, Tier>
  function rankPlace(id: number, tier: Tier) {
    const nextRanks = { ...effectiveRanks, [id]: tier }
    setRanks(nextRanks)
    const next = stops.map((stop) => ({
      ...stop,
      side: tiers.indexOf(nextRanks[stop.id]) >= 3,
    }))
    next.sort(
      (a, b) => tiers.indexOf(nextRanks[a.id]) - tiers.indexOf(nextRanks[b.id]),
    )
    revise(next)
    setNotice(
      `${stops.find((stop) => stop.id === id)?.name} moved to ${tier} tier. Questline priorities updated.`,
    )
  }
  const [search, setSearch] = useState('')
  const [view, setView] = useState('Map')
  const [planned, setPlanned] = useSaved('questline-planned', false)
  const [dialog, setDialog] = useState('')
  const [editing, setEditing] = useState<Stop | null>(null)
  const current = stops.find((s) => s.id === selected) ?? stops[0]
  const total = stops
    .filter((s) => !s.side)
    .reduce((sum, s) => sum + s.price, 0)
  const revise = useCallback(
    (next: Stop[]) => {
      setStops(next)
      setAccepted(false)
    },
    [setStops, setAccepted],
  )
  function move(id: number, offset: number) {
    const next = [...stops]
    const index = next.findIndex((s) => s.id === id)
    const target = index + offset
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    revise(next)
  }
  function exportTrip() {
    const file = new Blob(
      [
        JSON.stringify(
          { trip, stops, votes: partyVotes, done, notes, owners, accepted },
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    )
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = 'questline-trip.json'
    link.click()
    URL.revokeObjectURL(url)
    setNotice('Your trip has been exported.')
  }
  function shareTrip() {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() =>
        setNotice('Demo link copied. This demo does not sync between people.'),
      )
      .catch(() =>
        setNotice('Copy the URL from your browser to share this demo.'),
      )
  }
  const main = stops.filter((s) => !s.side)
  const displayed = (tab === 'Quest log' ? main : stops)
    .filter((s) => filter === 'All' || s.category === filter)
    .filter((s) => s.name.toLowerCase().includes(search.toLowerCase()))
  function voteFor(id: number, choice: string) {
    setPartyVotes({
      ...partyVotes,
      [id]: {
        ...partyVotes[id],
        [voter]: partyVotes[id]?.[voter] === choice ? '' : choice,
      },
    })
  }
  function vote(choice: string) {
    voteFor(current.id, choice)
  }
  function buildPlan() {
    const pending = stops.filter((stop) => !stop.side)
    const ordered: Stop[] = []
    while (pending.length) {
      const highest = Math.min(
        ...pending.map((stop) => tiers.indexOf(effectiveRanks[stop.id])),
      )
      const candidates = pending.filter(
        (stop) => tiers.indexOf(effectiveRanks[stop.id]) === highest,
      )
      const previous = ordered.at(-1)
      const next = previous
        ? candidates.reduce(
            (best, stop) =>
              Math.hypot(stop.x - previous.x, stop.y - previous.y) <
              Math.hypot(best.x - previous.x, best.y - previous.y)
                ? stop
                : best,
            candidates[0],
          )
        : candidates[0]
      ordered.push(next)
      pending.splice(
        pending.findIndex((stop) => stop.id === next.id),
        1,
      )
    }
    revise([...ordered, ...stops.filter((stop) => stop.side)])
    setPlanned(true)
    setView('Map')
    setTab('Questline')
    setNotice(
      'Draft route arranged by tier priority and nearby map positions. Review, vote, and adjust together.',
    )
  }
  function closeDialog() {
    setDialog('')
    setModal(false)
  }
  function toggleSide(id: number) {
    revise(
      stops.map((stop) =>
        stop.id === id ? { ...stop, side: !stop.side } : stop,
      ),
    )
  }
  function importChat(text: string) {
    const matches = initialStops.filter((stop) =>
      text.toLowerCase().includes(stop.name.toLowerCase()),
    )
    const additions = matches.filter(
      (stop) => !stops.some((existing) => existing.id === stop.id),
    )
    if (additions.length) revise([...stops, ...additions])
    setModal(false)
    setNotice(
      matches.length
        ? `${matches.length} sample places matched; ${additions.length} added to your board.`
        : 'No sample places matched. Add a waypoint manually to include a new place.',
    )
  }
  function saveTrip(next: Trip) {
    setTrip(next)
    setDialog('')
    setNotice(
      'Trip details saved. Rebuild the route to apply planning changes.',
    )
  }
  const saveWaypoint = useCallback(
    (values: WaypointInput) => {
      const next: Stop = {
        ...values,
        id: editing?.id ?? Date.now(),
        votes: editing?.votes ?? 0,
      }
      revise(
        editing
          ? stops.map((stop) => (stop.id === editing.id ? next : stop))
          : [...stops, next],
      )
      setSelected(next.id)
      setDialog('')
      setNotice(
        editing ? 'Waypoint updated.' : 'A new possibility added to your map.',
      )
    },
    [editing, stops, revise, setSelected, setDialog, setNotice],
  )
  function removeWaypoint(id: number) {
    revise(stops.filter((stop) => stop.id !== id))
    setDone(done.filter((doneId) => doneId !== id))
    setDialog('')
    setNotice('Waypoint removed.')
  }
  function changeTab(next: string) {
    setTab(next)
    setFilter('All')
    setSearch('')
  }
  function openDetails(id: number) {
    setSelected(id)
    setDialog('details')
  }
  function addWaypoint() {
    setEditing(null)
    setDialog('waypoint')
  }
  function toggleDone(id: number) {
    setDone(
      done.includes(id)
        ? done.filter((doneId) => doneId !== id)
        : [...done, id],
    )
  }
  function acceptPlan() {
    setAccepted(true)
    changeTab('Quest log')
    setNotice('Questline accepted. Check off each stop as you go.')
  }
  function readConversation(text: string) {
    const lines = text.split('\n').filter((line) => line.trim())
    setMessages(lines)
    setNotice(`${lines.length} messages saved to the reader.`)
  }
  function showPlaceOnMap(id: number) {
    setSelected(id)
    setView('Map')
  }
  function reviewRoute() {
    setView('Map')
    setTab('Questline')
  }
  if (!planned)
    return (
      <SetupPage onBuildPlan={buildPlan}>
        <TripSetupFields
          trip={trip}
          constraints={constraints}
          travelMode={travelMode}
          onTripChange={setTrip}
          onConstraintsChange={setConstraints}
          onTravelModeChange={setTravelMode}
        />
        <StartingPlaces
          stops={stops}
          mainCount={main.length}
          total={total}
          onToggleSide={toggleSide}
        />
      </SetupPage>
    )
  return (
    <div className="app">
      <NavigationRail
        view={view}
        onViewChange={setView}
        onQuestLog={() => {
          setView('Map')
          setTab('Quest log')
        }}
      />

      <div className="workspace">
        <PlannerHeader
          onPlanSetup={() => setPlanned(false)}
          onExport={exportTrip}
          onShare={shareTrip}
        />
        <TripHeading
          trip={trip}
          onSettings={() => setDialog('settings')}
          onImport={() => setModal(true)}
        />
        <ViewNavigation
          view={view}
          accepted={accepted}
          onViewChange={setView}
        />
        {view === 'Planning desk' && (
          <PlanningDesk
            conversation={
              <ConversationReader
                stops={stops}
                messages={messages}
                chatDraft={chatDraft}
                onDraftChange={setChatDraft}
                onReadConversation={readConversation}
                onSelectPlace={showPlaceOnMap}
              />
            }
            route={
              <RouteGraph
                stops={stops}
                done={done}
                onReviewRoute={reviewRoute}
                onDetails={openDetails}
              />
            }
            priorities={
              <TierList
                options={stops}
                ranks={effectiveRanks}
                onRank={rankPlace}
                voter={voter}
                onVoter={setVoter}
                votes={partyVotes}
                onVote={voteFor}
              />
            }
            constraints={
              <ConstraintsCard
                constraints={constraints}
                onConstraintsChange={setConstraints}
              />
            }
            travel={
              <TravelCosts
                total={total}
                travelMode={travelMode}
                gasPrice={gasPrice}
                onTravelModeChange={setTravelMode}
                onGasPriceChange={setGasPrice}
              />
            }
            location={<LocationCard />}
          />
        )}
        {view === 'Overview' && (
          <Overview
            hero={
              <OverviewHero
                stopCount={stops.length}
                onExplore={() => setView('Map')}
              />
            }
            stats={
              <TripStats
                mainCount={main.length}
                total={total}
                budget={trip.budget}
                completed={
                  done.filter((id) => main.some((stop) => stop.id === id))
                    .length
                }
              />
            }
            party={<PartyCard />}
            preparation={
              <PreparationCard
                travelMode={travelMode}
                onSettings={() => setDialog('settings')}
                onReviewRoute={reviewRoute}
                onExport={exportTrip}
              />
            }
          />
        )}
        <div className={`planner ${view !== 'Map' ? 'hidden' : ''}`}>
          <MapPanel
            stops={stops}
            mapStops={stops.map((s) => ({
              id: s.id,
              name: s.name,
              side: s.side,
              done: done.includes(s.id),
              lat: s.lat ?? sampleCoords[s.id]?.lat,
              lng: s.lng ?? sampleCoords[s.id]?.lng,
            }))}
            selectedId={selected}
            done={done}
            zoom={zoom}
            googleMapsEnabled={googleMapsEnabled}
            onSelect={setSelected}
            onZoomIn={() => setZoom(Math.min(1.5, zoom + 0.1))}
            onZoomOut={() => setZoom(Math.max(1, zoom - 0.1))}
            onReset={() => setZoom(1)}
          >
            {current ? (
              <PlaceCard
                className="place-card"
                current={current}
                number={String(
                  stops.findIndex((s) => s.id === current.id) + 1,
                ).padStart(2, '0')}
                voter={voter}
                vote={votes[current.id]}
                onVoterChange={setVoter}
                onVote={vote}
                onView={() => setDialog('details')}
                onToggleSide={() => toggleSide(current.id)}
              />
            ) : (
              <EmptyMap onAddWaypoint={addWaypoint} />
            )}
          </MapPanel>
          <QuestBoard
            stops={stops}
            main={main}
            displayed={displayed}
            selected={selected}
            tab={tab}
            filter={filter}
            search={search}
            partyVotes={partyVotes}
            owners={owners}
            done={done}
            accepted={accepted}
            total={total}
            trip={trip}
            onTabChange={changeTab}
            onFilterChange={setFilter}
            onSearchChange={setSearch}
            onSelect={setSelected}
            onMove={move}
            onDetails={openDetails}
            onToggleDone={toggleDone}
            onAddWaypoint={addWaypoint}
            onBuildPlan={buildPlan}
            onAccept={acceptPlan}
          />
        </div>
        <AppFooter />
        {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
        <DialogHost open={Boolean(dialog || modal)} onClose={closeDialog}>
          {modal && (
            <ImportChatDialog
              transcript={transcript}
              matches={initialStops.filter((stop) =>
                transcript.toLowerCase().includes(stop.name.toLowerCase()),
              )}
              onTranscriptChange={setTranscript}
              onImport={importChat}
            />
          )}
          {dialog === 'settings' && (
            <TripSettingsDialog trip={trip} onSaveTrip={saveTrip} />
          )}
          {dialog === 'waypoint' && (
            <WaypointDialog
              editing={editing}
              onSaveWaypoint={saveWaypoint}
            />
          )}
          {dialog === 'details' && current && (
            <PlaceDetailsDialog
              current={current}
              interested={
                Object.values(partyVotes[current.id] ?? {}).filter(
                  (v) => v === 'I’m in',
                ).length
              }
              owner={owners[current.id] || ''}
              note={notes[current.id] || ''}
              onOwnerChange={(name) =>
                setOwners({ ...owners, [current.id]: name })
              }
              onNoteChange={(text) =>
                setNotes({ ...notes, [current.id]: text })
              }
              onEdit={() => {
                setEditing(current)
                setDialog('waypoint')
              }}
              onToggleSide={() => {
                toggleSide(current.id)
                setNotice('Questline updated. Review and accept the new draft.')
              }}
              onRemove={() => setDialog('remove')}
            />
          )}
          {dialog === 'remove' && current && (
            <RemoveWaypointDialog
              current={current}
              onKeep={() => setDialog('details')}
              onRemove={() => removeWaypoint(current.id)}
            />
          )}
        </DialogHost>
      </div>
    </div>
  )
}
export default App
