import { useState } from 'react'
import type { Uuid } from './api'
import { isDemoPath, TripProvider, usePathname, useTripSession } from './state'
import App from './App'
import { CreateTripPage } from './features/trip-setup/CreateTripPage'
import { JoinTripPage } from './features/trip-setup/JoinTripPage'
import { TripApp } from './trip/TripApp'

export function Root() {
  const pathname = usePathname()
  return isDemoPath(pathname) ? <App /> : <LiveTrip />
}

function LiveTrip() {
  const { state, createTrip, joinTrip, leaveTrip } = useTripSession()
  const [rejectedTripId, setRejectedTripId] = useState<Uuid | null>(null)

  if (state.status === 'no-trip') {
    return <CreateTripPage createTrip={createTrip} resumableTripId={state.resumableTripId} />
  }
  if (state.status === 'needs-join') {
    return <JoinTripPage key={state.tripId} joinTrip={joinTrip} rejoin={rejectedTripId === state.tripId} />
  }
  const { session } = state
  return (
    <TripProvider
      session={session}
      onUnauthorized={() => {
        setRejectedTripId(session.tripId)
        leaveTrip()
      }}
    >
      <TripApp />
    </TripProvider>
  )
}
