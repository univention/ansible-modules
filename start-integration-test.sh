# start the integration test scenario from cmdline

die () {
	echo "Usage: [ENV_VAR=setting] ... ${0##*/} scenario.cfg"
	echo "$1"
	exit 1
}

test -z "$1" && die "no scenario.cfg given"

UCS_VERSION="${UCS_VERSION:=5.0-1}"
KVM_TEMPLATE="${KVM_TEMPLATE:=ucs-joined-master}"
KVM_BUILD_SERVER="${KVM_BUILD_SERVER:=ranarp}"
KVM_USER="${KVM_USER:=$USER}"
KVM_DHCP="${KVM_DHCP:=1}"
HALT="${HALT:=false}"
CFG="$(readlink -f "$1")"


declare -a cmd=()
cmd+=(
    "docker" "run"
    --rm
    -w /test
    -v "${PWD:-$(pwd)}:/test"
    -v "$HOME/ec2:$HOME/ec2:ro"
    -v "$CFG:$CFG:ro"
    --dns '192.168.0.124'
    --dns '192.168.0.97'
    --network host
    --dns-search 'knut.univention.de'
    -v "$HOME/.ssh:$HOME/.ssh:ro"
    -e UCS_VERSION="$UCS_VERSION"
    -e KVM_TEMPLATE="$KVM_TEMPLATE"
    -e KVM_BUILD_SERVER="$KVM_BUILD_SERVER"
    -e KVM_USER="$KVM_USER"
    -e USER="$KVM_USER"
    -e KVM_DHCP="$KVM_DHCP"
    -e HOME="$HOME"
    -u "${UID:-$(id -u)}"
    "docker-registry.knut.univention.de/ucs-ec2-tools"
)

cmd+=("ucs-kvm-create" -c "$CFG")
"$HALT" && cmd+=("-t")
"${cmd[@]}" && [ -e "./COMMAND_SUCCESS" ]
