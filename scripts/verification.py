"""Bounded, read-only AWS Arcade snapshots. No apply, exec, repair or deletion.

A receipt reports selected API observations, not completion of the whole lab.
The browser treats imported JSON as user-supplied evidence, never attestation.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

LABS = ("07-eks-foundation", "08-kubernetes-release", *(
    f"11-incident-gauntlet/scenario-{number:02}" for number in range(1, 9)
))
MAX_OUTPUT = 4 * 1024 * 1024


@dataclass(frozen=True)
class Options:
    lab: str
    phase: str
    profile: str
    expected_account: str
    region: str
    cluster: str
    context: str = ""

    def validate(self):
        if self.lab not in LABS or self.phase not in ("verify", "cleanup"):
            raise ValueError("Choose one supported lab and verify or cleanup.")
        if not re.fullmatch(r"\d{12}", self.expected_account):
            raise ValueError("--expected-account must be the 12-digit sandbox account ID.")
        for label, value, pattern in (
            ("profile", self.profile, r"[A-Za-z0-9_][A-Za-z0-9_.@+=,-]{0,127}"),
            ("region", self.region, r"[a-z]{2}(?:-[a-z]+)+-\d"),
            ("cluster", self.cluster, r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}"),
        ):
            if not re.fullmatch(pattern, value):
                raise ValueError(f"Invalid --{label}; provide a literal name, not a command.")
        if not self.context and not (self.lab == LABS[0] and self.phase == "cleanup"):
            raise ValueError("--context is required for Kubernetes checks; select it explicitly.")
        if self.context and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+=,-]{0,255}", self.context):
            raise ValueError("Invalid --context name.")


class ProcessRunner:
    """The only process boundary; argv comes from fixed templates below."""
    def run(self, argv):
        env = dict(os.environ, AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off")
        try:
            result = subprocess.run(argv, shell=False, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=35, env=env)
        except FileNotFoundError:
            return subprocess.CompletedProcess(argv, 127, "", "ArcadeToolMissing")
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, "", "ArcadeTimeout")
        except (OSError, UnicodeError):
            return subprocess.CompletedProcess(argv, 126, "", "ArcadeProcessError")
        if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
            return subprocess.CompletedProcess(argv, 126, "", "ArcadeOutputLimit")
        return result


def _safe_error(result):
    """Never copy provider stderr, kubeconfig, tokens, object bodies or logs."""
    for token, message in (
        ("ArcadeToolMissing", "Required executable is not installed or not on PATH."),
        ("ArcadeTimeout", "Command exceeded the 35-second timeout; inspect connectivity."),
        ("ArcadeOutputLimit", "API output exceeded the verifier limit."),
        ("AccessDenied", "AWS denied this read operation; inspect the selected role."),
        ("Forbidden", "Kubernetes denied this read or impersonation operation."),
        ("Unauthorized", "Kubernetes authentication failed."),
        ("ExpiredToken", "AWS session expired; sign in to the selected profile again."),
        ("ResourceNotFoundException", "The named AWS resource was not found."),
        ("NotFound", "A required Kubernetes resource was not found."),
    ):
        if token in result.stderr:
            return message
    return f"Read command failed (exit {result.returncode}); inspect the command in your terminal."


def _condition(obj, name):
    return any(item.get("type") == name and item.get("status") == "True"
               for item in obj.get("status", {}).get("conditions", []))


def _memory_bytes(value):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(Ki|Mi|Gi|Ti|K|M|G|T)?", str(value))
    if not match:
        return None
    powers = {None: 1, "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3,
              "Ti": 1024**4, "K": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4}
    try:
        return Decimal(match[1]) * powers[match[2]]
    except InvalidOperation:
        return None


def _restricted_ipv4_cidrs(cidrs):
    try:
        return bool(cidrs) and all(isinstance(ipaddress.ip_network(cidr), ipaddress.IPv4Network)
                                   and ipaddress.ip_network(cidr).prefixlen == 32 for cidr in cidrs)
    except (TypeError, ValueError):
        return False


class Collector:
    def __init__(self, options, runner):
        self.options = options
        self.runner = runner
        self.checks = []
        self.kubeconfig = None

    def add(self, id_, label, status, expected, observed):
        self.checks.append({"id": id_, "label": label[:200], "status": status,
                            "expected": str(expected)[:2000], "observed": str(observed)[:2000]})

    def assertion(self, id_, label, passed, expected, observed):
        self.add(id_, label, "pass" if passed else "fail", expected, observed)

    def aws(self, *args):
        o = self.options
        return ["aws", "--profile", o.profile, "--region", o.region, "--output", "json", *args]

    def kubectl(self, *args, namespace=None, local_config=False):
        argv = ["kubectl", "--context", self.options.context, "--request-timeout", "20s"]
        if self.kubeconfig and not local_config:
            argv += ["--kubeconfig", self.kubeconfig]
        if namespace:
            argv += ["-n", namespace]
        return argv + list(args)

    def read(self, id_, label, argv):
        result = self.runner.run(argv)
        if result.returncode:
            self.add(id_, label, "error", "Read operation succeeds.", _safe_error(result))
            return None
        try:
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, TypeError):
            self.add(id_, label, "error", "A JSON object from the API.", "The command returned invalid JSON.")
            return None

    def identity_and_cluster(self):
        o = self.options
        identity = self.read("identity", "Sandbox account", self.aws("sts", "get-caller-identity"))
        if identity is None:
            return None
        if identity.get("Account") != o.expected_account:
            self.add("identity", "Sandbox account", "error", "The explicit expected account.",
                     "Account mismatch. Stopped before cluster or Kubernetes reads.")
            return None
        self.assertion("identity", "Sandbox account", True, "Selected profile resolves to expected account.", "Account matches.")
        if o.lab == LABS[0] and o.phase == "cleanup":
            result = self.runner.run(self.aws("eks", "describe-cluster", "--name", o.cluster))
            if result.returncode and re.search(r"\(ResourceNotFoundException\)", result.stderr):
                self.assertion("cluster-absent", "EKS cluster absent", True,
                               "DescribeCluster returns ResourceNotFoundException.", "Named cluster does not exist in this account and region.")
            elif result.returncode:
                self.add("cluster-absent", "EKS cluster absent", "error", "Named ResourceNotFoundException.", _safe_error(result))
            else:
                self.assertion("cluster-absent", "EKS cluster absent", False, "Cluster no longer exists.", "DescribeCluster still succeeds; deletion is not confirmed.")
            return None
        response = self.read("cluster-read", "Read EKS cluster", self.aws("eks", "describe-cluster", "--name", o.cluster))
        if response is None:
            return None
        cluster = response.get("cluster", {})
        endpoint = cluster.get("endpoint", "")
        ca = cluster.get("certificateAuthority", {}).get("data", "")
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+", endpoint) or not ca:
            self.add("cluster-read", "EKS connection data", "error", "A valid EKS HTTPS endpoint and CA.", "DescribeCluster lacks usable connection data.")
            return None
        config = self.read("context", "Selected Kubernetes context", self.kubectl("config", "view", "--minify", "-o", "json", local_config=True))
        if config is None:
            return None
        contexts = config.get("clusters", [])
        if len(contexts) != 1 or contexts[0].get("cluster", {}).get("server", "").rstrip("/") != endpoint.rstrip("/"):
            self.add("context", "Selected Kubernetes context", "error", "Context endpoint matches DescribeCluster.", "Context does not match. Stopped before Kubernetes API reads.")
            return None
        self.assertion("context", "Selected Kubernetes context", True, "Context endpoint matches the selected EKS cluster.", "Endpoint matches. Checks use a temporary config pinned to the selected AWS profile and EKS CA.")
        return cluster

    def config(self, cluster):
        """Do not execute credential plugins supplied by the user's kubeconfig."""
        o = self.options
        return {"apiVersion": "v1", "kind": "Config", "current-context": o.context,
                "clusters": [{"name": "arcade-verified", "cluster": {"server": cluster["endpoint"],
                              "certificate-authority-data": cluster["certificateAuthority"]["data"]}}],
                "contexts": [{"name": o.context, "context": {"cluster": "arcade-verified", "user": "arcade-verified"}}],
                "users": [{"name": "arcade-verified", "user": {"exec": {
                    "apiVersion": "client.authentication.k8s.io/v1beta1", "command": "aws",
                    "args": ["--profile", o.profile, "--region", o.region, "eks", "get-token", "--cluster-name", o.cluster, "--output", "json"],
                    "interactiveMode": "Never", "env": [{"name": "AWS_PAGER", "value": ""}, {"name": "AWS_CLI_AUTO_PROMPT", "value": "off"}]}}}]}

    def namespace_absent(self, namespace):
        result = self.runner.run(self.kubectl("get", "namespace", namespace, "--ignore-not-found", "-o", "json"))
        if result.returncode:
            self.add("namespace-absent", "Namespace absent", "error", "Authorized get returns no object.", _safe_error(result))
        else:
            self.assertion("namespace-absent", "Namespace absent", not result.stdout.strip(),
                           "Authorized get --ignore-not-found returns no object.",
                           "Namespace is absent." if not result.stdout.strip() else "Namespace still exists, including while Terminating.")

    def can_i(self, namespace, actor, verb, resource, expected):
        args = ["auth", "can-i", verb, resource]
        if actor:
            args.append(f"--as=system:serviceaccount:{namespace}:{actor}")
        elif namespace is None:
            args.append("--all-namespaces")
        result = self.runner.run(self.kubectl(*args, namespace=namespace))
        answer = result.stdout.strip()
        id_ = f"rbac-{verb}-{resource.replace('/', '-')}"
        if (result.returncode, answer) not in ((0, "yes"), (1, "no")) or result.stderr.strip():
            self.add(id_, "Authorization boundary", "error", "A definitive yes or no authorization response.", _safe_error(result))
            return
        self.assertion(id_, f"{actor or 'Selected role'}: {verb} {resource}", (answer == "yes") == expected,
                       "Allowed." if expected else "Denied.", "Allowed." if answer == "yes" else "Denied.")

    def foundation(self, cluster):
        c = cluster
        self.assertion("cluster-active", "Control plane health", c.get("status") == "ACTIVE", "ACTIVE", c.get("status", "missing"))
        try:
            toolchain = json.loads((Path(__file__).resolve().parents[1] / "toolchain.json").read_text(encoding="utf-8"))
            expected_version = toolchain["eks"]["version"]
            self.assertion("cluster-version", "Documented EKS version", c.get("version") == expected_version, expected_version, c.get("version", "missing"))
        except (OSError, ValueError, KeyError, TypeError):
            self.add("cluster-version", "Documented EKS version", "error", "Version matches the bundled toolchain.json.", "Bundled EKS version could not be read; restore the complete kit.")
        network = c.get("resourcesVpcConfig", {})
        cidrs = network.get("publicAccessCidrs", [])
        self.assertion("cluster-boundary", "Cost and API boundary", c.get("upgradePolicy", {}).get("supportType") == "STANDARD" and network.get("endpointPrivateAccess") is True and network.get("endpointPublicAccess") is True and _restricted_ipv4_cidrs(cidrs),
                       "STANDARD support, private API access, public access limited to IPv4 /32 entries.",
                       f"Support={c.get('upgradePolicy', {}).get('supportType', 'missing')}; private={network.get('endpointPrivateAccess')}; public CIDR count={len(cidrs)}.")
        ng = self.read("nodegroup-read", "Managed node group", self.aws("eks", "describe-nodegroup", "--cluster-name", self.options.cluster, "--nodegroup-name", "lab"))
        if ng is not None:
            ng = ng.get("nodegroup", {})
            scale = ng.get("scalingConfig", {})
            self.assertion("nodegroup", "One managed worker", ng.get("status") == "ACTIVE" and scale.get("desiredSize") == 1 and scale.get("minSize") == 1 and scale.get("maxSize") == 2 and not ng.get("health", {}).get("issues", []),
                           "ACTIVE, no health issues, one desired worker, min 1 / max 2.",
                           f"Status={ng.get('status', 'missing')}; desired={scale.get('desiredSize')}; min={scale.get('minSize')}; max={scale.get('maxSize')}; health issues={len(ng.get('health', {}).get('issues', []))}.")
        for addon in ("vpc-cni", "kube-proxy", "coredns", "eks-pod-identity-agent"):
            data = self.read(f"addon-read-{addon}", f"Read {addon}", self.aws("eks", "describe-addon", "--cluster-name", self.options.cluster, "--addon-name", addon))
            if data is not None:
                data = data.get("addon", {})
                issues = data.get("health", {}).get("issues", [])
                self.assertion(f"addon-{addon}", f"{addon} health", data.get("status") == "ACTIVE" and not issues,
                               "ACTIVE with no health issues.", f"Status={data.get('status', 'missing')}; issue count={len(issues)}.")
        nodes = self.read("nodes-read", "Read workers", self.kubectl("get", "nodes", "-o", "json"))
        if nodes is not None:
            items = nodes.get("items", [])
            ready = [n for n in items if _condition(n, "Ready") and n.get("metadata", {}).get("labels", {}).get("role") == "lab" and n.get("metadata", {}).get("labels", {}).get("node.kubernetes.io/instance-type") == "t3.medium"]
            self.assertion("nodes", "One ready small lab node", len(items) == len(ready) == 1, "Exactly one node, Ready, role=lab, instance type t3.medium.", f"Nodes={len(items)}; Ready t3.medium lab nodes={len(ready)}.")
        self.can_i(None, None, "create", "deployments", True)
        data = self.read("agent-read", "Pod Identity agent rollout", self.kubectl("get", "daemonset", "eks-pod-identity-agent", "-o", "json", namespace="kube-system"))
        if data is not None:
            s = data.get("status", {})
            desired = s.get("desiredNumberScheduled", 0)
            self.assertion("agent-ready", "Pod Identity agent ready", desired > 0 and s.get("numberReady") == desired and s.get("updatedNumberScheduled") == desired and s.get("observedGeneration", 0) >= data.get("metadata", {}).get("generation", 1), "Current DaemonSet generation is fully ready.", f"Desired={desired}; ready={s.get('numberReady', 0)}; updated={s.get('updatedNumberScheduled', 0)}.")

    def workload(self, namespace, incident):
        if incident == 6:
            job = self.read("job-read", "Inspection job", self.kubectl("get", "job", "inspect", "-o", "json", namespace=namespace))
            if job is not None:
                account = job.get("spec", {}).get("template", {}).get("spec", {}).get("serviceAccountName")
                self.assertion("job-complete", "Inspection job completed", _condition(job, "Complete") and job.get("status", {}).get("succeeded", 0) >= 1 and account == "inspector", "Job Complete with a succeeded pod, using inspector.", f"Complete={_condition(job, 'Complete')}; succeeded={job.get('status', {}).get('succeeded', 0)}; expected service account={account == 'inspector'}.")
            self.can_i(namespace, "inspector", "get", "configmap/app-settings", True)
            self.can_i(namespace, "inspector", "list", "configmaps", False)
            self.can_i(namespace, "inspector", "get", "secrets", False)
            return
        name, selector = ("web", "app=arcade-web") if incident is None else ("app", "app=incident")
        desired = 2 if incident == 8 else 1
        deployment = self.read("deployment-read", "Read release", self.kubectl("get", "deployment", name, "-o", "json", namespace=namespace))
        if deployment is not None:
            status, spec = deployment.get("status", {}), deployment.get("spec", {})
            healthy = spec.get("replicas") == desired and status.get("observedGeneration", 0) >= deployment.get("metadata", {}).get("generation", 1) and all(status.get(key, 0) == desired for key in ("replicas", "updatedReplicas", "availableReplicas", "readyReplicas"))
            self.assertion("rollout", "Current release ready", healthy, f"Current generation, exactly {desired} desired / updated / available / ready replicas.", f"Desired={spec.get('replicas')}; updated={status.get('updatedReplicas', 0)}; available={status.get('availableReplicas', 0)}; ready={status.get('readyReplicas', 0)}.")
            containers = spec.get("template", {}).get("spec", {}).get("containers", [])
            probes = bool(containers) and all(bool(c.get("readinessProbe")) for c in containers)
            if incident != 7:
                probes = probes and all("httpGet" in c.get("readinessProbe", {}) for c in containers)
            self.assertion("readiness", "Readiness preserved", probes, "A readiness probe remains on each application container; HTTP for web workloads.", "Required probes present." if probes else "A required probe is missing or no longer HTTP.")
            if incident == 2:
                references = [item.get("valueFrom", {}).get("configMapKeyRef", {}) for container in containers for item in container.get("env", []) if item.get("name") == "GREETING"]
                correct = len(references) == 1 and references[0].get("name") == "release-config" and references[0].get("key") == "message" and references[0].get("optional") is not True
                self.assertion("config-reference", "Original namespace configuration used", correct, "GREETING requires release-config key message; the environment input remains present.", "Required ConfigMap reference matches." if correct else "Required GREETING reference was removed, made optional or still targets the wrong source.")
                config = self.read("config-read", "Read referenced configuration", self.kubectl("get", "configmap", "release-config", "-o", "json", namespace=namespace))
                if config is not None:
                    self.assertion("config-key", "Required configuration key exists", "message" in config.get("data", {}), "release-config contains the message key.", "Key exists; value omitted from receipt." if "message" in config.get("data", {}) else "Required key is absent.")
            if incident == 7:
                limits = [_memory_bytes(c.get("resources", {}).get("limits", {}).get("memory")) for c in containers]
                self.assertion("memory-budget", "Original memory ceiling", bool(limits) and all(limit is not None and 0 < limit <= 64 * 1024**2 for limit in limits), "Every container has a positive memory limit no greater than 64 MiB.", "Memory limits remain within budget." if limits and all(limit is not None and 0 < limit <= 64 * 1024**2 for limit in limits) else "Memory limit missing, unrecognized or above 64 MiB.")
        pods = self.read("pods-read", "Read release pods", self.kubectl("get", "pods", "-l", selector, "-o", "json", namespace=namespace))
        if pods is not None:
            items = [p for p in pods.get("items", []) if not p.get("metadata", {}).get("deletionTimestamp")]
            healthy = [p for p in items if p.get("status", {}).get("phase") == "Running" and _condition(p, "Ready") and p.get("spec", {}).get("nodeName") and p.get("status", {}).get("containerStatuses") and all(c.get("ready") and "running" in c.get("state", {}) for c in p["status"]["containerStatuses"])]
            self.assertion("pods", "Scheduled, running, ready pods", len(items) == len(healthy) == desired, f"Exactly {desired} non-terminating scheduled, Running, Ready pod(s); all containers running.", f"Active pods={len(items)}; healthy={len(healthy)}.")
            if incident == 5:
                nodes = self.read("capacity-read", "Read existing worker capacity", self.kubectl("get", "nodes", "-o", "json"))
                if nodes is not None:
                    workers = nodes.get("items", [])
                    correct = len(workers) == 1 and _condition(workers[0], "Ready") and workers[0].get("metadata", {}).get("labels", {}).get("role") == "lab" and all(p.get("spec", {}).get("nodeName") == workers[0].get("metadata", {}).get("name") for p in healthy)
                    self.assertion("existing-capacity", "Existing worker is sufficient", correct, "One Ready role=lab node hosts the repaired release; no added worker.", f"Total nodes={len(workers)}; release stays on the existing lab worker={correct}.")
            if incident in (3, 7):
                stable = len(healthy) == desired
                ages = []
                for pod in healthy:
                    for container in pod["status"]["containerStatuses"]:
                        try:
                            start = datetime.fromisoformat(container["state"]["running"]["startedAt"].replace("Z", "+00:00"))
                            ages.append((datetime.now(timezone.utc) - start).total_seconds())
                        except (KeyError, ValueError, TypeError):
                            stable = False
                stable = stable and bool(ages) and all(age >= 60 for age in ages)
                self.assertion("process-stability", "Process survived startup", stable, "Each current process has run for at least 60 seconds. A point-in-time observation, not a soak test.", "Every process is at least 60 seconds old." if stable else "A process is missing, not Running, or younger than 60 seconds; repeat after observing it.")
        if incident != 7:
            self.service(namespace, name, selector)
        if incident is None:
            for verb, resource, allow in (("get", "pods", True), ("get", "secrets", False), ("patch", "deployments", False)):
                self.can_i(namespace, "observer", verb, resource, allow)
        if incident == 8:
            pdb = self.read("pdb-read", "Read disruption budget", self.kubectl("get", "pdb", "app", "-o", "json", namespace=namespace))
            if pdb is not None:
                spec, status = pdb.get("spec", {}), pdb.get("status", {})
                valid = spec.get("selector", {}).get("matchLabels") == {"app": "incident"} and status.get("observedGeneration", 0) >= pdb.get("metadata", {}).get("generation", 1) and status.get("expectedPods") == 2 and status.get("currentHealthy") == 2 and status.get("desiredHealthy") == 1 and status.get("disruptionsAllowed") == 1
                self.assertion("disruption-budget", "Exactly one disruption allowed", valid, "Current PDB selects incident pods, has 2 healthy / 1 required / 1 allowed disruption.", f"Healthy={status.get('currentHealthy')}; required={status.get('desiredHealthy')}; allowed={status.get('disruptionsAllowed')}. Actual eviction remains a manual runbook check.")

    def service(self, namespace, name, selector):
        data = self.read("service-read", "Read service", self.kubectl("get", "service", name, "-o", "json", namespace=namespace))
        if data is not None:
            spec = data.get("spec", {})
            label, value = selector.split("=", 1)
            self.assertion("service", "Internal service selects release", spec.get("type", "ClusterIP") == "ClusterIP" and spec.get("selector") == {label: value} and bool(spec.get("ports")), "ClusterIP with the release selector and a service port.", "Expected selector and internal type." if spec.get("selector") == {label: value} and spec.get("type", "ClusterIP") == "ClusterIP" else "Service selector or type differs from the lab contract.")
        endpoints = self.read("endpoints-read", "Read ready service backends", self.kubectl("get", "endpointslices", "-l", f"kubernetes.io/service-name={name}", "-o", "json", namespace=namespace))
        if endpoints is not None:
            count = sum(1 for s in endpoints.get("items", []) if any(p.get("port") for p in s.get("ports", [])) for e in s.get("endpoints", []) if e.get("conditions", {}).get("ready") is True and e.get("addresses"))
            self.assertion("endpoints", "Ready service backend", count > 0, "At least one addressed Ready EndpointSlice backend with a port.", f"Ready backends={count}. This does not execute an HTTP request.")


def collect_receipt(options, runner=None):
    options.validate()
    collector = Collector(options, runner or ProcessRunner())
    cluster = collector.identity_and_cluster()
    if cluster is not None:
        # Use a private snapshot so credential plugins/role overrides in a context
        # cannot silently choose another principal after the account guard passes.
        with tempfile.TemporaryDirectory(prefix="arcade-verify-") as directory:
            config = Path(directory) / "kubeconfig.json"
            fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(collector.config(cluster), file)
            collector.kubeconfig = str(config)
            if options.lab == LABS[0]:
                collector.foundation(cluster)
            else:
                incident = int(options.lab[-2:]) if options.lab.startswith("11-") else None
                namespace = f"arcade-incident-{incident:02}" if incident else "arcade-app"
                if options.phase == "cleanup":
                    collector.namespace_absent(namespace)
                else:
                    collector.workload(namespace, incident)
    if options.phase == "cleanup":
        scope = ("Point-in-time absence of the named EKS cluster only. This does not prove Terraform state is empty or orphaned instances, volumes, ENIs, IPs and other billable resources are gone. Run the cost/cleanup audit." if options.lab == LABS[0] else "Point-in-time absence of this namespace only. EKS and its workers still bill. This does not prove cluster teardown or absence of orphaned AWS resources; complete lab 07 cleanup and the cost audit.")
    elif options.lab == LABS[0]:
        scope = "Read-only control plane, worker, managed addon and selected authorization snapshot. Does not check Terraform drift, complete IAM/network policy, launch template hardening or orphaned billable resources. Finish the runbook acceptance and teardown checks."
    else:
        scope = "Read-only rollout, configuration and selected API-observable checks at this instant. Does not make an in-cluster HTTP request, perform an eviction, prove the original failure or certify a durable fix. Complete the runbook functional checks and explain your evidence."
    counts = {name: sum(check["status"] == status for check in collector.checks)
              for name, status in (("passed", "pass"), ("failed", "fail"), ("errors", "error"))}
    return {"schemaVersion": 1, "kind": "aws-arcade-verification", "toolVersion": "1",
            "labId": options.lab, "phase": options.phase,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "environment": {"account": options.expected_account, "region": options.region, "cluster": options.cluster, "context": options.context},
            "scope": scope, "checks": collector.checks, "summary": counts}


def exit_code(receipt):
    return 2 if receipt["summary"]["errors"] else 1 if receipt["summary"]["failed"] else 0


def write_receipt(path, receipt):
    """Private, atomic; replace only an existing regular file owned by this user."""
    path = Path(path)
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    if existing and (not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid()):
        raise ValueError("Receipt output must be a new path or your own regular file, never a symlink.")
    content = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    if len(content) > 128 * 1024:
        raise ValueError("Receipt exceeds the size limit.")
    fd, temporary = tempfile.mkstemp(prefix=".arcade-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
