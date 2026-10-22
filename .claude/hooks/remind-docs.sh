#!/usr/bin/env bash
# PostToolUse hook for Edit|Write: the agent's behavior is specified in docs/spectra/specs/
# and described in README.md and docs/. Editing the package code is a cue to check them.
# Reminds once; stays quiet after README.md or anything under docs/ has been changed.
set -u

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
[ -z "$file" ] && exit 0

case "$file" in
  */fixlab/loop.py|*/fixlab/tools.py|*/fixlab/toolparse.py|*/fixlab/workspace.py|\
*/fixlab/sandbox.py|*/fixlab/interpreter.py|*/fixlab/telemetry.py|*/fixlab/cli.py|\
*/fixlab/mcp_tools.py|*/fixlab/display.py) kind=code ;;
  */tests/golden/*) kind=golden ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
if git status --porcelain -- README.md docs 2>/dev/null | grep -q .; then
  exit 0
fi

if [ "$kind" = golden ]; then
  msg="You edited tests/golden/. The golden trace is the baseline for test_trace_golden.py; regenerate it only with UPDATE_GOLDEN=1 for an intentional behavior change, never by hand, and say so in the commit."
else
  msg="You edited fixlab/$(basename "$file"). Its behavior is specified in docs/spectra/specs/ and described in README.md and docs/. If behavior, CLI output, tool schemas or telemetry fields changed: the change needs a Spectra change (do not edit archived ones), and README.md or docs/*.md must be updated if users can see the difference."
fi

jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
