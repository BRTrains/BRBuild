class Builder:
    def __init__(self, name):
        self.name = name

    def build(self):
        print(f"{self.name} is building something.")