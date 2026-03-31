#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec "${PWD}/.venv/bin/python" -u main.py
