# Shoal station

This repository is the canonical **Network Root** for [Shoal](https://taco3064.github.io/shoal-app/), a network of independent repository reviews backed by public evidence. Because the Network Root belongs to a Personal GitHub Account, this repository is also its owner's **Reviewer Node**. It receives Review Requests through its Issues and runs the canonical Reviewer Summary Workflow. Its GitHub Repository ID is the stable Reviewer Node identity; being the Network Root does not exempt it from Shoal's Protocol or eligibility checks.

For this Root owner, this `README.md` is the **live Review Policy source of truth**. Changes to it change the Root owner's Policy and the initial Policy that future direct forks receive. Existing forks retain their own independently owned README and are not rewritten when the Root Policy changes.

Other Personal GitHub Accounts create Reviewer Nodes by **directly forking this Network Root**. A fork of another Reviewer's fork does not qualify, nor does an Organization-owned repository. In a direct fork, the copied `README.md` becomes that Reviewer's own public Review Policy. Reviewers may change their Policy and are responsible for the criteria they publish; Shoal does not require a fixed README layout. The Review Request form and Summary Workflow are Shoal-managed files synchronized from this Network Root to direct forks by `gh shoal init` without overwriting the Reviewer's `README.md`. The Root itself is the canonical source of those files and does not run `gh shoal init` against itself.

## Initial Review / Star Policy

This is the Root owner's current Review Policy and the initial Policy provided to future direct forks. **All eight conditions are required.** They are not weighted, scored, or bonus signals. If any condition cannot be established from verifiable evidence, the result under this Policy is **FAIL**, not a Star.

1. **Originality.** The repository demonstrates substantive original work or a meaningful original solution. Tutorial reproductions, course clones, and copies without substantive contribution do not meet this condition.
2. **Engineering evolution.** The repository exposes meaningful engineering evolution through traceable problems, decisions, corrections, tradeoffs, or iterative improvement.
3. **Claims have evidence.** Material claims about behavior, quality, architecture, performance, safety, maintainability, or capability are supported by verifiable repository evidence rather than assertion alone.
4. **CI rigor and verifiable delivery.** A coverage percentage is not required. CI must not accept a candidate with a failing required build or package result merely because a developer reports local verification. Delivery or CD has a verifiable delivered result appropriate to the repository. Where deployment details are hidden from GitHub, assess the observable delivered result without inferring those hidden details.
5. **Issue / PR design trace.** Issues and pull requests provide enough evidence to reconstruct meaningful design reasoning, problem framing, implementation decisions, or verification history.
6. **Demonstrable result / evidence chain.** A usable demonstration, artifact, published result, or other verifiable evidence chain connects the repository's claims to an observable outcome.
7. **Fork-specific evaluation.** For a fork, evaluate the substantive changes made by the fork and apply these same required conditions to its own changes, without granting credit for upstream work.
8. **Maintenance or explicit archival status.** An active repository shows meaningful maintenance within the latest six months. An inactive repository can meet this condition only if it explicitly identifies itself as an archived or historical showcase repository.
