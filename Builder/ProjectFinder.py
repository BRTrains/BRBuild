import sys
from pathlib import Path

class ProjectFinder:
    '''Finds all projects in the parent directory that contain a "BRBuild.yaml" file, indicating they can be built by BRBuild.'''
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.parent_folder = self.project_root.parent

        self.projects = self.find_projects()

    def find_projects(self):
        # Find all folders in the directory above the project root that contain a "BRBuild.yaml" file
        print(f"Searching for projects in: {self.parent_folder}")
        target_folders = [
            p.name
            for p in self.parent_folder.iterdir()
            if p.is_dir() and (p / "BRBuild.yaml").is_file()
        ]
        return target_folders
    
if __name__ == "__main__":
    finder = ProjectFinder()

    if not finder.projects:
        print("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
        sys.exit(1)
    else:
        print("Found projects:", finder.projects)