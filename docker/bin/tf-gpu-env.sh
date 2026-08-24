#!/bin/sh
# Source this from a worker command:  . /usr/local/bin/tf-gpu-env.sh
#
# On a CPU-only host this is a no-op, so one image and one worker command work
# whether or not a GPU was passed in.
#
# When a GPU is present, two things are needed before TensorFlow initializes:
#   1. LD_LIBRARY_PATH covering the CUDA libs shipped by tensorflow[and-cuda],
#      otherwise TF logs "Cannot dlopen some GPU libraries" and stays on CPU.
#   2. XLA_FLAGS pointing at a CUDA data dir containing
#      nvvm/libdevice/libdevice.10.bc, otherwise XLA compilation of the
#      detector fails with "libdevice not found at ./libdevice.10.bc".
#
# tf-gpu-paths.py finds those paths; this script only decides what to export.
# Splitting it that way is not just tidiness: glibc caches the library search
# path when a process starts, so LD_LIBRARY_PATH has to be in the environment
# before python execs. Assigning it from inside python would come too late for
# the dlopen that TensorFlow does on import.
#
# Keras 2/3 selection is left alone: retina-face already sets
# TF_USE_LEGACY_KERAS itself on import, same as on CPU.

# Both the entrypoint and a compose command override may source this, and the
# exports below append to what is already there, so a second run would duplicate
# every entry.
if [ -n "${TF_GPU_ENV_CONFIGURED:-}" ]; then
  echo "tf-gpu-env: already configured, nothing to do"
# The NVIDIA container runtime creates /dev/nvidiactl. Its absence means no GPU
# reached this container, and TensorFlow should be left on CPU untouched.
elif [ ! -e /dev/nvidiactl ]; then
  echo "tf-gpu-env: no NVIDIA device present, leaving TensorFlow on CPU"
  TF_GPU_ENV_CONFIGURED=cpu
  export TF_GPU_ENV_CONFIGURED
else
  # /usr/local/bin holds the copy baked into the image; /app/docker/bin is what a
  # compose bind mount shadows during local development.
  tf_gpu_paths_script=""
  for tf_gpu_candidate in \
    "${TF_GPU_PATHS_SCRIPT:-}" \
    /usr/local/bin/tf-gpu-paths.py \
    /app/docker/bin/tf-gpu-paths.py
  do
    if [ -n "$tf_gpu_candidate" ] && [ -f "$tf_gpu_candidate" ]; then
      tf_gpu_paths_script="$tf_gpu_candidate"
      break
    fi
  done

  if [ -z "$tf_gpu_paths_script" ]; then
    echo "tf-gpu-env: tf-gpu-paths.py not found; cannot configure GPU libraries" >&2
  else
    # Reading through a file rather than a pipe keeps the loop in this shell; a
    # pipeline would assign in a subshell and lose everything. The case arms are
    # also an allow-list, so an unexpected line cannot set anything else.
    tf_gpu_paths_out=$(mktemp)
    if python "$tf_gpu_paths_script" > "$tf_gpu_paths_out"; then
      while IFS='=' read -r tf_gpu_key tf_gpu_value; do
        case "$tf_gpu_key" in
          NVIDIA_LIB_DIRS) NVIDIA_LIB_DIRS="$tf_gpu_value" ;;
          CUDA_DATA_DIR) CUDA_DATA_DIR="$tf_gpu_value" ;;
          LIBDEVICE_FILE) LIBDEVICE_FILE="$tf_gpu_value" ;;
        esac
      done < "$tf_gpu_paths_out"
    else
      echo "tf-gpu-env: tf-gpu-paths.py failed; cannot configure GPU libraries" >&2
    fi
    rm -f "$tf_gpu_paths_out"
  fi

  if [ -n "${NVIDIA_LIB_DIRS:-}" ]; then
    LD_LIBRARY_PATH="${NVIDIA_LIB_DIRS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export LD_LIBRARY_PATH
  fi

  if [ -z "${CUDA_DATA_DIR:-}" ] && [ -n "${LIBDEVICE_FILE:-}" ]; then
    CUDA_DATA_DIR=/tmp/tf-cuda
    mkdir -p "${CUDA_DATA_DIR}/nvvm/libdevice"
    cp -f "$LIBDEVICE_FILE" "${CUDA_DATA_DIR}/nvvm/libdevice/libdevice.10.bc"
    # The worker drops to an unprivileged user after this runs.
    chmod -R a+rX "${CUDA_DATA_DIR}"
  fi

  if [ -n "${CUDA_DATA_DIR:-}" ]; then
    XLA_FLAGS="--xla_gpu_cuda_data_dir=${CUDA_DATA_DIR}${XLA_FLAGS:+ $XLA_FLAGS}"
    export XLA_FLAGS
  else
    echo "tf-gpu-env: libdevice.10.bc not found; XLA compilation on GPU will fail" >&2
  fi

  : "${TF_FORCE_GPU_ALLOW_GROWTH:=true}"
  : "${TF_GPU_ALLOCATOR:=cuda_malloc_async}"
  export TF_FORCE_GPU_ALLOW_GROWTH TF_GPU_ALLOCATOR

  TF_GPU_ENV_CONFIGURED=gpu
  export TF_GPU_ENV_CONFIGURED

  echo "tf-gpu-env: NVIDIA device present, TensorFlow configured for GPU"

  # Sourced, so leave nothing of ours behind in the caller's shell.
  unset NVIDIA_LIB_DIRS CUDA_DATA_DIR LIBDEVICE_FILE
  unset tf_gpu_paths_script tf_gpu_candidate tf_gpu_paths_out tf_gpu_key tf_gpu_value
fi
