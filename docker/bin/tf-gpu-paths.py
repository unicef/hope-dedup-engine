"""Locate the CUDA libraries that ``tensorflow[and-cuda]`` ships inside site-packages.

Run by ``tf-gpu-env.sh``, which turns the ``KEY=VALUE`` lines printed here into
``LD_LIBRARY_PATH`` and ``XLA_FLAGS``. Restricted to the standard library on
purpose: this executes at container start, before Django or the app package are
importable, and before TensorFlow has been touched.

Keys printed, each only when the corresponding path exists:

``NVIDIA_LIB_DIRS``
    Colon-joined ``nvidia/*/lib`` directories to prepend to ``LD_LIBRARY_PATH``.
``CUDA_DATA_DIR``
    A directory already laid out as ``nvvm/libdevice/libdevice.10.bc``, which XLA
    can be pointed at as-is.
``LIBDEVICE_FILE``
    A bare ``libdevice.10.bc``; the caller has to stage it into the layout above.
"""

import site
from pathlib import Path

LIBDEVICE = "libdevice.10.bc"


def nvidia_lib_dirs(site_dirs: list[Path]) -> list[Path]:
    return [
        package / "lib"
        for site_dir in site_dirs
        for package in sorted((site_dir / "nvidia").glob("*"))
        if (package / "lib").is_dir()
    ]


def libdevice_location(site_dirs: list[Path]) -> tuple[str, Path] | None:
    """Find libdevice, preferring a tree XLA can consume without help.

    ``nvidia-cuda-nvcc`` ships the ``nvvm/libdevice`` layout XLA expects. triton,
    pulled in indirectly by torch, carries only the bare bitcode file, so it is
    the weaker match and the caller has more work to do with it.
    """
    for site_dir in site_dirs:
        nvcc = site_dir / "nvidia/cuda_nvcc"
        if (nvcc / "nvvm/libdevice" / LIBDEVICE).is_file():
            return "CUDA_DATA_DIR", nvcc
        bare = site_dir / "triton/backends/nvidia/lib" / LIBDEVICE
        if bare.is_file():
            return "LIBDEVICE_FILE", bare
    return None


def main() -> None:
    site_dirs = [Path(directory) for directory in site.getsitepackages()]

    if lib_dirs := nvidia_lib_dirs(site_dirs):
        print("NVIDIA_LIB_DIRS=" + ":".join(str(path) for path in lib_dirs))

    if location := libdevice_location(site_dirs):
        key, path = location
        print(f"{key}={path}")


if __name__ == "__main__":
    main()
