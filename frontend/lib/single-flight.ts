/** Reuse an unfinished write so repeated save triggers cannot create duplicate records. */
export function singleFlight<T>(slot: { current: Promise<T> | null }, write: () => Promise<T>): Promise<T> {
  if (slot.current) return slot.current;
  const pending = Promise.resolve().then(write).finally(() => {
    if (slot.current === pending) slot.current = null;
  });
  slot.current = pending;
  return pending;
}
