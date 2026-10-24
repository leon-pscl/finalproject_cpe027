/**
 * Keeps uploaded audio in IndexedDB so a chat can still play its recording after a refresh.
 * Every function degrades to a no-op when IndexedDB is unavailable (private mode, tests).
 */
const DB_NAME = 'lectureflow-audio';
const STORE = 'recordings';

function open(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    if (typeof indexedDB === 'undefined') return resolve(null);
    try {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

async function run<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T | undefined> {
  const db = await open();
  if (!db) return undefined;
  return new Promise((resolve) => {
    try {
      const request = work(db.transaction(STORE, mode).objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(undefined);
    } catch {
      resolve(undefined);
    }
  });
}

export const saveAudio = (key: string, blob: Blob) => run('readwrite', (store) => store.put(blob, key));
export const deleteAudio = (key: string) => run('readwrite', (store) => store.delete(key));
export const loadAudio = async (key: string): Promise<Blob | undefined> => {
  const value = await run<unknown>('readonly', (store) => store.get(key));
  return value instanceof Blob ? value : undefined;
};
