"""Pure ctypes path: load libfrepple.so directly and call the public C API
(FreppleInitialize, FreppleReadXMLFile, FreppleSaveFile, FreppleExit).
Avoids relying on the bin/frepple wrapper. Mirrors the future Odoo addon
solver-wrapper subprocess pattern."""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from pathlib import Path


def load_engine(lib_path: Path) -> ctypes.CDLL:
    if not lib_path.exists():
        raise FileNotFoundError(f"libfrepple.so not found at {lib_path}")
    lib = ctypes.CDLL(str(lib_path))

    lib.FreppleVersion.restype = ctypes.c_char_p
    lib.FreppleVersion.argtypes = []

    lib.FreppleInitialize.restype = None
    lib.FreppleInitialize.argtypes = [ctypes.c_bool]

    lib.FreppleReadXMLFile.restype = None
    lib.FreppleReadXMLFile.argtypes = [
        ctypes.c_char_p,  # filename
        ctypes.c_bool,    # validate
        ctypes.c_bool,    # validate_only
        ctypes.c_bool,    # one more flag in this signature
    ]

    lib.FreppleSaveFile.restype = None
    lib.FreppleSaveFile.argtypes = [ctypes.c_char_p]

    lib.FreppleExit.restype = None
    lib.FreppleExit.argtypes = []

    return lib


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", type=Path,
                        default=Path("/src/bin/libfrepple.so"))
    parser.add_argument("--xml", type=Path,
                        default=Path("/src/test/constraints_material_1/"
                                     "constraints_material_1.xml"))
    parser.add_argument("--out", type=Path,
                        default=Path("/tmp/poc_ctypes_out.xml"))
    args = parser.parse_args()

    os.environ.setdefault("FREPPLE_HOME", str(args.lib.parent))

    print(f"=== ctypes POC ===")
    print(f"lib  = {args.lib}")
    print(f"xml  = {args.xml}")
    print(f"out  = {args.out}")

    lib = load_engine(args.lib)
    version = lib.FreppleVersion().decode("utf-8")
    print(f"frePPLe version: {version}")

    t0 = time.monotonic()
    lib.FreppleInitialize(True)
    t_init = time.monotonic() - t0

    t0 = time.monotonic()
    lib.FreppleReadXMLFile(str(args.xml).encode("utf-8"), False, False, False)
    t_read = time.monotonic() - t0

    t0 = time.monotonic()
    lib.FreppleSaveFile(str(args.out).encode("utf-8"))
    t_save = time.monotonic() - t0

    lib.FreppleExit()

    ok = args.out.exists() and args.out.stat().st_size > 0
    print(f"init: {t_init:.3f}s  read+solve: {t_read:.3f}s  save: {t_save:.3f}s")
    print(f"output: {args.out} ({args.out.stat().st_size if args.out.exists() else 0} bytes)")
    print(f"=== verdict: {'PASS' if ok else 'FAIL'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
