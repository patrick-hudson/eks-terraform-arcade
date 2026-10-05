# 10 · Layered hints

<details><summary>Hint 1 — A PVC is a request, not a disk</summary>

Check the PVC events and its StorageClass. Is there a waiting consumer, a permission error, a provisioner that never responds, or an attach failure after a PV was created? Those are different stages.
</details>

<details><summary>Hint 2 — Compare the controller contract</summary>

Compare `StorageClass.provisioner` with the installed `CSIDriver` names. A similarly named AWS provisioner is not necessarily the driver you installed. This lab uses ordinary managed nodes and the standard EBS CSI add-on.
</details>

<details><summary>Hint 3 — The immutable-field trap</summary>

The intended provisioner is `ebs.csi.aws.com`. The fixture asks a different EKS storage implementation to provision the disk. Provisioner is immutable on a StorageClass. Prove that the current PVC is unbound. Correct `candidate.yaml`; the module detects StorageClass content changes and plans its replacement. For this empty fixture, use the answer’s two-stage Terraform change to remove the failed consumer/claim, then recreate them against the correct class; an old claim can retain stale driver annotations. Keep any bound claim intact until you have a data-preserving migration or an explicitly disposable cleanup plan.
</details>
