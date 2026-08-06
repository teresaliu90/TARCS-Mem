#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
cd "$project_dir"

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.example to .env and configure DeepSeek first." >&2
  exit 1
fi

set -a
. ./.env
set +a

if [ "${TARCSMEM_LLM_PROVIDER:-}" != "deepseek" ]; then
  echo "Set TARCSMEM_LLM_PROVIDER=deepseek in .env." >&2
  exit 1
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY is empty. Paste a newly rotated key into the local .env file." >&2
  exit 1
fi

if [ -x .venv-agent/bin/python ]; then
  python_bin=.venv-agent/bin/python
elif [ -x .venv/bin/python ]; then
  python_bin=.venv/bin/python
else
  echo "No project virtual environment found. Create .venv and install .[ui,api]." >&2
  exit 1
fi

export PYTHONPATH="$project_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python_bin" -m tarcsmem ui --db ./data/tarcsmem-deepseek.db
