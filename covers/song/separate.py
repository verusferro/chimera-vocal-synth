"""audio-separator, with one fix for AMD GPUs (ROCm): the RoFormer models' attention runs on
PyTorch's plain "math" kernel. On a Radeon RX 9070 XT (gfx1201, ROCm 6.4 PyTorch) the
memory-efficient kernel the library picks gives wrong output (the stems come out as noise),
while the math kernel matches the CPU result. On a CPU or an NVIDIA GPU nothing changes.

  python covers/song/separate.py SONG.wav -m bs_roformer_vocals_resurrection_unwa.ckpt \
      --model_file_dir covers/vendor/models --output_dir covers/work/<song>/stems --output_format WAV

Takes audio-separator's own arguments. Run it with the Python that has audio-separator and a GPU
PyTorch (docs/setup.md: the ROCm venv needs LD_LIBRARY_PATH=/opt/rocm/lib under WSL).
"""
import sys

import torch
from audio_separator.separator.uvr_lib_v5.roformer import attend
from audio_separator.utils.cli import main

if torch.version.hip:
    attend._sdpa_backends = lambda config: [torch.nn.attention.SDPBackend.MATH]

sys.exit(main())
