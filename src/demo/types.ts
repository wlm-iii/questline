export type Stop = { id: number; name: string; category: string; description: string; price: number; x: number; y: number; side: boolean; votes: number; time: string; lat?: number; lng?: number }
export type Trip = { name: string; date: string; destination: string; budget: number }
export type Constraints = { returnBy: string; maxWalk: number; dietary: string; mobility: string }
export type PartyVotes = Record<number, Record<string, string>>
export type WaypointInput = Omit<Stop, 'id' | 'votes' | 'lat' | 'lng'>
