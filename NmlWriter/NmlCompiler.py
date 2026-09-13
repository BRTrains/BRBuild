import logging
import shutil
import sys
from contextlib import redirect_stdout
from importlib import util
from pathlib import Path

from Tools.StreamDuplicator import StreamDuplicator

logger = logging.getLogger(__name__)


class NmlCompiler:
    def __init__(self):
        pass

    def compile(self, nml_filepath, lang_folder=None, log_nml_output=False):
        nml_path = Path(__file__).resolve().parents[2] / "nml"
        nmlc = None

        # Try local ../nml first
        if nml_path.exists() and nml_path.is_dir():
            logger.info(f"Local instance found, using NML from {nml_path}")
            sys.path.insert(0, str(nml_path))
            try:
                import nml.main as nmlc
            except ImportError:
                logger.warning(f"Could not import NML from local path {nml_path}")
                nmlc = None

        # If local not available, try installed package
        if nmlc is None:
            found_nml = util.find_spec("nml")
            if found_nml is not None:
                logger.info(f"No NML found in {nml_path}. Trying to use nml from python")
                import nml.main as nmlc
            else:
                logger.error("nml is not installed. You can get it using 'pip install nml'")
                return -1

        # Prepare parameters
        parameters = [nml_filepath]

        if lang_folder:
            parameters.extend(["-l", lang_folder])

        logger.info(f"Compiling with parameters: {parameters}")

        # Compile. Log output to file if requested, otherwise just print to console. Always print to console.
        try:
            if log_nml_output:
                with open("nmlc.log", "w") as log_file:
                    duplicator = StreamDuplicator(sys.stdout, log_file, enable_a=True, enable_b=True)

                    with redirect_stdout(duplicator):
                        nmlc.main(parameters)

                    log_file.write("NML Finished\n")
            else:
                nmlc.main(parameters)

        except SystemExit as e:
            if e.code != 0:
                logger.exception(f"NML compilation failed with SystemExit {e}")
                raise

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