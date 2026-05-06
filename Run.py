import argparse
import logging
import sys
from pathlib import Path
from Builder import ProjectFinder, Builder
from Project.Project import Project

def run_build(project_name=None):
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
        builder.build(project)
    else:
        logger.debug("No specific project specified. Searching for all projects in the parent directory.")
        # Find and build all projects
        
        if not finder.projects:
            logger.debug("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
            return False
        
        logger.info(f"Found projects: {finder.projects}")
        builder = Builder()
        
        for project in finder.projects:
            builder.build(project)
    
    return True

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

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    configure_logging(
        enable_file=args.log is not None,
        log_file=args.log or "build.log"
    )

    logger = logging.getLogger("Run")

    logger.info("Starting build")

    try: 
        success = run_build(args.project)
    except Exception as exc:
        logger.exception("Build failed with an exception:" + str(exc))
        success = False

    logger.info(
        "Build %s",
        "succeeded" if success else "failed"
    )

    raise SystemExit(0 if success else 1)