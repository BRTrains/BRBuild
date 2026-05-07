from contextlib import redirect_stdout
from importlib import util
from pathlib import Path
import pathlib
import shutil
import sys
import logging

from Tools.StreamDuplicator import StreamDuplicator
logger = logging.getLogger(__name__)

class NmlCompiler:
    def __init__(self):
        pass

    def compile(self, nml_filepath, lang_folder = None):
        nml_path = Path(__file__).resolve().parents[2] / "nml"
        nmlc = None

        # Try local ../nml first        
        if nml_path.exists() and nml_path.is_dir():
            print("Local instance found, using NML from ", nml_path)
            sys.path.insert(0, str(nml_path))
            try:
                import nml.main as nmlc
            except ImportError:
                raise                
                nmlc = None

        # If local not available, try installed package
        if nmlc is None:
            found_nml = util.find_spec("nml")
            if found_nml is not None:
                print(f"No NML found in {nml_path}. Trying to use nml from python")
                import nml.main as nmlc
            else:
                print("nml is not installed. You can get it using 'pip install nml'")
                return -1

        # Prepare parameters
        parameters = [nml_filepath]

        if lang_folder:
            parameters.extend(["-l", lang_folder])

        logger.info(f"Compiling with parameters: {parameters}")

        # Compile
        with open("nmlc.log", "w") as log_file:
            duplicator = StreamDuplicator(sys.stdout, log_file, enable_a=True, enable_b=True)

            try:
                with redirect_stdout(duplicator):
                    nmlc.main(parameters)
            except SystemExit:
                log_file.write("NML Finished\n")

        logger.info("Finished compiling grf file")
        return nml_filepath.replace(".nml", ".grf")

    def copy_newgrf(self, grf_filepath):
        try:
            src = Path(grf_filepath).expanduser().resolve()
        except Exception as e:
            print(str(grf_filepath))
            print(e)

        if not src.is_file():
            raise FileNotFoundError(f"Source file not found: {src}")

        # Get the user's Documents folder in a cross-platform way
        documents = Path.home() / "Documents"
        target_dir = documents / "OpenTTD" / "newgrf"

        if not target_dir.exists():
            print(f"Target folder not found: {target_dir}, trying alternate")
            documents_alt = Path.home() / "OneDrive" / "Documents"
            target_dir = documents_alt / "OpenTTD" / "newGRF"

        if not target_dir.exists():
            print(f"Target folder not found: {target_dir}")
            return None

        dest = target_dir / src.name
        try:
            shutil.copy2(src, dest)
            print(f"Copied to: {dest}")
            return dest
        except Exception as e:
            print(f"Copy failed: {e}")
            return None