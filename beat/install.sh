#!/bin/bash
# The beat tracker's environment: Python 3.10 (madmom needs it), the numpy it builds against,
# PyTorch, BeatNet, audio in and OSC out. Run once from the repo root; takes a few minutes.
#     bash beat/install.sh
set -e
cd "$(dirname "$0")/.."
brew list portaudio >/dev/null 2>&1 || brew install portaudio
uv venv --python 3.10 beat/.venv
P=beat/.venv/bin/python
uv pip install --python $P "numpy<1.24" "cython<3" "setuptools<70" wheel
uv pip install --python $P --no-build-isolation madmom
# madmom 0.16.1 predates Python 3.10's collections cleanup
sed -i '' 's/^from collections import MutableSequence/from collections.abc import MutableSequence/' beat/.venv/lib/python3.10/site-packages/madmom/processors.py
uv pip install --python $P torch torchaudio librosa matplotlib pyaudio sounddevice python-osc
uv pip install --python $P --no-deps BeatNet
$P -c "import BeatNet, madmom, torch, sounddevice, pythonosc; print('beat tracker ready, torch', torch.__version__)"
