#!/bin/bash
# run_audit_and_report.sh — Run a single clinic audit and generate reports

set -e

cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || (python3 -m venv .venv && source .venv/bin/activate && pip install -q requests beautifulsoup4 reportlab)

if [ -z "$1" ]; then
    echo "Usage: ./run_audit_and_report.sh <clinic_url>"
    echo "Example: ./run_audit_and_report.sh https://www.example-physio.com"
    exit 1
fi

echo "Running audit for: $1"
echo "$1" | python3 auditv.py

# Find the most recently generated JSON file
LATEST_JSON=$(ls -t outputs/audit_output_*.json | head -1)
echo ""
echo "Generating reports from: $LATEST_JSON"
python3 generate_reports.py "$LATEST_JSON"

echo ""
echo "✓ Audit and reports complete!"
