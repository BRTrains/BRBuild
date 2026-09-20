import logging
import os
import shutil
import subprocess
import sys
from importlib import util
from pathlib import Path

from Tools.StreamDuplicator import strip_ansi

logger = logging.getLogger(__name__)


class NmlCompiler:
    def __init__(self):
        pass

    def _resolve_nml(self) -> Path | None:
        """Locate the directory that holds the nml package to compile with.

        A local ../nml checkout next to BRBuild takes priority over the nml
        installed in the running interpreter, matching the historical behaviour.
        The returned path is the directory containing the package (not the package
        folder itself), because it is handed to the child as PYTHONPATH.
        """
        nml_path = Path(__file__).resolve().parents[2] / "nml"

        if nml_path.exists() and nml_path.is_dir():
            logger.info(f"Local instance found, using NML from {nml_path}")
            return nml_path

        found_nml = util.find_spec("nml")
        if found_nml is None:
            logger.error("nml is not installed. You can get it using 'pip install nml'")
            return None

        locations = list(found_nml.submodule_search_locations or [])
        if not locations and found_nml.origin:
            locations = [str(Path(found_nml.origin).parent)]

        if not locations:
            logger.error(f"Could not determine the location of the installed nml package ({found_nml}).")
            return None

        logger.info(f"No NML found in {nml_path}. Trying to use nml from python")
        package_dir = Path(locations[0])
        if package_dir.name == "nml":
            return package_dir.parent
        return package_dir

    def compile(self, nml_filepath, lang_folder=None, log_nml_output=False):
        nml_path = self._resolve_nml()
        if nml_path is None:
            return -1

        # Prepare parameters
        parameters = [nml_filepath]

        if lang_folder:
            parameters.extend(["-l", lang_folder])

        logger.info(f"Compiling with parameters: {parameters}")

        # nmlc keeps its language, string and constant registries in module-level
        # globals, so a second in-process compile inherits the first project's state
        # and aborts with 'String name "..." is used multiple times'. Run each compile
        # in its own interpreter so one project cannot leak into the next.
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(nml_path), *filter(None, [environment.get("PYTHONPATH")])]
        )
        command = [
            sys.executable,
            "-c",
            "import sys; from nml.main import main; sys.exit(main(sys.argv[1:]))",
            *parameters,
        ]

        # Compile. Log output to file if requested, otherwise just print to console. Always print to console.
        log_file = open("nmlc.log", "w") if log_nml_output else None
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=environment,
            )

            # nmlc's output is written straight to the console; log files are kept
            # free of colour escapes by the parent instead of nmlc itself.
            if log_file is not None:
                log_file.write(strip_ansi(completed.stdout))
                log_file.write("NML Finished\n")

            sys.stdout.write(completed.stdout)
            sys.stdout.flush()
        finally:
            if log_file is not None:
                log_file.close()

        if completed.returncode != 0:
            logger.error(f"NML compilation failed with exit code {completed.returncode}")
            raise SystemExit(completed.returncode)

        logger.info("Finished compiling grf file")
        return nml_filepath.replace(".nml", ".grf")

    def copy_newgrf(self, grf_filepath):
        try:
            src = Path(grf_filepath).expanduser().resolve()
        except Exception as e:
            logger.error(f"Error occurred while resolving path: {grf_filepath}. {e}")
            return None

        if not src.is_file():
            raise FileNotFoundError(f"Source file not found: {src}")

        # Get the user's Documents folder in a cross-platform way
        documents = Path.home() / "Documents"
        target_dir = documents / "OpenTTD" / "newgrf"

        if not target_dir.exists():
            logger.info(f"Target folder not found: {target_dir}, trying alternate")
            documents_alt = Path.home() / "OneDrive" / "Documents"
            target_dir = documents_alt / "OpenTTD" / "newGRF"

        if not target_dir.exists():
            logger.error(f"Target folder not found: {target_dir}")
            return None

        dest = target_dir / src.name
        try:
            shutil.copy2(src, dest)
            logger.info(f"Copied to: {dest}")
            return dest
        except Exception as e:
            logger.error(f"Copy failed: {e}")
            return None