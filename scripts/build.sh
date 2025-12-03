#!/usr/bin/env bash
git config --global url."https://${GITHUB_USERNAME}:${GITHUB_ACCESS_TOKEN}@github.com".insteadOf "https://github.com"
git submodule update --init --recursive
pip install -e .
pip install -e user_service