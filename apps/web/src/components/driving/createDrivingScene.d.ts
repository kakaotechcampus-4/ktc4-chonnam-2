export interface DrivingScene {
  dispose(): void
  /** Suspend rendering and simulation without changing the user's pause or gear selection. */
  setActive(active: boolean): void
}
/** Mount the local Three.js scene; dispose releases all resources. */
export function createDrivingScene(root: HTMLDivElement, onUnavailable: () => void): DrivingScene
