"use client";

export type TraceInfo = {
  requestId?: string;
  traceId?: string;
  updatedAt?: number;
};

type Listener = (info: TraceInfo) => void;

let lastTrace: TraceInfo = {};
const listeners = new Set<Listener>();

export function generateRequestId(): string {
  try {
    // Browser + modern Node
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const c: any = globalThis.crypto;
    if (c?.randomUUID) return c.randomUUID();
  } catch {
    // ignore
  }
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export function setLastTrace(info: TraceInfo) {
  lastTrace = { ...lastTrace, ...info, updatedAt: Date.now() };
  listeners.forEach((l) => l(lastTrace));
}

export function getLastTrace(): TraceInfo {
  return lastTrace;
}

export function subscribeTrace(listener: Listener): () => void {
  listeners.add(listener);
  listener(lastTrace);
  return () => {
    listeners.delete(listener);
  };
}

