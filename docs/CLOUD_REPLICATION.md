# Authorized Cloud Replication Protocol

This is a service-independent runbook for an isolated deployment. It is not a
one-command launcher for the author's private Oracle Cloud environment. The
public repository contains neither that server nor its authenticated client
adapter. Adapt the protocol to an implementation supporting the documented
telemetry and handoff semantics.

## 1. Preconditions

1. Obtain permission for the cluster, queue, event producer, subscription cohort,
   container images, and resulting workload. Use a dedicated test deployment
   and Service route, not a shared production selector.
2. Record deployment and client revisions, image digests, replica count, CPU and
   memory requests/limits, queue quotas, TTL settings, telemetry interval,
   client workers, and processing/ACK delay.
3. Register or select subscriptions before starting. Each subscription maps to
   a logical queue channel and an event-type filter. Verify the mapping rather
   than assuming the last identifier segment is globally unique.
4. Verify publisher acceptance, fanout, one delivery, processing, and an ACK
   receipt with a small smoke workload before increasing pressure.
5. Confirm the queue has a measured capacity budget. The historical environment
   used an existing 400 MB limit; a new deployment must use its actual limit.

## 2. Capacity-Bounded Publication

The initial logical event count is not the number of publisher calls. With
5,000 subscriptions matching one event type, publishing 100,000 source events
can create 500,000,000 queue copies. Queue overhead and payload size also matter.

Use a conservative budget:

`new_queue_copies <= floor((free_bytes - reserve_bytes) / measured_bytes_per_copy)`.

Then divide by the measured matching fanout to bound source events. Include
queue metadata overhead in the measured per-copy estimate. Stop or throttle
publishing when the reserve is approached. Record rejected/throttled requests
separately from accepted events. Do not assume every accepted publish has
already been enqueued on every matching channel.

Use synthetic, non-sensitive payloads with a unique trial and event ID. Keep a
publisher ledger of intended, accepted, rejected, and retried events. Avoid
unlimited backlog generation as a substitute for a controlled saturation test.

## 3. Sticky-Connection Scale-Out Scenario

1. Start the isolated subscriber deployment with one ready Pod.
2. Establish the planned persistent connections and subscriptions; record the
   actual connection-to-Pod and subscription-to-connection assignments.
3. Generate a capacity-bounded backlog and measure baseline delivery/ACK rates.
4. Scale to the fixed post-scale replica count and wait for readiness.
5. Verify existing sockets remain on their original Pod before any action.
6. Run one preregistered policy arm: unchanged placement, guarded greedy, or
   frozen DQL. Keep the same workload and resource envelope across arms.
7. Capture new probe endpoints, rejected candidates, selected/applied actions,
   handoff receipts, retained sessions, queue depth, and per-Pod load.
8. Stop publication, reconcile delivery/ACK observations, and perform bounded
   cleanup. Restore the isolated deployment and record the final state.

Repeat arms with independent trial IDs, paired workloads, and randomized or
counterbalanced execution order. Do not reuse a drained queue as the initial
state for only one policy. A single sequential trial is not a confidence
interval over independent deployments.

## 4. Required Measurement Streams

| Stream | Minimum fields |
| --- | --- |
| Workload ledger | Trial ID, event ID, event type, payload bytes, publish time/status, matching fanout |
| Queue telemetry | Timestamp, pseudonymous channel, backlog, in-flight count, storage, throttling |
| Connection telemetry | Connection/session ID, pseudonymous Pod, counts, backlog, freshness |
| Subscription lifecycle | Subscription pseudonym, source/target, standby, quiesce, activation, unsubscribe receipts |
| Policy trace | Features, feasible actions, Q-values/rule trigger, selected action, applied action, guard reason |
| Delivery ledger | Event/subscription pair, delivery attempt, processed timestamp, ACK send/receipt, retry |
| Resource telemetry | Ready Pods, CPU, memory, throttling, GC, restarts, errors, transport disconnects |

Grafana is useful for visual inspection and corroborating resource behavior.
Export the underlying metric series with timestamps and query definitions for
analysis. Dashboard screenshots alone cannot establish which subscriptions
moved, whether ACK receipts arrived, or whether a policy executed its proposal.

## 5. Probe Pressure and Admission Cases

Compare a candidate with fewer subscriptions but high backlog against one with
more subscriptions and low backlog. Register the counts, rates, and initial
queues before running. Confirm which resource is saturated instead of assuming
subscription count alone determines service capacity.

Record rejected probes as well as accepted ones. A useful result can show that
selective migration preserves ongoing connections and avoids a poor candidate;
that does not automatically prove the learning component beats the same guards
with a greedy selector. Keep the common executor and guards equal across those
arms to isolate selector differences.

## 6. TTL Comparison Under Load

1. Establish a specified connection-age distribution. To test synchronization,
   create a cohort together and document the resulting expiry spread.
2. Preload or publish the same bounded workload in each arm, with equal client
   processing settings. Keep preloaded and continuous-arrival studies separate.
3. Measure TTL on/off, synchronized versus staggered expiry where supported,
   and selective guarded migration as distinct arms.
4. Record every interrupted session, concurrent disconnect count, lost active
   subscription time, re-subscription receipt latency, and delivery/ACK gaps.
5. Report whether DQL actually migrated or stayed under its guards. The paper's
   preloaded TTL-disabled DQL arm stayed throughout; do not relabel it as a
   migration performance test.
6. Keep queue drain, cleanup, and the next trial's baseline separate. Retain
   timeout and incomplete-recovery observations instead of dropping them.

## 7. Training and Evaluation Separation

Train or tune only on the declared development workload. Persist transitions,
replay state when supported, network state, RNG state, configuration, and hashes.
Select a checkpoint using validation data, then freeze weights and exploration
before the holdout. Preserve feature ordering and action-contract compatibility.

Do not adjust a scripted baseline using the DQL actions from the same trial.
Random timing controls use an independent, fixed seed and declared jitter rule.
Retain a strong guarded-greedy baseline alongside those controls.

## 8. Closeout and Publication Evidence

Record the exact measurement window, uncertainty unit, exclusions, queue
initialization procedure, cleanup status, and remaining unresolved receipts.
Create a hash manifest for each sealed trial. Store sensitive raw evidence in
an access-controlled archive. Publish only approved pseudonymous traces and
aggregate measurements; never credentials or customer payloads.

The existing public evidence is a recorded outcome, not authorization or a
guarantee that a new infrastructure deployment will have identical performance.
