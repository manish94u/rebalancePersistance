# Standalone Reference Simulator

This is the standard-library simulation source exported from the research
workspace. One table-environment formatting fix is recorded in
`../provenance/import-manifest.json`; numerical code is unchanged. No server,
Kubernetes, OCI SDK, or transport connection is needed.

## Run

From the repository root, with `.vnv` activated:

```bash
python simulator/run_experiments.py --steps 20 --seeds 1
python simulator/run_experiments.py --steps 3000 --seeds 5
python simulator/run_tiered_backlog_experiment.py --steps 3000 --seeds 3
```

Use seeds from 1 through 10 for the first runner. Outputs go to `output/`
beside the runners and are ignored by Git. Runs can overwrite earlier output;
keep independent run directories when retaining new experiments.

## Modules

- `environment.py`: subscription queues, connection placement, Pod accounting,
  arrivals, delivery capacity, client processing capacity, and action execution.
- `controllers.py`: static, threshold-based heuristic, and epsilon-greedy
  controllers; these receive the observation rather than full environment state.
- `dql.py`: the reference simulator's online/target networks, replay sampling,
  temporal-difference update, and DQL ablations.
- `metrics.py`: interval and per-seed measurements, summaries, CSV/LaTeX output.
- `run_experiments.py`: workload definitions and twelve compared variants.
- `run_tiered_backlog_experiment.py`: 20,000-subscription tiered initial backlog.

Backlog belongs to a subscription queue. A connection's backlog is the sum for
its assigned subscriptions; a Pod's backlog is the sum for all its assigned
subscriptions, not only those observed by one client. The client-facing state
is partial. Global statistics are for offline evaluation.

The environment models per-connection service sharing and a pressure-dependent
service factor. It does not emulate TCP packets, STOMP receipts, a real queue
service, or a Kubernetes load balancer. Generated results must be described as
simulation measurements.

## Relation to the Paper

The preserved source comments refer to the earlier simulator study. This
standalone runner is not the later proprietary deployment-adapter evaluator.
Its DQL controller should not be substituted for the paper's saved 21--32--6
network when interpreting the locked holdout. Use `../evidence/reanalyse.py`
to recompute the archived paper results and inspect the actual frozen weights.

The long-run commands create new exploratory results; running them does not
replace the paired episode evidence or establish new live-cloud performance.
