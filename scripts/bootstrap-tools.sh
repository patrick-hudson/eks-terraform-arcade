#!/usr/bin/env bash
# Linux/WSL installer. All downloads and installs remain under this project's .tools.
set -euo pipefail
ARCADE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
if (($#)); then
  printf 'Usage: bash scripts/bootstrap-tools.sh\nInstalls pinned tools locally; does not change shell configuration or authenticate AWS.\n'
  [[ $1 == --help || $1 == -h ]] && exit 0 || exit 2
fi
[[ $(uname -s) == Linux ]] || { printf 'This bootstrap supports Linux/WSL. See docs/setup.md for macOS.\n' >&2; exit 1; }
case $(uname -m) in
  x86_64) ARCADE_ARCH=amd64; ARCADE_AWS_ARCH=x86_64 ;;
  aarch64|arm64) ARCADE_ARCH=arm64; ARCADE_AWS_ARCH=aarch64 ;;
  *) printf 'Unsupported CPU architecture.\n' >&2; exit 1 ;;
esac
for ARCADE_DEP in python3 curl unzip gpg tar sha256sum install; do
  command -v "$ARCADE_DEP" >/dev/null || { printf 'Missing prerequisite: %s\n' "$ARCADE_DEP" >&2; exit 1; }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python >=3.10 is required")'
ARCADE_BIN="$ARCADE_ROOT/.tools/bin"
ARCADE_CACHE="$ARCADE_ROOT/.tools/downloads"
mkdir -p "$ARCADE_BIN" "$ARCADE_CACHE"
ARCADE_PIN() {
  python3 - "$ARCADE_ROOT/toolchain.json" "$1" "${2:-}" <<'PY'
import json, re, sys
pins = {c['name']: c['version'] for c in json.load(open(sys.argv[1]))['components']}
value = pins.get(sys.argv[2], sys.argv[3])
if not re.fullmatch(r'\d+\.\d+\.\d+', value):
    sys.exit('Missing or invalid release pin: ' + sys.argv[2])
print(value)
PY
}
ARCADE_FETCH() {
  local url=$1 target=$2
  if [[ ! -s "$target" ]]; then
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 --retry 3 "$url" -o "$target.part"
    mv -- "$target.part" "$target"
  fi
}
ARCADE_CHECKSUM() {
  python3 - "$1" "$2" <<'PY'
import hashlib, pathlib, sys
artifact, sums = map(pathlib.Path, sys.argv[1:])
matches = [line.split()[0] for line in sums.read_text().splitlines()
           if len(line.split()) == 2 and line.split()[1].lstrip('*') == artifact.name]
if len(matches) != 1 or hashlib.sha256(artifact.read_bytes()).hexdigest() != matches[0]:
    sys.exit('SHA-256 verification failed: ' + artifact.name)
print('SHA-256 verified: ' + artifact.name)
PY
}
ARCADE_TF=$(ARCADE_PIN Terraform)
ARCADE_KUBECTL=$(ARCADE_PIN kubectl)
ARCADE_KUBECONFORM=$(ARCADE_PIN kubeconform)
ARCADE_AWS=$(ARCADE_PIN 'AWS CLI')
ARCADE_JQ=$(ARCADE_PIN jq 1.8.2)

ARCADE_TF_ZIP="terraform_${ARCADE_TF}_linux_${ARCADE_ARCH}.zip"
if [[ ! -e "$ARCADE_CACHE/$ARCADE_TF_ZIP" && -f "$ARCADE_ROOT/work/toolchain/downloads/$ARCADE_TF_ZIP" ]]; then
  cp -- "$ARCADE_ROOT/work/toolchain/downloads/$ARCADE_TF_ZIP" "$ARCADE_CACHE/$ARCADE_TF_ZIP"
fi
ARCADE_FETCH "https://releases.hashicorp.com/terraform/$ARCADE_TF/$ARCADE_TF_ZIP" "$ARCADE_CACHE/$ARCADE_TF_ZIP"
ARCADE_FETCH "https://releases.hashicorp.com/terraform/$ARCADE_TF/terraform_${ARCADE_TF}_SHA256SUMS" "$ARCADE_CACHE/terraform_${ARCADE_TF}_SHA256SUMS"
ARCADE_CHECKSUM "$ARCADE_CACHE/$ARCADE_TF_ZIP" "$ARCADE_CACHE/terraform_${ARCADE_TF}_SHA256SUMS"
unzip -p "$ARCADE_CACHE/$ARCADE_TF_ZIP" terraform > "$ARCADE_BIN/terraform.new"
chmod 0755 "$ARCADE_BIN/terraform.new"
mv "$ARCADE_BIN/terraform.new" "$ARCADE_BIN/terraform"

ARCADE_FETCH "https://dl.k8s.io/release/v$ARCADE_KUBECTL/bin/linux/$ARCADE_ARCH/kubectl" "$ARCADE_CACHE/kubectl-$ARCADE_KUBECTL-$ARCADE_ARCH"
ARCADE_FETCH "https://dl.k8s.io/release/v$ARCADE_KUBECTL/bin/linux/$ARCADE_ARCH/kubectl.sha256" "$ARCADE_CACHE/kubectl-$ARCADE_KUBECTL-$ARCADE_ARCH.sha256"
printf '%s  %s\n' "$(cat "$ARCADE_CACHE/kubectl-$ARCADE_KUBECTL-$ARCADE_ARCH.sha256")" "$ARCADE_CACHE/kubectl-$ARCADE_KUBECTL-$ARCADE_ARCH" | sha256sum --check --status
printf 'SHA-256 verified: kubectl %s\n' "$ARCADE_KUBECTL"
install -m 0755 "$ARCADE_CACHE/kubectl-$ARCADE_KUBECTL-$ARCADE_ARCH" "$ARCADE_BIN/kubectl"

ARCADE_KC_DIR="$ARCADE_CACHE/kubeconform-$ARCADE_KUBECONFORM"
mkdir -p "$ARCADE_KC_DIR"
ARCADE_FETCH "https://github.com/yannh/kubeconform/releases/download/v$ARCADE_KUBECONFORM/kubeconform-linux-$ARCADE_ARCH.tar.gz" "$ARCADE_KC_DIR/kubeconform-linux-$ARCADE_ARCH.tar.gz"
ARCADE_FETCH "https://github.com/yannh/kubeconform/releases/download/v$ARCADE_KUBECONFORM/CHECKSUMS" "$ARCADE_KC_DIR/CHECKSUMS"
ARCADE_CHECKSUM "$ARCADE_KC_DIR/kubeconform-linux-$ARCADE_ARCH.tar.gz" "$ARCADE_KC_DIR/CHECKSUMS"
tar -xzf "$ARCADE_KC_DIR/kubeconform-linux-$ARCADE_ARCH.tar.gz" -C "$ARCADE_KC_DIR" kubeconform
install -m 0755 "$ARCADE_KC_DIR/kubeconform" "$ARCADE_BIN/kubeconform"

ARCADE_JQ_DIR="$ARCADE_CACHE/jq-$ARCADE_JQ"
mkdir -p "$ARCADE_JQ_DIR"
ARCADE_FETCH "https://github.com/jqlang/jq/releases/download/jq-$ARCADE_JQ/jq-linux-$ARCADE_ARCH" "$ARCADE_JQ_DIR/jq-linux-$ARCADE_ARCH"
ARCADE_FETCH "https://github.com/jqlang/jq/releases/download/jq-$ARCADE_JQ/sha256sum.txt" "$ARCADE_JQ_DIR/sha256sum.txt"
ARCADE_CHECKSUM "$ARCADE_JQ_DIR/jq-linux-$ARCADE_ARCH" "$ARCADE_JQ_DIR/sha256sum.txt"
install -m 0755 "$ARCADE_JQ_DIR/jq-linux-$ARCADE_ARCH" "$ARCADE_BIN/jq"

ARCADE_AWS_URL="https://awscli.amazonaws.com/awscli-exe-linux-${ARCADE_AWS_ARCH}-${ARCADE_AWS}.zip"
ARCADE_AWS_ZIP="$ARCADE_CACHE/awscli-${ARCADE_AWS_ARCH}-${ARCADE_AWS}.zip"
ARCADE_FETCH "$ARCADE_AWS_URL" "$ARCADE_AWS_ZIP"
ARCADE_FETCH "$ARCADE_AWS_URL.sig" "$ARCADE_AWS_ZIP.sig"
ARCADE_FETCH 'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html' "$ARCADE_CACHE/aws-cli-install.html"
python3 - "$ARCADE_CACHE/aws-cli-install.html" "$ARCADE_CACHE/aws-cli-public-key.asc" <<'PY'
import html, pathlib, re, sys
text = html.unescape(pathlib.Path(sys.argv[1]).read_text())
match = re.search(r'-----BEGIN PGP PUBLIC KEY BLOCK-----.*?-----END PGP PUBLIC KEY BLOCK-----', text, re.S)
if not match:
    sys.exit('AWS signing key not found in official installation documentation')
pathlib.Path(sys.argv[2]).write_text(re.sub(r'<[^>]+>', '', match.group(0)) + '\n')
PY
ARCADE_GPG="$ARCADE_CACHE/gnupg"
mkdir -p "$ARCADE_GPG"
chmod 0700 "$ARCADE_GPG"
ARCADE_FINGERPRINT=$(gpg --homedir "$ARCADE_GPG" --batch --with-colons --show-keys "$ARCADE_CACHE/aws-cli-public-key.asc" 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }')
[[ "$ARCADE_FINGERPRINT" == FB5DB77FD5C118B80511ADA8A6310ACC4672475C ]] || { printf 'AWS signing key fingerprint differs from the documented pin. Stop and review the official signing-key rotation.\n' >&2; exit 1; }
gpg --homedir "$ARCADE_GPG" --batch --import "$ARCADE_CACHE/aws-cli-public-key.asc" >/dev/null 2>&1
gpg --homedir "$ARCADE_GPG" --batch --verify "$ARCADE_AWS_ZIP.sig" "$ARCADE_AWS_ZIP"
ARCADE_AWS_EXTRACT="$ARCADE_CACHE/awscli-$ARCADE_AWS-extracted"
mkdir -p "$ARCADE_AWS_EXTRACT"
unzip -q -o "$ARCADE_AWS_ZIP" -d "$ARCADE_AWS_EXTRACT"
"$ARCADE_AWS_EXTRACT/aws/install" --install-dir "$ARCADE_ROOT/.tools/aws-cli" --bin-dir "$ARCADE_BIN" --update

chmod 0755 "$ARCADE_ROOT/scripts/arcade"
ln -sfn ../../scripts/arcade "$ARCADE_BIN/arcade"
source "$ARCADE_ROOT/scripts/env.sh"
python3 "$ARCADE_ROOT/scripts/doctor.py"
printf '\nReady. Activate this terminal with:\n  source %q\n' "$ARCADE_ROOT/scripts/env.sh"
