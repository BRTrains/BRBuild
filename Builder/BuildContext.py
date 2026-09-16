from dataclasses import dataclass, field
from typing import Any

from Project.Project import Project


@dataclass
class BuildContext:
    project_data: Any = None
    project: Project | None = None
    nml_output_folder: str = ""
    candidates: list = field(default_factory=list)
    nml_files: list = field(default_factory=list)
    successful_variants: list = field(default_factory=list)
    failed_variants: list = field(default_factory=list)
    nml_filepath: str | None = None
    lang_folder: str | None = None
    newgrf_filepath: str | None = None
    log_nml_output: bool = False
    palette: list | None = None
    template_definitions: list | None = None