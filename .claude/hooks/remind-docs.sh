#!/usr/bin/env bash
# PostToolUse hook for Edit|Write: the agent's behavior is specified in docs/spectra/specs/ and
# described in README.md and docs/. Editing the package code is a cue to check them, and editing
# the golden trace is a cue to regenerate it properly instead of by hand.
# Reminds once per file and HEAD; stays quiet while README.md or docs/ have uncommitted changes.
# Requires jq.
set -u

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$here/lib.sh"

command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$file" ] && exit 0

case "$file" in
  */fixlab/loop.py|*/fixlab/tools.py|*/fixlab/toolparse.py|*/fixlab/workspace.py|\
*/fixlab/sandbox.py|*/fixlab/interpreter.py|*/fixlab/telemetry.py|*/fixlab/cli.py|\
*/fixlab/mcp_tools.py|*/fixlab/display.py|*/fixlab/bench/*.py) kind=code ;;
  */tests/golden/*) kind=golden ;;
  *) exit 0 ;;
esac

init_repo "$input" || exit 0
if git status --porcelain -- README.md docs 2>/dev/null | grep -q .; then
  exit 0
fi

state="$(root_dir)/.claude/state/docs-reminded"
rel=${file#"$(root_dir)"/}; [ "$rel" = "$file" ] && rel=fixlab/$(basename "$file")
key="$(git rev-parse HEAD 2>/dev/null || echo none):$rel"
if grep -qxF "$key" "$state" 2>/dev/null; then
  exit 0
fi
mkdir -p "$(dirname "$state")"
printf '%s\n' "$key" >> "$state"

if [ "$kind" = golden ]; then
  msg="You edited tests/golden/. The golden trace is the baseline for test_trace_golden.py; regenerate it only with UPDATE_GOLDEN=1 for an intentional behavior change, never by hand, and say so in the commit."
else
  msg="You edited $rel. Its behavior is specified in docs/spectra/specs/ and described in README.md and docs/. If behavior, CLI output, tool schemas or telemetry fields changed: the change needs a Spectra change (do not edit archived ones), and README.md or docs/*.md must be updated if users can see the difference."
fi

jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
