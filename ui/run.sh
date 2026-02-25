#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit
streamlit run ui/app.py "$@"
