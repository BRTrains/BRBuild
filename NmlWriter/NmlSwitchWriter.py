class NmlSwitchWriter:
    def __init__(self):
        pass

    def write_switch(self, f, vehicle_type, target_type, name, expression, values: dict):
        self.writeline(f"switch ({vehicle_type}, {target_type}, {name}, {expression})", f)
        self.writeline("{", f)
        if isinstance(values, dict):
            for key, val in values.items():
                if key == "default":
                    self.writeline(f"{val}{'' if str(val).strip().endswith(';') else ';'}", f, 1)
                else:
                    self.writeline(f"{key:} : {val}{'' if str(val).strip().endswith(';') else ';'}", f, 1)
        elif isinstance(values, list):
            for i, val in enumerate(values):
                self.writeline(f"{i}: {val}{'' if str(val).strip().endswith(';') else ';'}", f, 1)
        self.writeline("}", f)
        self.writeline("\n", f)