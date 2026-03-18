# Nightly prompt usage

Use these prompts with the bounded Karpathy shell:

1. Run baseline deterministic nightly job.
2. Feed the nightly diagnostics + current settings into `karpathy_proposer_prompt.txt`.
3. Take the returned JSON patch proposal.
4. Feed the proposal + nightly diagnostics into `karpathy_critic_prompt.txt`.
5. If critic verdict is `reject`, do not run challenger.
6. If critic verdict is `approve` or `cautious_approve`, apply the patch only to the allowed bounded config files.
7. Run challenger.
8. Let the fixed Python judge accept or reject based on metrics.

## Recommended overnight cadence
- Start with 3–5 challenger attempts max per night.
- Use Sonnet-class model for proposer/critic.
- Keep all core evaluation deterministic.
- Do not allow live promotion before maturity gates are satisfied.
