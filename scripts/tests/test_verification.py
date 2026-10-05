"""Verification contracts exercise mocked processes, never a live AWS account."""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from verification import Options, collect_receipt, exit_code, write_receipt, ProcessRunner, _memory_bytes


class FakeRunner:
    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def run(self, argv):
        self.calls.append(argv)
        key = self.key(argv)
        result = self.overrides.get(key, FIXTURES.get(key))
        if result is None:
            raise AssertionError(f"Unexpected process: {argv}")
        if isinstance(result, tuple):
            code, out, err = result
        else:
            code, out, err = 0, json.dumps(result), ""
        return subprocess.CompletedProcess(argv, code, out, err)

    @staticmethod
    def key(argv):
        if argv[0] == "aws":
            return tuple(argv[7:])
        # Strip fixed global options, generated kubeconfig and namespace.
        args = argv[1:]
        for flag in ("--context", "--request-timeout", "--kubeconfig", "-n"):
            while flag in args:
                i = args.index(flag)
                args = args[:i] + args[i+2:]
        return tuple(args)


CLUSTER = {"cluster": {"status": "ACTIVE", "version": "1.37", "endpoint": "https://example.eks.amazonaws.com", "certificateAuthority": {"data": "dGVzdA=="}, "upgradePolicy": {"supportType": "STANDARD"}, "resourcesVpcConfig": {"endpointPrivateAccess": True, "endpointPublicAccess": True, "publicAccessCidrs": ["203.0.113.1/32"]}}}
DEPLOY = {"metadata": {"generation": 2}, "spec": {"replicas": 1, "template": {"spec": {"containers": [{"name": "app", "readinessProbe": {"httpGet": {"path": "/", "port": "http"}}, "resources": {"limits": {"memory": "64Mi"}}}]}}}, "status": {"observedGeneration": 2, "replicas": 1, "updatedReplicas": 1, "availableReplicas": 1, "readyReplicas": 1}}
PODS = {"items": [{"metadata": {"name": "app-abc"}, "spec": {"nodeName": "node-a"}, "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}], "containerStatuses": [{"name": "app", "ready": True, "restartCount": 0, "state": {"running": {"startedAt": "2020-01-01T00:00:00Z"}}}]}}]}
FIXTURES = {
    ("sts", "get-caller-identity"): {"Account": "123456789012"},
    ("eks", "describe-cluster", "--name", "tfeks-arcade"): CLUSTER,
    ("config", "view", "--minify", "-o", "json"): {"clusters": [{"cluster": {"server": CLUSTER["cluster"]["endpoint"]}}]},
    ("get", "deployment", "app", "-o", "json"): DEPLOY,
    ("get", "pods", "-l", "app=incident", "-o", "json"): PODS,
    ("get", "service", "app", "-o", "json"): {"spec": {"type": "ClusterIP", "selector": {"app": "incident"}, "ports": [{"port": 8080, "targetPort": "http"}]}},
    ("get", "endpointslices", "-l", "kubernetes.io/service-name=app", "-o", "json"): {"items": [{"ports": [{"port": 8080}], "endpoints": [{"addresses": ["10.0.1.1"], "conditions": {"ready": True}}]}]},
    ("get", "namespace", "arcade-incident-01", "--ignore-not-found", "-o", "json"): (0, "", ""),
}


def options(lab="11-incident-gauntlet/scenario-01", phase="verify"):
    return Options(lab=lab, phase=phase, profile="arcade", expected_account="123456789012", region="us-east-1", cluster="tfeks-arcade", context="arcade-lab")


class ReceiptTests(unittest.TestCase):
    def test_memory_quantity_conversion_valid_and_invalid_values(self):
        for value, expected in (("64Mi", 64 * 1024**2), ("0.5Gi", 512 * 1024**2),
                                ("65536Ki", 64 * 1024**2), ("64M", 64000000),
                                ("67108864", 64 * 1024**2), (67108864, 64 * 1024**2)):
            with self.subTest(value=value):
                self.assertEqual(_memory_bytes(value), Decimal(expected))
        for value in (None, "", "not-memory", "-1Mi", "64MB", "NaN", "Infinity", "64Mi trailing"):
            with self.subTest(value=value):
                self.assertIsNone(_memory_bytes(value))

    def test_healthy_oom_repair_preserves_valid_64_mib_limit(self):
        receipt = collect_receipt(options("11-incident-gauntlet/scenario-07"), FakeRunner())
        self.assertEqual(exit_code(receipt), 0)
        self.assertTrue(any(c["id"] == "memory-budget" and c["status"] == "pass" for c in receipt["checks"]))

    def test_healthy_incident_receipt_is_bounded_read_only_snapshot(self):
        runner = FakeRunner()
        receipt = collect_receipt(options(), runner)
        self.assertEqual(exit_code(receipt), 0)
        self.assertEqual(receipt["kind"], "aws-arcade-verification")
        self.assertIn("HTTP", receipt["scope"])
        self.assertEqual(receipt["summary"]["failed"], 0)
        for argv in runner.calls:
            self.assertFalse(set(argv) & {"apply", "delete", "exec", "create", "patch", "run", "drain"})
        self.assertNotIn("10.0.1.1", json.dumps(receipt))

    def test_unready_deployment_fails_even_when_pods_run(self):
        deployment = json.loads(json.dumps(DEPLOY))
        deployment["status"]["readyReplicas"] = 0
        receipt = collect_receipt(options(), FakeRunner({("get", "deployment", "app", "-o", "json"): deployment}))
        self.assertEqual(exit_code(receipt), 1)
        self.assertTrue(any(c["id"] == "rollout" and c["status"] == "fail" for c in receipt["checks"]))

    def test_missing_endpoint_fails_despite_ready_pods(self):
        key = ("get", "endpointslices", "-l", "kubernetes.io/service-name=app", "-o", "json")
        receipt = collect_receipt(options(), FakeRunner({key: {"items": []}}))
        self.assertEqual(exit_code(receipt), 1)

    def test_account_mismatch_aborts_before_cluster_or_kubectl(self):
        runner = FakeRunner({("sts", "get-caller-identity"): {"Account": "999999999999"}})
        receipt = collect_receipt(options(), runner)
        self.assertEqual(exit_code(receipt), 2)
        self.assertEqual(len(runner.calls), 1)

    def test_wrong_context_aborts_before_cluster_resource_reads(self):
        key = ("config", "view", "--minify", "-o", "json")
        runner = FakeRunner({key: {"clusters": [{"cluster": {"server": "https://wrong.example.com"}}]}})
        receipt = collect_receipt(options(), runner)
        self.assertEqual(exit_code(receipt), 2)
        self.assertEqual(len(runner.calls), 3)

    def test_cleanup_absence_is_pass_but_forbidden_is_error(self):
        self.assertEqual(exit_code(collect_receipt(options(phase="cleanup"), FakeRunner())), 0)
        key = ("get", "namespace", "arcade-incident-01", "--ignore-not-found", "-o", "json")
        receipt = collect_receipt(options(phase="cleanup"), FakeRunner({key: (1, "", "Error from server (Forbidden): private detail") }))
        self.assertEqual(exit_code(receipt), 2)
        self.assertNotIn("private detail", json.dumps(receipt))

    def test_cluster_cleanup_only_accepts_named_not_found(self):
        key = ("eks", "describe-cluster", "--name", "tfeks-arcade")
        for error, expected in [("An error occurred (ResourceNotFoundException) when calling DescribeCluster", 0), ("An error occurred (AccessDeniedException)", 2)]:
            runner = FakeRunner({key: (254, "", error)})
            receipt = collect_receipt(options("07-eks-foundation", "cleanup"), runner)
            self.assertEqual(exit_code(receipt), expected)
            self.assertEqual(len(runner.calls), 2)
            self.assertIn("orphan", receipt["scope"])

    def test_unsupported_or_injected_arguments_rejected_before_execution(self):
        for field, value in [("lab", "09-pod-identity"), ("cluster", "--endpoint-url=evil"), ("profile", "x\n--debug"), ("expected_account", "123"), ("context", "")]:
            opt = options()
            object.__setattr__(opt, field, value)
            runner = FakeRunner()
            with self.assertRaises(ValueError):
                collect_receipt(opt, runner)
            self.assertEqual(runner.calls, [])

    def test_job_rbac_requires_deny_beyond_named_configmap(self):
        overrides = {
            ("get", "job", "inspect", "-o", "json"): {"spec": {"template": {"spec": {"serviceAccountName": "inspector"}}}, "status": {"succeeded": 1, "conditions": [{"type": "Complete", "status": "True"}]}},
        }
        for verb, resource, allow in [("get", "configmap/app-settings", True), ("list", "configmaps", False), ("get", "secrets", False)]:
            key = ("auth", "can-i", verb, resource, "--as=system:serviceaccount:arcade-incident-06:inspector")
            overrides[key] = (0 if allow else 1, "yes\n" if allow else "no\n", "")
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-06"), FakeRunner(overrides))), 0)
        overrides[("auth", "can-i", "get", "secrets", "--as=system:serviceaccount:arcade-incident-06:inspector")] = (0, "yes\n", "")
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-06"), FakeRunner(overrides))), 1)

    def test_oom_memory_ceiling_cannot_be_bypassed_by_green_pod(self):
        deployment = json.loads(json.dumps(DEPLOY))
        deployment["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["memory"] = "1Gi"
        receipt = collect_receipt(options("11-incident-gauntlet/scenario-07"), FakeRunner({("get", "deployment", "app", "-o", "json"): deployment}))
        self.assertEqual(exit_code(receipt), 1)
        self.assertTrue(any(c["id"] == "memory-budget" and c["status"] == "fail" for c in receipt["checks"]))

    def test_recently_restarted_oom_workload_does_not_pass_stability(self):
        from datetime import datetime, timezone
        pods = json.loads(json.dumps(PODS))
        pods["items"][0]["status"]["containerStatuses"][0]["state"]["running"]["startedAt"] = datetime.now(timezone.utc).isoformat()
        receipt = collect_receipt(options("11-incident-gauntlet/scenario-07"), FakeRunner({("get", "pods", "-l", "app=incident", "-o", "json"): pods}))
        self.assertEqual(exit_code(receipt), 1)
        self.assertTrue(any(c["id"] == "process-stability" and c["status"] == "fail" for c in receipt["checks"]))

    def test_config_input_cannot_be_removed_to_make_pods_green(self):
        override = {("get", "configmap", "release-config", "-o", "json"): {"data": {"message": "do not leak value"}}}
        receipt = collect_receipt(options("11-incident-gauntlet/scenario-02"), FakeRunner(override))
        self.assertEqual(exit_code(receipt), 1)
        self.assertNotIn("do not leak value", json.dumps(receipt))
        deployment = json.loads(json.dumps(DEPLOY))
        deployment["spec"]["template"]["spec"]["containers"][0]["env"] = [{"name": "GREETING", "valueFrom": {"configMapKeyRef": {"name": "release-config", "key": "message"}}}]
        override[("get", "deployment", "app", "-o", "json")] = deployment
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-02"), FakeRunner(override))), 0)

    def test_scheduler_repair_does_not_pass_by_adding_capacity(self):
        node = {"metadata": {"name": "node-a", "labels": {"role": "lab"}}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        key = ("get", "nodes", "-o", "json")
        overrides = {key: {"items": [node]}}
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-05"), FakeRunner(overrides))), 0)
        overrides[key] = {"items": [node, node]}
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-05"), FakeRunner(overrides))), 1)

    def test_removing_readiness_probe_does_not_pass_web_incident(self):
        deployment = json.loads(json.dumps(DEPLOY))
        del deployment["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]
        receipt = collect_receipt(options("11-incident-gauntlet/scenario-04"), FakeRunner({("get", "deployment", "app", "-o", "json"): deployment}))
        self.assertEqual(exit_code(receipt), 1)
        self.assertTrue(any(c["id"] == "readiness" and c["status"] == "fail" for c in receipt["checks"]))

    def test_crash_loop_repair_requires_stable_process(self):
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-03"), FakeRunner())), 0)

    def test_cleanup_terminating_namespace_is_not_absent(self):
        key = ("get", "namespace", "arcade-incident-01", "--ignore-not-found", "-o", "json")
        receipt = collect_receipt(options(phase="cleanup"), FakeRunner({key: {"metadata": {"deletionTimestamp": "2026-10-04T10:00:00Z"}, "status": {"phase": "Terminating"}}}))
        self.assertEqual(exit_code(receipt), 1)

    def test_malformed_identity_output_is_error_and_stops_reads(self):
        runner = FakeRunner({("sts", "get-caller-identity"): (0, "not json", "")})
        receipt = collect_receipt(options(), runner)
        self.assertEqual(exit_code(receipt), 2)
        self.assertEqual(len(runner.calls), 1)

    def test_missing_executable_has_safe_error_category(self):
        with patch("verification.subprocess.run", side_effect=FileNotFoundError("private path")):
            result = ProcessRunner().run(["kubectl", "version"])
        self.assertEqual(result.returncode, 127)
        self.assertNotIn("private path", result.stderr)

    def test_pdb_requires_one_allowed_disruption_despite_healthy_replicas(self):
        deployment = json.loads(json.dumps(DEPLOY))
        deployment["spec"]["replicas"] = 2
        for key in ("replicas", "updatedReplicas", "availableReplicas", "readyReplicas"):
            deployment["status"][key] = 2
        pods = {"items": PODS["items"] * 2}
        pdb = {"metadata": {"generation": 2}, "spec": {"selector": {"matchLabels": {"app": "incident"}}}, "status": {"observedGeneration": 2, "expectedPods": 2, "currentHealthy": 2, "desiredHealthy": 2, "disruptionsAllowed": 0}}
        overrides = {("get", "deployment", "app", "-o", "json"): deployment, ("get", "pods", "-l", "app=incident", "-o", "json"): pods, ("get", "pdb", "app", "-o", "json"): pdb}
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-08"), FakeRunner(overrides))), 1)
        pdb["status"].update(desiredHealthy=1, disruptionsAllowed=1)
        self.assertEqual(exit_code(collect_receipt(options("11-incident-gauntlet/scenario-08"), FakeRunner(overrides))), 0)

    def test_lab_08_observer_cannot_read_secrets_or_patch_release(self):
        overrides = {
            ("get", "deployment", "web", "-o", "json"): DEPLOY,
            ("get", "pods", "-l", "app=arcade-web", "-o", "json"): PODS,
            ("get", "service", "web", "-o", "json"): {"spec": {"type": "ClusterIP", "selector": {"app": "arcade-web"}, "ports": [{"port": 80}]}},
            ("get", "endpointslices", "-l", "kubernetes.io/service-name=web", "-o", "json"): {"items": [{"ports": [{"port": 80}], "endpoints": [{"addresses": ["10.0.1.1"], "conditions": {"ready": True}}]}]},
        }
        for verb, resource, allowed in (("get", "pods", True), ("get", "secrets", False), ("patch", "deployments", False)):
            overrides[("auth", "can-i", verb, resource, "--as=system:serviceaccount:arcade-app:observer")] = (0 if allowed else 1, "yes\n" if allowed else "no\n", "")
        self.assertEqual(exit_code(collect_receipt(options("08-kubernetes-release"), FakeRunner(overrides))), 0)
        overrides[("auth", "can-i", "patch", "deployments", "--as=system:serviceaccount:arcade-app:observer")] = (0, "yes\n", "")
        self.assertEqual(exit_code(collect_receipt(options("08-kubernetes-release"), FakeRunner(overrides))), 1)

    def test_foundation_checks_each_addon_health_not_just_names(self):
        overrides = {
            ("eks", "describe-nodegroup", "--cluster-name", "tfeks-arcade", "--nodegroup-name", "lab"): {"nodegroup": {"status": "ACTIVE", "instanceTypes": ["t3.medium"], "scalingConfig": {"desiredSize": 1, "minSize": 1, "maxSize": 2}, "health": {"issues": []}}},
            ("get", "nodes", "-o", "json"): {"items": [{"metadata": {"name": "node-a", "labels": {"role": "lab", "node.kubernetes.io/instance-type": "t3.medium"}}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}]},
            ("get", "daemonset", "eks-pod-identity-agent", "-o", "json"): {"metadata": {"generation": 2}, "status": {"observedGeneration": 2, "desiredNumberScheduled": 1, "numberReady": 1, "updatedNumberScheduled": 1}},
            ("auth", "can-i", "create", "deployments", "--all-namespaces"): (0, "yes\n", ""),
        }
        for addon in ("vpc-cni", "kube-proxy", "coredns", "eks-pod-identity-agent"):
            overrides[("eks", "describe-addon", "--cluster-name", "tfeks-arcade", "--addon-name", addon)] = {"addon": {"status": "ACTIVE", "health": {"issues": []}}}
        receipt = collect_receipt(options("07-eks-foundation"), FakeRunner(overrides))
        self.assertEqual(exit_code(receipt), 0)
        key = ("eks", "describe-addon", "--cluster-name", "tfeks-arcade", "--addon-name", "coredns")
        overrides[key] = {"addon": {"status": "ACTIVE", "health": {"issues": [{"code": "InsufficientNumberOfReplicas"}]}}}
        self.assertEqual(exit_code(collect_receipt(options("07-eks-foundation"), FakeRunner(overrides))), 1)

    def test_selected_context_credential_plugin_is_never_executed(self):
        class InspectRunner(FakeRunner):
            config = None
            def run(self, argv):
                if "--kubeconfig" in argv:
                    path = Path(argv[argv.index("--kubeconfig") + 1])
                    self.config = json.loads(path.read_text())
                    self.mode = path.stat().st_mode & 0o777
                return super().run(argv)
        runner = InspectRunner()
        self.assertEqual(exit_code(collect_receipt(options(), runner)), 0)
        plugin = runner.config["users"][0]["user"]["exec"]
        self.assertEqual(plugin["command"], "aws")
        self.assertEqual(plugin["args"][:2], ["--profile", "arcade"])
        self.assertEqual(plugin["interactiveMode"], "Never")
        self.assertEqual(runner.mode, 0o600)
        temporary = next(argv[argv.index("--kubeconfig") + 1] for argv in runner.calls if "--kubeconfig" in argv)
        self.assertFalse(Path(temporary).exists())

    def test_process_timeout_is_reported_without_raw_error(self):
        with patch("verification.subprocess.run", side_effect=subprocess.TimeoutExpired("aws secret-value", 35)):
            result = ProcessRunner().run(["aws", "--version"])
        self.assertEqual(result.returncode, 124)
        self.assertNotIn("secret-value", result.stderr)

    def test_receipt_file_is_private_atomic_and_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            receipt = collect_receipt(options(), FakeRunner())
            write_receipt(target, receipt)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(target.read_text()), receipt)
            receipt["toolVersion"] = "2"
            write_receipt(target, receipt)
            self.assertEqual(json.loads(target.read_text())["toolVersion"], "2")
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                write_receipt(link, receipt)

    def test_process_boundary_uses_no_shell_and_timeout(self):
        with patch("verification.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
            ProcessRunner().run(["aws", "--version"])
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.kwargs["timeout"], 35)
        self.assertEqual(run.call_args.kwargs["env"]["AWS_PAGER"], "")
        self.assertEqual(run.call_args.kwargs["env"]["AWS_CLI_AUTO_PROMPT"], "off")


if __name__ == "__main__":
    unittest.main()
