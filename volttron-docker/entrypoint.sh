#!/usr/bin/env bash
set -euo pipefail
# -e: Exit immediately if any command returns a nonzero (error) status.
# -u: Treat any reference to an unset variable as an error, and immediately exit.
# -o pipefail: the pipelines exit status is nonzero if any command in that chain fails.

# Activate the Volttron virtualenv
source /volttron/env/bin/activate

SHARED_DIR="${VOLTTRON_HOME}/AgentPackages/shared"

# If the folder with shared packages is mounted, install each package editable
if [ -d "$SHARED_DIR" ]; then
  echo ">> Found shared package directory: $SHARED_DIR"

  for pkg in "$SHARED_DIR"/*; do
    if [ -d "$pkg" ]; then
      if [ -f "$pkg/setup.py" ] || [ -f "$pkg/pyproject.toml" ]; then
        echo ">> Installing shared package: $pkg"
        pip install -e "$pkg"
      else
        echo ">> Skipping $pkg (no setup.py or pyproject.toml)"
      fi
    fi
  done
fi

# Start Volttron with whatever args were passed in
exec volttron "$@"