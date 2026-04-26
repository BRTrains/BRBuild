import argparse
from pathlib import Path
from Builder.Builder import Builder
from Builder.ProjectFinder import ProjectFinder

def run_build(project_name=None):
    if project_name:
        # Build specific project
        builder = Builder()
        builder.build(project_name)
    else:
        # Find and build all projects
        finder = ProjectFinder()
        
        if not finder.projects:
            print("No projects found. Please ensure there are folders with a 'BRBuild.yaml' file in the parent directory.")
            return False
        
        print("Found projects:", finder.projects)
        builder = Builder()
        
        for project in finder.projects:
            builder.build(project)
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build BRBuild projects")
    parser.add_argument("project", nargs="?", default=None, help="Project name to build (optional; will search for projects if omitted)")
    
    args = parser.parse_args()
    success = run_build(args.project)
    exit(0 if success else 1)