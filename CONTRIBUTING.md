# Contributing

1. Work on a branch and keep manuscript changes separate from new experiments.
2. Preserve `evidence/`, the original reference manuscript, and imported figure
   values. New runs belong in their own identified artifact directory.
3. Record code revision, configuration, seeds, checkpoint hash, action contract,
   workload initialization, evaluation window, and analysis unit.
4. Keep the strong guarded-greedy comparator distinct from ad-hoc scripted
   schedules. Never tune a comparator using the test policy's realized actions.
5. Report paired estimates and all preregistered metrics, including tradeoffs.
6. Run the documented verification and tests before proposing a change.
7. Scan staged files and archives for credentials, private endpoints, raw
   subscription identifiers, and payloads before upload. Do not add raw cloud
   databases or a whole internal source checkout.

The default CI validates offline artifacts only. It does not create cloud
resources, publish events, retrain models, or regenerate measured statistics.

A license for additional code or data must be selected by the rights holder.
Do not infer permission to redistribute employer-owned service code from this
repository's publication artifacts.
