#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 src/safety_project.py --scale full --seed 20261022 --output output
