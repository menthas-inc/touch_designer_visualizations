#!/bin/bash
# The beat tracker's environment: Python 3.10 (madmom needs it), the numpy it builds against,
# audio in and OSC out. Run once from the repo root; takes a minute or two.
#     bash beat/install.sh
set -e
cd "$(dirname "$0")/.."
brew list portaudio >/dev/null 2>&1 || brew install portaudio
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg  # madmom reads anything but wav through it
uv venv --python 3.10 beat/.venv
P=beat/.venv/bin/python
uv pip install --python $P "numpy<1.24" "cython<3" "setuptools<70" wheel
uv pip install --python $P --no-build-isolation madmom
# madmom 0.16.1 predates Python 3.10's collections cleanup
sed -i '' 's/^from collections import MutableSequence/from collections.abc import MutableSequence/' beat/.venv/lib/python3.10/site-packages/madmom/processors.py
uv pip install --python $P scipy sounddevice python-osc
# madmom imports pkg_resources, gone from setuptools 81; something above pulls setuptools up, so pin it last
uv pip install --python $P "setuptools<70"
$P -c "import madmom, sounddevice, pythonosc; print('beat tracker ready, madmom', madmom.__version__)"
