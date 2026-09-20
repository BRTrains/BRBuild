import logging
import sys
from pathlib import Path

import yaml

from Project.Project import Project

logger = logging.getLogger(__name__)


class ProjectFinder:
    '''Finds all projects in the parent directory that contain a "BRBuild.yaml" file, indicating they can be built by BRBuild.'''

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.parent_folder = self.project_root.parent

        logger.debug(f"ProjectFinder initialized. Looking for projects in: {self.parent_folder}")

        self.projects = self.find_projects()

    def _load_project_from_path(self, p: Path) -> Project | None:
        config_file = p / "BRBuild.yaml"

        if not p.is_dir() or not config_file.is_file():
            return None

        try:
            config = yaml.safe_load(config_file.read_text())
        except Exception as exc:
            logger.exception(f"Failed to load {config_file}: {exc}")
            return None

        if not isinstance(config, dict):
            logger.error(f"Invalid BRBuild.yaml in {p}: expected a YAML mapping")
            return None

        project_config = config.get("project")
        if not isinstance(project_config, dict):
            logger.error(f"Invalid BRBuild.yaml in {p}: missing or invalid 'project' section")
            return None

        target_folders = project_config.get("target_folders")
        if not isinstance(target_folders, list):
            target_folders = []

        # A project palette is relative to the BRBuild checkout so manifests stay portable;
        # without one, fall back to BRBuild's own palette rather than the caller's CWD.
        palette_path = Path(project_config.get("palette") or "Sprites/ttd-newgrf-dos.gpl").expanduser()
        if not palette_path.is_absolute():
            palette_path = self.project_root / palette_path
        palette = str(palette_path)

        return Project({
            "path": str(p),
            "name": project_config.get("name"),
            "build": bool(project_config.get("build")),
            "targetFolders": target_folders,
            "grfFolder": project_config.get("grf_folder"),
            "soundFolder": project_config.get("sound_folder"),
            "palette": palette,
        })

    def find_projects(self):
        logger.debug(f"Searching for projects in: {self.parent_folder}")
        projects = []

        for p in self.parent_folder.iterdir():
            project = self._load_project_from_path(p)
            if project is not None:
                projects.append(project)

        return projects

    def find_project(self, project_name: str) -> Project | None:
        '''
        Finds and loads a single project by folder name.
        Looks for ../<project_name>/BRBuild.yaml and applies the same validation as find_projects().
        '''
        p = self.parent_folder / project_name
        logger.debug(f"Searching for project: {p}")

        project = self._load_project_from_path(p)

        if project is None:
            logger.error(f"Project '{project_name}' not found or invalid at path: {p}")

        return project


if __name__ == "__main__":
    finder = ProjectFinder()

    if not finder.projects:
        logger.error("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
        sys.exit(1)
    else:
        logger.info("Found projects:", finder.projects)