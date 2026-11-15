import React, { useEffect, useState } from 'react';
import type { StationSnapshot } from '../types/morph.ts';
import { formatTimestamp, DISPLAY_TIME_ZONE } from './EvidenceImage.tsx';

export function ReplayPanel({ snapshot, onSeek, onOpenCycle }: {
  snapshot: StationSnapshot; onSeek: (index: number) => void; onOpenCycle: (id: string) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const replay = snapshot.replay!;
  useEffect(() => {
    if (!playing) return;
    if (replay.cursor >= replay.count - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => onSeek(replay.cursor + 1), 1000);
    return () => window.clearTimeout(timer);
  }, [playing, replay.cursor, replay.count, onSeek]);
  const event = replay.event;
  return <section aria-label="Read-only historical replay" className="mb-6 rounded-lg border border-[#6c5840] bg-[#1b1914] p-4 text-[12px]">
    <h2 className="font-medium text-[#C7A477]">Read-only historical replay</h2>
    <p className="my-2 text-[#A7A39A]">Source: {snapshot.sourceMode} · Saved session totals remain fixed. Playback only browses the original events; it does not execute tasks. Snapshot received {formatTimestamp(replay.savedAt)} · {DISPLAY_TIME_ZONE}.</p>
    {event ? <>
      <div className="my-3 flex flex-wrap items-center gap-3">
        <button type="button" aria-label="Previous replay event" disabled={!replay.cursor} onClick={()=>onSeek(replay.cursor-1)} className="rounded border border-[#6c5840] px-3 py-1.5 disabled:opacity-40">Previous</button>
        <button type="button" onClick={()=>setPlaying(v=>!v)} disabled={replay.cursor>=replay.count-1} className="rounded border border-[#6c5840] px-3 py-1.5 disabled:opacity-40">{playing?'Pause replay':'Play replay'}</button>
        <button type="button" aria-label="Next replay event" disabled={replay.cursor>=replay.count-1} onClick={()=>onSeek(replay.cursor+1)} className="rounded border border-[#6c5840] px-3 py-1.5 disabled:opacity-40">Next</button>
        <span>Event {replay.cursor+1} of {replay.count} · Original sequence {event.sequence}</span>
      </div>
      <input aria-label="Replay event position" type="range" min={0} max={replay.count-1} value={replay.cursor} onChange={e=>onSeek(Number(e.target.value))} className="w-full"/>
      <p className="my-2">{event.type} · {event.entityId} · Revision {event.entityRevision} · {formatTimestamp(event.occurredAt)}</p>
      <details><summary className="cursor-pointer text-[#C7A477]">Original event values</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-[10px]">{JSON.stringify(event.payload,null,2)}</pre></details>
      {event.cycleId && <button type="button" onClick={()=>onOpenCycle(event.cycleId!)} className="mt-3 text-[#C7A477] underline">Open saved cycle trace</button>}
    </> : <p>No recorded events in this session.</p>}
  </section>;
}
