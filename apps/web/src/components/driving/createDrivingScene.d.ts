/** Mount the local Three.js scene; the returned function releases all resources. */
export function createDrivingScene(root: HTMLDivElement, onUnavailable: () => void): () => void
