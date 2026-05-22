#!/usr/bin/env bash
set -e

DB="$(dirname "$0")/../results/benchmarks.db"
DB="$(realpath "$DB")"

if [ -f "$DB" ]; then
    rm "$DB"
    echo "Deleted: $DB"
else
    echo "Nothing to delete: $DB does not exist"
fi
