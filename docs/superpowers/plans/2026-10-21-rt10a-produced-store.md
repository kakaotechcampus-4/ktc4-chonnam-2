# RT-10(a) produced object gate

Status: IN_PROGRESS. Refs #297 (RT-10(a)).

The requested slice implements Consult #346 O-1–O-3 within existing T1 atomicity and the existing Case ProducedReader callable. Latest develop at start: `596e8a162b71949e7b3189e994921bb6247aac4b`. No Contract, Accepted Decision, Baseline or other Owner public surface changes are planned.

1. RED: pin opaque JSON snapshots, stable execution/ordinal refs, validation, reader behavior, and independent MySQL acceptance inventory before implementation.
2. GREEN: add frozen runtime_0005 migration and common produced object storage; append only, exact replay accepted, conflicting replay rejected. Existing external produced refs remain valid without duplication into this store.
3. RED/GREEN: attach optional payload objects to internal HandlerResult, bind generated refs before T1 persistence retries, persist using the terminal Connection, verify durable payloads on unknown COMMIT recovery. Preserve lease and cancellation rules.
4. Verify with real MySQL: terminal/payload atomicity, rollback on either write, duplicates/conflicts/concurrency, lost COMMIT acknowledgement, redelivery and fresh process reads. Reader returns one opaque dict by default; multi-object assembly is injected by the caller, with no domain imports in storage.
5. Add independent required parameter/family inventory and JSON/JUnit omission mutations without relaxing existing checks, deadlines or workflow.
6. Run relevant regression, strict MySQL report and boundary/Contract checks. Record raw failures and successful retries separately, source hashes and limitations in the handoff note and append-only Implementation Log.
7. Leave all delivery changes uncommitted and unstaged for independent review; do not register real handlers or implement Case adapter/8-13, export or RT-11.

Review focus: missing payload on recovered terminal; changed payload on replay; stolen lease; multiple objects with external refs; producer mutation; read by another process without memory state; metadata/family or JUnit omission cannot pass the gate.
