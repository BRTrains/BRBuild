import logging
from pathlib import Path
logger = logging.getLogger(__name__)

class Project:
    def __init__(self, project_data):
        if isinstance(project_data, dict):
            self.name = project_data.get("name") or Path(project_data.get("path", "")).name
            self.path = Path(project_data.get("path", ".")).expanduser().resolve()
            self.build = bool(project_data.get("build"))
            self.grfFolder = project_data.get("grfFolder", "src/grf")
            self.soundFolder = project_data.get("soundFolder", "src/sound")
            self.targetFolders = project_data.get("targetFolders") if isinstance(project_data.get("targetFolders"), list) else []
            logger.debug(f"Initialized Project: {self} from data: {project_data}")
        else:
            logger.warning(f"Project initialized with non-dict data: {project_data}. Using default values.")    
            self.name = str(project_data)
            self.path = Path(f"../{self.name}").expanduser().resolve()
            self.build = True
            self.grfFolder = "src/grf"
            self.soundFolder = "src/sound"
            self.targetFolders = []

    def __repr__(self):
        return f"Project(name='{self.name}', path='{self.path}', build={self.build}, targetFolders={self.targetFolders})"