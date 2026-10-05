#!/usr/bin/env bash
set -euo pipefail

OPENCUT_URL="${OPENCUT_URL:-https://opencut-production-c28c.up.railway.app}"
ASTELFAM_URL="${ASTELFAM_URL:-https://astelfam-editor-production-46b0.up.railway.app}"
WORKSPACE="${ASTEL_VIDEO_WORKSPACE:-$HOME/AstelVideoEditor}"

mkdir -p "$WORKSPACE"

cat > "$WORKSPACE/mac-validation-session.json" <<EOF
{
  "startedAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "machine": "$(scutil --get ComputerName 2>/dev/null || hostname)",
  "platform": "macOS",
  "openCutUrl": "$OPENCUT_URL",
  "astelFamUrl": "$ASTELFAM_URL",
  "workspace": "$WORKSPACE",
  "stage": 2,
  "status": "READY_FOR_HUMAN_LOGIN_AND_MEDIA"
}
EOF

echo "Astel Live Editor — macOS validation"
echo "Workspace: $WORKSPACE"
echo "Opening OpenCut..."
open "$OPENCUT_URL"

echo
echo "STAGE 2 READY."
echo "Use the same LIVE EDIT TEST project and repeat the bridge round-trip."
echo "Do not upload or publish from this validation script."
