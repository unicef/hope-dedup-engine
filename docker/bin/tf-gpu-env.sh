#!/bin/sh
# Source this from a GPU worker command:  . /app/docker/bin/tf-gpu-env.sh
#
# Two things are needed before TensorFlow initializes:
#   1. LD_LIBRARY_PATH covering the CUDA libs shipped by tensorflow[and-cuda],
#      otherwise TF logs "Cannot dlopen some GPU libraries" and stays on CPU.
#   2. XLA_FLAGS pointing at a CUDA data dir containing
#      nvvm/libdevice/libdevice.10.bc, otherwise XLA compilation of the
#      detector fails with "libdevice not found at ./libdevice.10.bc".
#
# Keras 2/3 selection is left alone: retina-face already sets
# TF_USE_LEGACY_KERAS itself on import, same as on CPU.

eval "$(python - <<'PY'
from pathlib import Path
import site

site_dirs = [Path(d) for d in site.getsitepackages()]

lib_dirs = [
    package / "lib"
    for site_dir in site_dirs
    for package in sorted((site_dir / "nvidia").glob("*"))
    if (package / "lib").is_dir()
]
if lib_dirs:
    print(f"NVIDIA_LIB_DIRS='{':'.join(str(p) for p in lib_dirs)}'")

# Preferred layout ships with nvidia-cuda-nvcc; triton (pulled in by torch)
# carries a bare copy we can link into the layout XLA expects.
for site_dir in site_dirs:
    candidate = site_dir / "nvidia/cuda_nvcc"
    if (candidate / "nvvm/libdevice/libdevice.10.bc").is_file():
        print(f"CUDA_DATA_DIR='{candidate}'")
        break
    bare = site_dir / "triton/backends/nvidia/lib/libdevice.10.bc"
    if bare.is_file():
        print(f"LIBDEVICE_FILE='{bare}'")
        break
PY
)"

if [ -n "$NVIDIA_LIB_DIRS" ]; then
  LD_LIBRARY_PATH="${NVIDIA_LIB_DIRS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export LD_LIBRARY_PATH
fi

if [ -z "$CUDA_DATA_DIR" ] && [ -n "$LIBDEVICE_FILE" ]; then
  CUDA_DATA_DIR=/tmp/tf-cuda
  mkdir -p "${CUDA_DATA_DIR}/nvvm/libdevice"
  cp -f "$LIBDEVICE_FILE" "${CUDA_DATA_DIR}/nvvm/libdevice/libdevice.10.bc"
fi

if [ -n "$CUDA_DATA_DIR" ]; then
  XLA_FLAGS="--xla_gpu_cuda_data_dir=${CUDA_DATA_DIR}${XLA_FLAGS:+ $XLA_FLAGS}"
  export XLA_FLAGS
else
  echo "tf-gpu-env: libdevice.10.bc not found; XLA compilation on GPU will fail" >&2
fi

: "${TF_FORCE_GPU_ALLOW_GROWTH:=true}"
: "${TF_GPU_ALLOCATOR:=cuda_malloc_async}"
export TF_FORCE_GPU_ALLOW_GROWTH TF_GPU_ALLOCATOR
