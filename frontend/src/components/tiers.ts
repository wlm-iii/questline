export const tiers = ['S', 'A', 'B', 'C', 'D', 'E', 'F'] as const
export type Tier = typeof tiers[number]
