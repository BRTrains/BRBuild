from pathlib import Path
import sys

from PIL import Image

#: How far from pure white a pixel may be and still count as white. A sheet's gutters are
#: white or near-white, and so is the white its transparency is replaced with.
WHITE_TOLERANCE = 3
PURE_WHITE = (255, 255, 255)


class PalettedImage:
    """Utility class for working with paletted images using a fixed game palette."""

    PALETTE_SIZE = 256 * 3

    def __init__(self, image, palette):
        self.image = image
        self.palette = palette

    @classmethod
    def load(cls, filename, palette):
        """Load an image from a file, with any transparency removed."""
        return cls(cls.without_transparency(Image.open(filename)), palette)

    @classmethod
    def without_transparency(cls, image):
        """Return an image with every transparent pixel set to the sheet's lightest white.

        8bpp OpenTTD sprites have no alpha, so a transparent pixel would otherwise reach
        the palette as whatever colour it happens to be stored in (any colour at all),
        and be read as artwork by the row detector. A sheet's background is a white, so
        the replacement colour is taken from the artwork itself.
        """
        if not cls.has_transparency(image):
            return image

        rgba = image.convert("RGBA")
        replacement = Image.new("RGBA", rgba.size, cls.lightest_white(rgba) + (255,))
        transparent = rgba.getchannel("A").point(lambda alpha: 255 if alpha < 255 else 0)
        rgba.paste(replacement, (0, 0), transparent)

        return rgba.convert("RGB")

    @staticmethod
    def has_transparency(image):
        """Return True if an image carries an alpha channel or a palette transparency."""
        return "A" in image.getbands() or "transparency" in image.info

    @staticmethod
    def is_white(colour):
        """Return True for a white or near-white colour, as a sheet's gutters are drawn."""
        return max(abs(channel - 255) for channel in colour) <= WHITE_TOLERANCE

    @classmethod
    def lightest_white(cls, image):
        """The lightest white the image's opaque pixels are drawn in, or pure white.

        A sheet drawn without any white at all (a grey-filled legacy sheet, say) has no
        white to take, so pure white stands in.
        """
        whites = [colour for colour in cls._opaque_colours(image) if cls.is_white(colour)]

        if not whites:
            return PURE_WHITE

        return max(whites, key=lambda colour: (min(colour), sum(colour)))

    @classmethod
    def _opaque_colours(cls, image):
        """Return the distinct RGB colours of an image's non-transparent pixels."""
        rgba = image.convert("RGBA")
        # A pixel count is always enough entries for every distinct colour there can be.
        counts = rgba.getcolors(maxcolors=rgba.width * rgba.height) or []

        return {colour[:3] for _, colour in counts if colour[3] > 0}

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
        Any transparency was already removed at load (see `without_transparency`).
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