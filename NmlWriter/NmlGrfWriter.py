import logging
import pathlib

from Lang.StringRegistry import nml_str
from .BaseNmlWriter import BaseNmlWriter
from .NmlSwitchWriter import NmlSwitchWriter
from .NmlTargetType import NmlTargetType

logger = logging.getLogger(__name__)


class NmlGrfWriter(BaseNmlWriter):
    def __init__(self, config):
        super().__init__()
        self.config = config

    def __repr__(self):
        return f"<Grf {self.config.short_name} ({self.config.version})>"

    def write_grf_gnml(self, output_path):
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            self.writeline(f, "// GRF definition block", indent=0)
            self.writeline(f, "grf {", indent=0)

            self.writeline(f, f'grfid: "{self.config.grfid}"; // {self.config.name}', indent=1)
            self.writeline(f, f'name: {nml_str(self.config.name, "grf_name")};', indent=1)
            self.writeline(f, f'desc: {nml_str(self.config.description, "grf_desc")};', indent=1)
            self.writeline(f, f"version: {self.config.version};", indent=1)
            self.writeline(f, f"min_compatible_version: {self.config.compatible_version};", indent=1)

            for idx, param in enumerate(self.config.params):
                self.writeline(f, f"param {idx} {{", indent=1)
                self.writeline(f, f"{param['identifier']} {{", indent=2)

                p_type = param.get("type", "int")
                self.writeline(f, f"type: {p_type};", indent=3)
                self.writeline(f, f"name: {nml_str(param['name_str'], param['identifier'] + '_name')};", indent=3)
                self.writeline(f, f"desc: {nml_str(param['desc_str'], param['identifier'] + '_desc')};", indent=3)
                self.writeline(f, f"min_value: {param['min_value']};", indent=3)
                self.writeline(f, f"max_value: {param['max_value']};", indent=3)
                self.writeline(f, f"def_value: {param['def_value']};", indent=3)

                if param.get("names"):
                    self.writeline(f, "names: {", indent=3)
                    for key, name in param["names"].items():
                        self.writeline(
                            f, f"{key}: {nml_str(name, param['identifier'] + '_' + str(key))};", indent=4
                        )
                    self.writeline(f, "};", indent=3)

                self.writeline(f, "}", indent=2)
                self.writeline(f, "}", indent=1)

            self.writeline(f, "}\n\n", indent=0)

            self.write_vehicle_switches(f)
            self.write_global_actions(f)

            logger.info(f"GRF GNML written to {output_path}")
            return output_path

    def write_railtype_table(self, table, output_path):
        """Write the project's railtype table and the constants vehicles name.

        Emitted as its own collated file before the vehicle blocks, because the
        constants must exist by the time a `track_type` property is parsed.
        """
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            self.writeline(
                f, "// Logical track types and the railtype labels they fall back to", indent=0
            )
            table.write_nml(f)
            self.writeline(f, "", indent=0)

        logger.info(f"Railtype table written to {output_path}")
        return output_path

    def write_global_actions(self, f):
        """Write parameter-controlled top-level NML actions."""
        for action in self.config.global_actions:
            self.writeline(f, f"if ({action['condition']})", indent=0)
            self.writeline(f, "{", indent=0)
            statement = str(action["action"]).strip()
            if not statement.endswith(";"):
                statement += ";"
            self.writeline(f, statement, indent=1)
            self.writeline(f, "}", indent=0)
            self.writeline(f, "", indent=0)

    def write_vehicle_switches(self, f):
        nmlSwitchWriter = NmlSwitchWriter()

        for sw in self.config.global_vehicle_switches:
            raw_target = sw.get("target_type", NmlTargetType.SELF)
            target_enum = NmlTargetType.from_str(raw_target)

            nmlSwitchWriter.write_switch(
                f=f,
                vehicle_type=sw["vehicle_type"],
                target_type=target_enum,
                name=sw["name"],
                expression=sw["expression"],
                values=sw["values"],
            )