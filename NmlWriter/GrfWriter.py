import pathlib
from pathlib import Path
from Lang.StringRegistry import nml_str
class GrfWriter:
    def __init__(self, config):
        self.config = config

    def __repr__(self):
        return f"<Grf {self.config.short_name} ({self.config.version})>"

    def write_grf_gnml(self, output_path):
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("// GRF definition block\n")
            f.write("grf {\n")

            f.write(f'\tgrfid: "{self.config.grfid}"; // {self.config.name}\n')
            f.write(f'\tname: {nml_str(self.config.name, "grf_name")};\n')
            f.write(f'\tdesc: {nml_str(self.config.description, "grf_desc")};\n')
            f.write(f'\tversion: {self.config.version};\n')
            f.write(f'\tmin_compatible_version: {self.config.compatible_version};\n')

            for idx, param in enumerate(self.config.params):
                f.write(f"\tparam {idx} {{\n")
                f.write(f"\t\t{param['identifier']} {{\n")

                p_type = param.get("type", "int")
                f.write(f"\t\t\ttype: {p_type};\n")
                f.write(f"\t\t\tname: {nml_str(param['name_str'], param['identifier'] + '_name')};\n")
                f.write(f"\t\t\tdesc: {nml_str(param['desc_str'], param['identifier'] + '_desc')};\n")
                f.write(f"\t\t\tmin_value: {param['min_value']};\n")
                f.write(f"\t\t\tmax_value: {param['max_value']};\n")
                f.write(f"\t\t\tdef_value: {param['def_value']};\n")

                if param.get("names"):
                    f.write("\t\t\tnames: {\n")
                    for key, name in param["names"].items():
                        f.write(
                            f"\t\t\t\t{key}: {nml_str(name, param['identifier'] + '_' + key)};\n"
                        )
                    f.write("\t\t\t};\n")

                f.write("\t\t}\n")
                f.write("\t}\n")

            f.write("}\n\n\n")

            self.write_vehicle_switches(f)

    def write_vehicle_switches(self, f):
        # TODO
        # Write vehicle switches - this is from BRMetro and used the switch writer from vehicle, but should probably be a new shared switch writer
        # vehicle_writer = NML_Vehicle(source_root=Path("."))
        raise(NotImplementedError("Vehicle switch writing not implemented yet"))

        for sw in self.config.global_vehicle_switches:
            vehicle_writer.write_switch(
                f=f,
                vehicle_type=sw["vehicle_type"],
                target_type=sw.get("target_type", "SELF"),
                name=sw["name"],
                expression=sw["expression"],
                values=sw["values"]
            )