# Frozen DQL Model

## Identity and Architecture

- File: `evidence/model/frozen-policy.json`.
- SHA-256: `3e68371d848eca85ec0b87c7c7dd831ea3ec953e2c1bd51c0d79871c7ef3e1e1`.
- Network: 21 inputs, 32 ReLU hidden units, six linear outputs.
- Parameters per network copy: `21*32 + 32 + 32*6 + 6 = 902`.
- Both online and target copies are stored. The online network selects actions;
  the delayed target copy supplies training targets.
- Output order: `stay, rebN, rebG, scale+, scale-, migrate`.

The feature order and normalization are defined in Appendix D and
`paper/model-implementation-appendix.tex`. Do not reorder features, substitute
cluster-wide telemetry for partial observations, or change normalization while
reusing the weights.

## Evaluation and Persistence

The archived checkpoint has exploration `epsilon=0`, training disabled, and
9,985 recorded training updates. The training process used 10,000 transitions;
updates start only when the replay batch is available. The selected candidate
came from the recorded training/validation process, not the evaluation seeds.

The implementation configuration includes uniform replay capacity 5,000,
batch size 16, learning rate 0.001, discount 0.99, and target copies every 250
updates. Check the original manifest before using these settings for a new run.

The public inference utility is read-only. A new training run must write to a
different directory and record a new checkpoint digest, training seeds,
transition count, action contract, feature schema, and validation procedure.
Do not replace the frozen checkpoint when exploring a new reward configuration.

## Action-Contract Compatibility

The saved checkpoint omits a newer action-contract identifier. It belongs to
the legacy open-only scale-up contract. A later executor introduced
cap-restoring scale-up, which changes the meaning and cost of that action.
Do not silently use the old weights with unrestricted newer action semantics.

The loaded cloud trial disabled both connection scaling actions and permitted
only `stay`, `rebN`, `rebG`, and `migrate`. Its settings are preserved in
`evidence/model/loaded-trial-settings.json`.

An action-value maximum does not bypass telemetry freshness, connection caps,
cooldown, projected pressure improvement, or the receipt-gated executor.

## Recorded Reward Settings

The loaded-trial settings store the weights on backlog, backlog growth, Pod
pressure, connection imbalance, migration cost, connection cost, and throughput
as `0.20, 0.15, 0.20, 0.15, 0.10, 0.05, 0.15` respectively. The first six are
penalties and throughput is a benefit. These weights do not imply that every
metric must improve simultaneously.

Pressure weights for subscription count, cumulative backlog, threshold backlog,
and reliability risk are `0.30, 0.25, 0.20, 0.25`. Count and backlog imbalance
weights are each `0.5`. See the preserved JSON for reference scales and guards.

## Evidence Boundaries

The model supports the reported workload-specific results. The mixed-workload
holdout improved reward and count balance, but not every throughput/backlog
metric. In the saturated scale-out model, both guarded selectors made added
capacity useful. The live trial confirms selected migrations and receipt
accounting; it is not a universal cloud throughput benchmark.

The `simulator/oaes_rebalancing_sim/dql.py` controller belongs to the earlier
reference simulator. It is not a drop-in loader for this saved deployment model.
