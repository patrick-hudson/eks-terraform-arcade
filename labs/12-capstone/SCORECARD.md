# Interview scorecard — 100 points

Candidate: __________________  Date: __________________
Account/region checked: __________________  Incident: __________________
Start/end: __________________  Estimated incremental cost: __________________

| Area | Evidence required | Maximum | Awarded |
|---|---|---:|---:|
| Foundation | Plan/state boundaries 5; dependency/network reasoning 5; current cost model and account/context checks 5 | 15 | |
| Application | Healthy rollout and working request 8; probes/resources explanation 6; restricted RBAC permitted and denied checks 6 | 20 | |
| AWS identity | Successful allowed request 5; expected denial 5; trust/association/permission explanation 5 | 15 | |
| Storage | Marker survives pod replacement 5; zone/binding/reclaim explanation 5 | 10 | |
| Incident | Evidence before mutation 5; causal diagnosis 5; minimal repair 5; functional verification and prevention 5 | 20 | |
| Change | Observable intended change 4; controlled rollout 3; concrete rollback explanation/demo 3 | 10 | |
| Teardown | Correct dependency order 4; cloud leftovers checked 4; cost/billing follow-up understood 2 | 10 | |
| **Total** | | **100** | |

Use these bands to guide the next practice session, not as hiring predictions: 85–100 = repeat under a tighter clock and defend tradeoffs; 70–84 = repeat the weakest boundary without hints; below 70 = replay the component games, then retry the capstone.

A result is **incomplete regardless of score** while known chargeable lab resources remain without an active cleanup attempt. If deletion is blocked, record the exact resource, error, current cost exposure, and next repair action; do not erase the state. If the timer expires during deletion, keep working.

Interview follow-ups:

1. A Terraform plan proposes replacing a resource containing data. What must you establish before approval?
2. A pod can read one bucket but cannot list buckets. Is this a failure or successful least privilege?
3. A pod says Running but clients time out. What do you inspect next, and in what order?
4. Why might adding a second node fail to fix a Pending pod?
5. What distinguishes node pressure, OOMKilled, and an application exit?
6. How can a PodDisruptionBudget block an upgrade without protecting against node failure?
7. What proves that a PVC's backing volume was removed? What changes for Retain?
8. How do you keep a Terraform provider from losing connectivity before Kubernetes cleanup completes?
9. Which parts of this lab's $20 cost target are enforced, and which are estimates or alerts?
10. After Terraform reports zero remaining resources, what could still be billing outside its state?

Notes / decisive evidence:

____________________________________________________________

____________________________________________________________
