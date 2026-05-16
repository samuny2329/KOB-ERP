"""Subprocess wrapper around `bin/frepple` engine.

Runs the C++ solver in an isolated subprocess so a crash, OOM, or infinite
loop cannot bring down the Odoo worker. The subprocess inherits a clean
environment with `LD_LIBRARY_PATH` and `FREPPLE_HOME` pointing at the
addon-bundled engine artifacts.

Pipeline:
    input.xml (frePPLe schema)
        ↓ subprocess /opt/thiti/bin/frepple input.xml
    bin/frepple writes output.<N>.xml in cwd
        ↓ read output.1.xml (constrained plan = plantype 1)
    output bytes returned to caller for parsing

Engine binary location is configurable via system parameter
`thiti.engine_binary_path` (default `/opt/thiti/bin/frepple`).
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from odoo import _, api, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

DEFAULT_BINARY = "/opt/thiti/bin/frepple"
DEFAULT_LIB_DIR = "/opt/thiti/lib"
DEFAULT_TIMEOUT_SEC = 600


class ThitiSolverWrapper(models.AbstractModel):
    _name = "thiti.solver.wrapper"
    _description = "Thiti Solver Wrapper (subprocess to bin/frepple)"

    @api.model
    def _get_binary_path(self) -> Path:
        param = self.env["ir.config_parameter"].sudo()
        return Path(param.get_param("thiti.engine_binary_path", DEFAULT_BINARY))

    @api.model
    def _get_lib_dir(self) -> Path:
        param = self.env["ir.config_parameter"].sudo()
        return Path(param.get_param("thiti.engine_lib_dir", DEFAULT_LIB_DIR))

    @api.model
    def _get_timeout(self) -> int:
        param = self.env["ir.config_parameter"].sudo()
        return int(param.get_param("thiti.engine_timeout_sec", DEFAULT_TIMEOUT_SEC))

    @api.model
    def run(self, input_xml: bytes, plan_type: str = "1",
            constraint: str = "15", loglevel: int = 1) -> dict:
        """Invoke the engine subprocess.

        Returns dict with keys:
            output_xml: bytes (constrained plan)
            stdout: str
            stderr: str
            returncode: int
            outputs: list[(name, bytes)] all output XML files
        """
        binary = self._get_binary_path()
        lib_dir = self._get_lib_dir()
        timeout = self._get_timeout()

        if not binary.exists():
            raise UserError(
                _("Engine binary not found at %s.\n\n"
                  "Build the frePPLe engine and copy bin/frepple + "
                  "libfrepple.so* to that path, or override the location "
                  "via the system parameter `thiti.engine_binary_path`.") % binary
            )

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = (
            f"{lib_dir}:" + env.get("LD_LIBRARY_PATH", "")
        )
        env["FREPPLE_HOME"] = str(binary.parent)
        env["plantype"] = plan_type
        env["constraint"] = constraint
        env["loglevel"] = str(loglevel)
        env["supply"] = "1"
        env["nowebservice"] = "1"

        with tempfile.TemporaryDirectory(prefix="thiti_run_") as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.xml"
            input_path.write_bytes(input_xml)

            try:
                proc = subprocess.run(
                    [str(binary), str(input_path)],
                    cwd=tmp_path,
                    env=env,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                _logger.error("Engine timed out after %ss", timeout)
                raise UserError(
                    _("Engine timed out after %s seconds.") % timeout
                ) from exc

            outputs: list[tuple[str, bytes]] = []
            for path in sorted(tmp_path.glob("output*.xml")):
                outputs.append((path.name, path.read_bytes()))

            # Serializer's <?python ?> block writes "output.xml" by default.
            # Older Phase 0 samples emit output.1.xml / output.2.xml — fall
            # back to those when present so the wrapper stays compatible.
            primary_output = b""
            for preferred in ("output.xml", "output.1.xml"):
                for name, blob in outputs:
                    if name == preferred:
                        primary_output = blob
                        break
                if primary_output:
                    break
            if not primary_output and outputs:
                primary_output = outputs[0][1]

            return {
                "output_xml": primary_output,
                "stdout": proc.stdout.decode("utf-8", errors="replace"),
                "stderr": proc.stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
                "outputs": outputs,
            }
