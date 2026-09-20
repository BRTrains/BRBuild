import argparse
import logging
import shutil
import sys
from pathlib import Path

from Builder import Builder, ProjectFinder

logger = logging.getLogger("Run")


def run_build(project_name=None, log_nml_output=False, release=False):
    ''' Orchestrator for the build process. If a project name is provided, it will attempt to build that specific project. Otherwise, it will search for all projects in the parent directory and build them. '''
    finder = ProjectFinder()

    if project_name:
        logger.info(f"Attempting to build specified project: {project_name}")

        # Build specific project
        project = finder.find_project(project_name)

        if not project:
            logger.error(f"Project '{project_name}' not found.")
            return False

        builder = Builder()
        builder.build(project, log_nml_output=log_nml_output, release=release)
    else:
        logger.debug("No specific project specified. Searching for all projects in the parent directory.")
        # Find and build all projects
        
        if not finder.projects:
            logger.debug("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
            return False
        
        logger.info(f"Found projects: {finder.projects}")
        builder = Builder()
        
        for project in finder.projects:
            builder.build(project, log_nml_output=log_nml_output, release=release)
    
    return True

def reset_graphics(project_name=None):
    ''' Ingest new spritesheets or restore them from ingested/ backups. '''
    finder = ProjectFinder()

    if project_name:
        project = finder.find_project(project_name)

        if not project:
            logger.error(f"Project '{project_name}' not found.")
            return False

        projects = [project]
    else:
        if not finder.projects:
            logger.debug("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
            return False

        projects = finder.projects

    reset_count = sum(reset_project_graphics(project) for project in projects)
    logger.info(f"Reset or ingested {reset_count} spritesheet(s).")
    return True

def reset_project_graphics(project) -> int:
    ''' Ingest new spritesheets, otherwise restore each sheet from its ingested/ source. '''
    count = 0

    # The latest ingested source for each vehicle, keyed by the vehicle's sheet path.
    ingested_paths = {
        ingested_path.parent.parent / ingested_path.name: ingested_path
        for ingested_path in project.path.rglob("ingested/*.png")
    }
    # Legacy `original/` folders and `<name>_original.png` siblings predate `ingested/`.
    for legacy_path in project.path.rglob("original/*.png"):
        base_path = legacy_path.parent.parent / legacy_path.name
        ingested_paths.setdefault(base_path, legacy_path)
    for legacy_path in project.path.rglob("*_original.png"):
        base_path = legacy_path.with_name(legacy_path.name.replace("_original.png", ".png"))
        ingested_paths.setdefault(base_path, legacy_path)
    # A sheet that failed to build is kept in `error/`; it is still the newest source we have.
    for error_path in project.path.rglob("error/*.png"):
        base_path = error_path.parent.parent / error_path.name
        ingested_paths.setdefault(base_path, error_path)

    new_paths = {}
    for new_folder in project.path.rglob("new"):
        if not new_folder.is_dir():
            continue

        candidates = sorted(
            path for path in new_folder.iterdir() if path.is_file() and path.suffix.lower() == ".png"
        )
        if len(candidates) > 1:
            raise ValueError(f"Expected one PNG in '{new_folder}', found {len(candidates)}.")
        if not candidates:
            continue

        yaml_path = new_folder.parent / f"{new_folder.parent.name}.yaml"
        if not yaml_path.is_file():
            logger.warning(f"Cannot determine spritesheet path for '{new_folder}'; expected '{yaml_path}'.")
            continue
        new_paths[yaml_path.with_suffix(".png")] = candidates[0]

    for base_path in sorted(set(ingested_paths) | set(new_paths)):
        new_path = new_paths.get(base_path)
        if new_path is not None:
            ingested_path = base_path.parent / "ingested" / base_path.name
            ingested_path.parent.mkdir(parents=True, exist_ok=True)
            if ingested_path.exists():
                ingested_path.unlink()
            shutil.move(new_path, ingested_path)
            if base_path.exists():
                base_path.unlink()
            shutil.copy2(ingested_path, base_path)
            logger.info(f"Ingested '{ingested_path}' from '{new_path.parent}'.")
            count += 1
            continue

        ingested_path = ingested_paths[base_path]
        # An errored sheet stays in error/ as the record of the failed attempt; only a legacy
        # backup is migrated, so a reset does not quietly reclassify it as a good ingestion.
        if ingested_path.parent.name not in {"ingested", "error"}:
            migrated_path = base_path.parent / "ingested" / base_path.name
            migrated_path.parent.mkdir(parents=True, exist_ok=True)
            if migrated_path.exists():
                migrated_path.unlink()
            shutil.move(str(ingested_path), str(migrated_path))
            ingested_path = migrated_path

        if base_path.exists():
            base_path.unlink()

        if ingested_path.is_file():
            shutil.copy2(ingested_path, base_path)
        else:
            continue
        logger.info(f"Reset '{base_path}' from '{ingested_path}'")
        count += 1

    return count

def configure_logging(enable_file: bool, log_file: str = "build.log") -> None:
    logger = logging.getLogger()
    # clear existing handlers
    logger.handlers.clear()
    # set root logger level to DEBUG to capture all messages; individual handlers will filter as needed
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s %(message)s")
    )
    logger.addHandler(console_handler)

    # Only log to file if --log argument is passed
    if enable_file:
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)-30s %(message)s")
        )
        logger.addHandler(file_handler)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Build BRBuild-compatible newGRF projects"
    )

    parser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project name to build (optional; will search for projects in the parent directory if omitted)"
    )

    parser.add_argument(
        "--log",
        nargs="?",
        const="build.log",
        default=None,
        help="Enable logging to a file. Optionally specify filename (default: build.log)"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List discovered projects and exit without building"
    )

    parser.add_argument(
        "--release",
        action="store_true",
        help="Lock sprite IDs and deprecate savegame-breaking or removed variants"
    )

    reset_graphics_group = parser.add_mutually_exclusive_group()

    reset_graphics_group.add_argument(
        "--reset-graphics",
        action="store_true",
        help="Restore vehicle spritesheets from original/ backups (if present) and continue with the build"
    )

    reset_graphics_group.add_argument(
        "--reset-graphics-only",
        action="store_true",
        help="Restore vehicle spritesheets from original/ backups (if present) and exit without building"
    )

    return parser.parse_args()

def clean_working_data():
    for folder_name in ("WorkingData", "Build"):
        folder = Path(folder_name)

        if not folder.exists():
            continue

        for path in folder.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

def clean_logs():
    for file_name in ("nmlc.log", "build.log"):
        path = Path(file_name)

        if path.exists() and path.is_file():
            path.unlink()

if __name__ == "__main__":
    args = parse_args()

    clean_logs()

    configure_logging(
        enable_file=args.log is not None,
        log_file=args.log or "build.log"
    )

    logger = logging.getLogger("Run")

    logger.debug(f"Parsed arguments: {args}")

    # If the user only wants to list projects, do that and exit without building
    if getattr(args, "list", False):
        finder = ProjectFinder()
        if not finder.projects:
            print("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
        else:
            print("Discovered projects:")
            for project in finder.projects:
                print(f" - {project.name} (path: {project.path})")
        raise SystemExit(0)

    # Reset graphics before building when requested.
    if getattr(args, "reset_graphics", False) or getattr(args, "reset_graphics_only", False):
        success = reset_graphics(args.project)
        if not success or getattr(args, "reset_graphics_only", False):
            raise SystemExit(0 if success else 1)

    logger.info("Cleaning working data")
    clean_working_data()

    logger.info("Starting build")

    try: 
        success = run_build(args.project, args.log is not None, args.release)
    except Exception as exc:
        logger.exception("Build failed with an exception:" + str(exc))
        success = False

    logger.info(
        "Build %s",
        "succeeded" if success else "failed"
    )

    raise SystemExit(0 if success else 1)