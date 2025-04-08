#!/bin/bash
# Clean previous builds
rm -rf dist/
rm -rf build/
rm -rf *.egg-info

# Build distributions
pip install --upgrade build
python -m build

# Upload to PyPI (will prompt for credentials)
pip install --upgrade twine
twine upload dist/*
