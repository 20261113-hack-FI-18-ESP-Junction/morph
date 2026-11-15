import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import type { DashboardState, SessionExport, Snapshot } from '@morph/station-client';
import { projectM06State } from './m06Projection.ts';
import { loadPendingReview, preservePendingReview } from './pendingReview.ts';
import { filterHistory, historyPage, replaySnapshot, type HistoryFilters } from './history.ts';

const read = <T>(name:string):T => JSON.parse(readFileSync(new URL(`../../../verification/fixtures/${name}`,import.meta.url),'utf8'));
const data = read<SessionExport>('sample-export.json');
const snapshot = read<Snapshot>('sample-snapshot.json');
const state:DashboardState={selection:{sourceMode:'simulation'},connection:'connected',stream:'connected',stale:false,error:null,
  receivedAt:'2026-11-14T16:30:00Z',lastEventSequence:50,session:snapshot.session,sessions:[snapshot.session!],snapshot,metrics:data.metrics,
  cycles:null,currentDetail:null,detail:null,cameras:null,sessionExport:data};
const source=projectM06State(state);
const filters:HistoryFilters={query:'',outcome:'all',reference:'all',startedAfter:'',startedBefore:'',model:'',error:''};

test('history combines persisted outcome, retry, label, model, error and UTC date filters',()=>{
  const retry=filterHistory(source,{...filters,outcome:'retry'});
  assert.deepEqual(retry.map(c=>c.id),['demo:retry']);
  assert.equal(filterHistory(source,{...filters,query:'retry',reference:'labeled'}).length,1);
  assert.equal(filterHistory(source,{...filters,query:'retry',reference:'unlabeled'}).length,0);
  assert.equal(filterHistory(source,{...filters,startedAfter:'2027-01-01'}).length,0);
  assert.equal(filterHistory(source,{...filters,startedBefore:'2025-01-01'}).length,0);
  const error=source.attempts.find(a=>a.errorCode)!;
  assert.ok(filterHistory(source,{...filters,error:error.errorCode!}).some(c=>c.id===error.cycleId));
  const model=source.modelRuns![0]!;
  assert.ok(filterHistory(source,{...filters,model:model.modelId}).some(c=>c.id===model.cycleId));
  assert.equal(filterHistory(source,{...filters,error:'absent-code'}).length,0);
});

test('history pagination traverses every matching ID once and clamps after filters shrink',()=>{
  const records=Array.from({length:37},(_,i)=>({id:`cycle-${i}`}));
  const first=historyPage(records,0,10); assert.equal(first.pages,4);
  const ids=Array.from({length:4},(_,page)=>historyPage(records,page,10).items).flat().map(x=>x.id);
  assert.deepEqual(ids,records.map(x=>x.id));assert.equal(new Set(ids).size,37);
  assert.equal(historyPage(records.slice(0,2),3,10).page,0);
  assert.deepEqual(historyPage([],9,10).items,[]);
});

test('replay visits original event values and revisions while preserving all records and backend counters',()=>{
  const before=JSON.stringify(source);
  const events=[...source.recentEvents].sort((a,b)=>a.sequence-b.sequence);
  for(let cursor=0;cursor<events.length;cursor++){
    const replay=replaySnapshot(source,cursor);
    assert.equal(replay.viewMode,'replay');assert.equal(replay.canControl,false);
    assert.deepEqual(replay.replay?.event,events[cursor]);
    for(const key of ['cycles','attempts','recentEvents','metrics','lastEventSequence'] as const) assert.deepEqual(replay[key],source[key]);
  }
  assert.equal(JSON.stringify(source),before);
  assert.equal(replaySnapshot(source,9999).replay?.cursor,events.length-1);
  assert.throws(()=>replaySnapshot({...source,activeSession:null}));
});

test('an uncertain review survives reload unchanged and malformed storage cannot become a submission',()=>{
  const values=new Map<string,string>();
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);}};
  const request={id:'review-1',eventId:'event-1',expectedRevision:2,authorId:'operator',reason:'Independent review',createdAt:'2026-11-14T20:00:00Z'};
  preservePendingReview(storage,'cycle',request);
  assert.deepEqual(loadPendingReview(storage,'cycle'),{request,invalid:false});
  request.expectedRevision=9;
  assert.equal(loadPendingReview(storage,'cycle').request?.expectedRevision,2);
  for(const invalid of ['{','null','[]',JSON.stringify({...request,eventId:'../invalid'})]){
    values.set('cycle',invalid);assert.deepEqual(loadPendingReview(storage,'cycle'),{request:null,invalid:true});
  }
  assert.throws(()=>preservePendingReview({getItem:()=>null,setItem:()=>{}},'cycle',request));
});
