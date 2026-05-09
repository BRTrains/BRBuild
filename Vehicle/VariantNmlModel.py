class VariantNmlModel:

    def __init__(self, variant, spritesets, switches, properties, callbacks):
        self.identifier = variant.identifier

        self.spritesets = spritesets
        self.switches = switches
        self.properties = properties
        self.callbacks = callbacks