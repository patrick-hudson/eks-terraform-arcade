# How the guided missions work

The mission player adds a practice structure to the existing runbooks: define the contract, build the fixture, investigate, verify, and clean up. It covers all 14 games and ten individual incidents. Each stage gives a concrete action, an observable success condition, and a checkpoint to explain aloud. The source runbooks remain the authority for complete command sequences, prerequisites, working directories and partial-failure recovery.

Start with the mission brief and write down what success means. Run the full build section in the linked source; isolated diagnostic cards assume its exports and working copy already exist. Record the first observed failure before editing. A different error can mean that account access, network connectivity, image delivery or another prerequisite is obscuring the intended exercise.

The investigation stage has three progressively stronger hints. The first classifies the failure, the second narrows the evidence, and the third identifies the relevant contract. Existing authored hint ladders are reused; the gauntlet overview instead directs you to the chosen incident’s own ladder. Reveal the next hint only after checking the previous one. Reference solutions stay available for comparing a completed attempt or recovering from a dead end.

Each mission includes a reasoning question with plausible alternatives and an explanation returned only after an answer is submitted. These questions test boundaries: what Terraform observed versus what you want, concurrent updates versus duplicate requests, a port-forward versus normal traffic, or an empty state versus verified AWS cleanup. They are rehearsal prompts, not certification. The debrief asks for evidence, what would happen in a different situation, a production tradeoff or a prevention measure.

Verification requires more than a successful apply or a green status. The guided stages preserve the source acceptance requirements, including intended authorization denials, stable Terraform plans, actual application output, persistence and the maintenance operation itself. A compact command card may demonstrate only part of that contract; the full source acceptance remains required.

Cleanup is a distinct stage for both solved and abandoned attempts. State files must remain available until deletion is verified. Workloads and backing volumes are removed before their controllers, identities and foundation. Where a cluster is reused during an active session, it remains an explicitly running cost item; checking off a lesson does not stop AWS billing. Game 13 adds one laptop-only ingress rule to the existing arena; the new incidents reuse that arena. No extra load balancer, NAT gateway or worker is required.

The local backend loads only `web/playbooks.json` through the same regular-file reader used by the source catalog. It accepts mission identifiers, stage identifiers, a one-based hint level, or a zero-based answer index; it never accepts a filesystem path or executes a lab command. Public lessons omit hint bodies, answer indices and answer explanations. Each hint call returns only the requested layer. Answer checking returns correctness and explanation only after a selected answer is supplied. These boundaries prevent accidental spoilers in normal navigation; they are not an examination security system, and the authored files remain on your computer.

All expected cloud results describe the intended runtime contract. The mission player does not connect to AWS, inspect a cluster, grade terminal output or certify deletion. You supply the evidence. Local progress and question correctness must never be presented as an automated cloud verification result.

The focused tests cover all 24 mission IDs and 120 stages, source links and headings, nonempty task contracts, exactly three investigation hints per mission, neutral incident briefs, public-payload answer removal, requested-hint isolation, right and wrong answers, invalid parameter types/ranges, and refusal to load a symlinked catalog. The expansion checks were first observed failing on missing lessons, the public-access track mapping and manual Kubernetes cleanup; they passed after integration. These checks validate the teaching content/API shape; they do not reproduce live AWS failures.

## Explain terms without turning the lab into a vocabulary test

Use ordinary words for the symptom and the action. Introduce a necessary term with its practical meaning: a Service is the app’s stable address, an EndpointSlice lists its traffic targets, and a PVC is an app’s disk request. Keep exact field names in code so learners can find them. The [plain-English field guide](glossary.md) offers short reminders. Questions test a decision or a consequence, not whether someone memorized a label.

Every repair belongs in the working Terraform source, including Kubernetes manifests read by the exercise module. Review a saved plan before applying it. Diagnostic reads, HTTP requests and the explicit maintenance eviction drill supply evidence; they do not replace the source repair.

Network acceptance states its scope. Internal-only missions require actual Service HTTP from the diagnostic pod. Game 13 separately requires external curl from the allowed laptop, then proves that access closes during teardown. Port-forwarding is not evidence of public reachability.

## Product references

The learning flow was informed by three documented patterns, checked October 4, 2026:

- [Instruqt tracks](https://docs.instruqt.com/getting-started/quickstart) combine sequential challenges with checks. This kit adopts explicit stages and success conditions; AWS results still require the learner's terminal evidence.
- [AWS immersive learning](https://aws.amazon.com/training/digital/immersive-learning/) includes guided Builder Labs in real AWS environments. The kit similarly connects instructions to observable service behavior, while keeping the environment in your account and within the practice allowance.
- [KodeKloud Playgrounds](https://support.kodekloud.com/what-are-kodekloud-playgrounds) emphasize open exploration, distinct from guided tasks. Here, full runbooks and source remain available alongside a structured mission path.

These are product-design references, not integrations or endorsements. No subscription or hosted sandbox was added.
