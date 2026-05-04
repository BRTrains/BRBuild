import sys, logging
logger = logging.getLogger(__name__)
from pathlib import Path

import yaml
from Project.Project import Project

class ProjectFinder:
    '''Finds all projects in the parent directory that contain a "BRBuild.yaml" file, indicating they can be built by BRBuild.'''
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.parent_folder = self.project_root.parent

        logger.debug(f"ProjectFinder initialized. Looking for projects in: {self.parent_folder}")

        self.projects = self.find_projects()

    def find_projects(self):
        # Find all folders in the directory above the project root that contain a "BRBuild.yaml" file
        logger.debug(f"Searching for projects in: {self.parent_folder}")
        projects = []

        for p in self.parent_folder.iterdir():
            config_file = p / "BRBuild.yaml"
            if not p.is_dir() or not config_file.is_file():
                continue

            try:
                config = yaml.safe_load(config_file.read_text())
            except Exception as exc:
                logger.exception(f"Failed to load {config_file}: {exc}")
                continue

            if not isinstance(config, dict):
                logger.error(f"Invalid BRBuild.yaml in {p}: expected a YAML mapping")
                continue

            project_config = config.get("project")
            if not isinstance(project_config, dict):
                logger.error(f"Invalid BRBuild.yaml in {p}: missing or invalid 'project' section")
                continue

            target_folders = project_config.get("target_folders")
            if not isinstance(target_folders, list):
                target_folders = []

            projects.append(Project({
                "path": str(p),
                "name": project_config.get("name"),
                "build": bool(project_config.get("build")),
                "target_folders": target_folders,
            }))

        return projects
    
if __name__ == "__main__":
    finder = ProjectFinder()

    if not finder.projects:
        logger.error("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
        sys.exit(1)
    else:
        logger.info("Found projects:", finder.projects)