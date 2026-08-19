# Subscription automation notes

GitHub Actions supports scheduled workflow cron expressions with a minimum interval of five minutes. Scheduled executions are best effort and can be delayed under high load, especially at the start of an hour. Therefore Kaveh should not promise an exact start time or depend on one-minute freshness.

For the first GitHub-hosted edition, Kaveh will run every 15 minutes at an off-hour minute. This is faster than the former two-hour cadence while leaving room for bounded Xray probes, network retries, and occasional scheduler delay. It will use one concurrency group, no overlapping work, a hard timeout, a small candidate cap, and a commit only when generated artifacts differ.

GitHub-managed scheduling is appropriate for a bounded starter job, but not a strict availability guarantee. A persistent deployment should be considered later only if the product requires an actual sub-five-minute latency objective.

References:
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
