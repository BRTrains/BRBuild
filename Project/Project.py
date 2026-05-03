from pathlib import Path

class Project:
    def __init__(self, project_data):
        if isinstance(project_data, dict):
            self.name = project_data.get("name") or Path(project_data.get("path", "")).name
            self.path = Path(project_data.get("path", ".")).expanduser().resolve()
            self.build = bool(project_data.get("build"))
            self.target_folders = project_data.get("target_folders") if isinstance(project_data.get("target_folders"), list) else []
        else:
            self.name = str(project_data)
            self.path = Path(f"../{self.name}").expanduser().resolve()
            self.build = True
            self.target_folders = []

    def __repr__(self):
        return f"Project(name='{self.name}', path='{self.path}', build={self.build}, target_folders={self.target_folders})"