export interface DrivingScene {
  dispose(): void
  /** Suspend the embedded game when returning to the thumbnail or leaving the viewport. */
  setActive(active: boolean): void
}
/** Load the local game document after opt-in; dispose releases its resources. */
export function createDrivingScene(root: HTMLDivElement, onUnavailable: () => void, onReady?: () => void): DrivingScene
