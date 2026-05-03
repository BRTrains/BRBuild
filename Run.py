import argparse
import logging
import sys
from pathlib import Path
from Builder import ProjectFinder, Builder
from Project.Project import Project

def run_build(project_name=None):
    ''' Orchestrator for the build process. If a project name is provided, it will attempt to build that specific project. Otherwise, it will search for all projects in the parent directory and build them. '''
    if project_name:
        logging.info(f"Attempting to build specified project: {project_name}")
        # Build specific project
        project = Project(project_name)

        builder = Builder()
        builder.build(project)
    else:
        logging.info("No specific project specified. Searching for all projects in the parent directory.")
        # Find and build all projects
        finder = ProjectFinder()
        
        if not finder.projects:
            logging.info("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
            return False
        
        logging.info(f"Found projects: {finder.projects}")
        builder = Builder()
        
        for project in finder.projects:
            builder.build(project)
    
    return True

def configure_logging(enable_file: bool, log_file: str = "build.log"):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s %(message)s")
    )
    logger.addHandler(console_handler)

    if enable_file:
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
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

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    configure_logging(
        enable_file=args.log is not None,
        log_file=args.log or "build.log"
    )

    logging.info("Starting build")

    try: 
        success = run_build(args.project)
    except Exception as exc:
        logging.exception("Build failed with an exception:" + str(exc))
        success = False

    logging.info(
        "Build %s",
        "succeeded" if success else "failed"
    )

    raise SystemExit(0 if success else 1)