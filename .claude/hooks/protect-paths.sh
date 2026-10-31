#!/usr/bin/env bash
# PreToolUse hook: block edits to secrets and generated code.
set -euo pipefail

path=$(jq -r '.tool_input.file_path // empty')
[ -z "$path" ] && exit 0

case "$path" in
  */.env|*/.env.*|*.pem|*.key)
    echo "Blocked: $path may contain secrets. Edit it yourself outside Claude." >&2
    exit 2 ;;
  */src/gen/*)
    echo "Blocked: $path is generated code. Change the generator or schema instead." >&2
    exit 2 ;;
esac
exit 0
