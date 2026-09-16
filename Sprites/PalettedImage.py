from pathlib import Path
import sys

from PIL import Image


class PalettedImage:
    """Utility class for working with paletted images using a fixed game palette."""

    PALETTE_SIZE = 256 * 3

    def __init__(self, image, palette):
        self.image = image
        self.palette = palette

    @classmethod
    def load(cls, filename, palette):
        """Load an image from a file."""
        return cls(Image.open(filename), palette)

    def is_using_palette(self):
        """Return True if the image is paletted and uses the exact configured palette."""
        if self.image.mode != "P":
            return False

        image_palette = self.image.getpalette() or []
        image_palette = image_palette[:self.PALETTE_SIZE]
        image_palette += [0] * (self.PALETTE_SIZE - len(image_palette))

        return image_palette == self.palette

    def set_palette(self):
        """Force the image onto the configured palette.

        Remaps every pixel to its nearest colour in the configured palette first (so an
        artist's stray non-palette colours land on the closest intended colour, e.g. gutters
        stay white), then attaches the exact palette table. Dithering is disabled so flat
        colour regions (like gutters) stay solid instead of being speckled with noise.
        """
        palette_image = Image.new("P", (1, 1))
        palette_image.putpalette(self.palette)

        rgb_image = self.image.convert("RGB")
        self.image = rgb_image.quantize(palette=palette_image, dither=Image.Dither.NONE)

    @classmethod
    def load_palette(cls, filename):
        """Load a GIMP .gpl palette into a 256-entry RGB palette."""
        colours = []

        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if (
                    line.startswith("GIMP Palette")
                    or line.startswith("Name:")
                    or line.startswith("Columns:")
                ):
                    continue

                parts = line.split()

                if len(parts) < 3:
                    continue

                try:
                    r, g, b = map(int, parts[:3])
                except ValueError:
                    continue

                if not all(0 <= value <= 255 for value in (r, g, b)):
                    raise ValueError(
                        f"Invalid RGB value in GPL palette: {line}"
                    )

                colours.append((r, g, b))

        if len(colours) > 256:
            raise ValueError(
                f"GPL palette contains {len(colours)} colours; "
                "Pillow paletted images support a maximum of 256."
            )

        palette = [value for colour in colours for value in colour]
        palette += [0] * (cls.PALETTE_SIZE - len(palette))

        return palette

    def save(self, filename):
        """Save the image."""
        self.image.save(filename)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python -m {Path(__file__).stem} <image>")
        sys.exit(1)

    image_filename = sys.argv[1]

    # Change this to the location of the game's GPL palette.
    palette_filename = "Sprites/ttd-newgrf-dos.gpl"

    palette = PalettedImage.load_palette(palette_filename)
    image = PalettedImage.load(image_filename, palette)

    if image.is_using_palette():
        print("Image is using the game palette.")
    else:
        print("Image is not using the game palette.")

    image.set_palette()

    output_filename = (
        Path(image_filename).with_stem(
            f"{Path(image_filename).stem}_paletted"
        )
    )

    image.save(output_filename)

    print(f"Saved: {output_filename}")