"use client";

/**
 * Tiny IndexedDB store for recorded media (private by default, local to
 * this browser). Server-side encrypted storage lands with the media
 * storage phase; recordings are never uploaded without consent.
 */
const DB_NAME = "careerforge-media";
const STORE = "recordings";
const VERSION = 1;

interface Recording {
  id: string;
  applicationId: string;
  blob: Blob;
  createdAt: string;
  seconds: number;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveRecording(rec: Recording): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(rec);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function listRecordings(applicationId?: string): Promise<Recording[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => {
      const all = (req.result as Recording[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      resolve(applicationId ? all.filter((r) => r.applicationId === applicationId) : all);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function deleteRecording(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
