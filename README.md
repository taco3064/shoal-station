# Shoal station

This repository is the canonical **Network Root** and station template for [Shoal](https://taco3064.github.io/shoal-app/), a network of independent repository reviews backed by public evidence. The Network Root supplies the initial Review Policy and the managed Review Request and Summary Workflow files. It is not itself a Reviewer Node.

A Personal GitHub Account creates a Reviewer Node by **directly forking this Network Root**. A fork of another Reviewer's fork does not qualify. In an eligible direct fork, this `README.md` becomes that Reviewer's own public Review Policy. Reviewers may change their Policy and are responsible for the criteria they publish; Shoal does not require a fixed README layout. The Review Request form and Summary Workflow are Shoal-managed files synchronized from this Network Root by `gh shoal init` without overwriting the Reviewer's `README.md`.

## Initial Review / Star Policy

This is the default Policy provided to new Reviewer Nodes. **All eight conditions are required.** They are not weighted, scored, or bonus signals. If any condition cannot be established from verifiable evidence, the result under this default Policy is **FAIL**, not a Star.

1. **Originality.** The repository demonstrates substantive original work or a meaningful original solution. Tutorial reproductions, course clones, and copies without substantive contribution do not meet this condition.
2. **Engineering evolution.** The repository exposes meaningful engineering evolution through traceable problems, decisions, corrections, tradeoffs, or iterative improvement.
3. **Claims have evidence.** Material claims about behavior, quality, architecture, performance, safety, maintainability, or capability are supported by verifiable repository evidence rather than assertion alone.
4. **CI rigor and verifiable delivery.** A coverage percentage is not required. CI must not accept a candidate with a failing required build or package result merely because a developer reports local verification. Delivery or CD has a verifiable delivered result appropriate to the repository. Where deployment details are hidden from GitHub, assess the observable delivered result without inferring those hidden details.
5. **Issue / PR design trace.** Issues and pull requests provide enough evidence to reconstruct meaningful design reasoning, problem framing, implementation decisions, or verification history.
6. **Demonstrable result / evidence chain.** A usable demonstration, artifact, published result, or other verifiable evidence chain connects the repository's claims to an observable outcome.
7. **Fork-specific evaluation.** For a fork, evaluate the substantive changes made by the fork and apply these same required conditions to its own changes, without granting credit for upstream work.
8. **Maintenance or explicit archival status.** An active repository shows meaningful maintenance within the latest six months. An inactive repository can meet this condition only if it explicitly identifies itself as an archived or historical showcase repository.
