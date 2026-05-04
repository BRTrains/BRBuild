# BR Build

A newGRF builder for the BRTrains group of OpenTTD newGRFs

## Building

### Build from this project folder

Run `python Run.py` to automatically scan `../` for folders containing a `BRBuild.yaml` file, and attempt to build them

To build a specific project `projectname` pass it as the first parameter using `python Run.py [projectname]`

Optionally append `--log` to write the output to build.log

Full usage: `python Run.py [projectname] [--log]`

### Build from target project folder

Copy the [build.py.example](docs/build.py.example) file to the project folder and rename it `build.py`, run it as `python build.py [--log]`, no project name is required, `--log` is optional to generate a `build.log` file

## Creating a project

Copy the [BRBuild.yaml.example](docs/BRBuild.yaml.example) file to the project folder and edit names, paths, configuration as appropriate

Read [the project docs](docs/project.md) for information on how to structure the project and required files, formats etc