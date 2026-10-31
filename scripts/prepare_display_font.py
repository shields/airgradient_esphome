# Copyright © 2026 Michael Shields

"""Rebuild the font assets used by ESPHome's monochrome OLED displays.

Inter supplies scalable readings, ProFont supplies small bitmap labels, and IBM
EGA supplies larger bitmap text. The source hashes pin the exact input files;
the upstream license files are copied unchanged alongside the prepared fonts.
"""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

from fontTools.ttLib import TTFont

SOURCE_URL = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
SOURCE_SHA256 = "9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e"
PROFONT_URL = (
    "https://raw.githubusercontent.com/olikraus/u8g2/"
    "ae801fc34a2735fce67345dc7f3ee2aa37100479/tools/font/bdf/profont11.bdf"
)
PROFONT_SHA256 = "cbf055074adb337955b29c60cbbcb2588826f5f330cf1ba73956dc7b165a1bfa"
PROFONT_LICENSE_URL = (
    "https://tobiasjung.name/downloadfile.php?"
    "file=ProFont_Distribution_2.2_with_license.zip"
)
PROFONT_LICENSE_SHA256 = "1901b8364a0cddff2b93c18914d0d2f9d856f92117d330950baa2653e5fb660b"
IBM_URL = (
    "https://int10h.org/oldschool-pc-fonts/download/"
    "oldschool_pc_font_pack_v2.2_linux.zip"
)
IBM_SHA256 = "b30dc3ecc9931ad2dd8be7517dd01813c8834a1911b582ab7643191b41a3d759"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "fonts"


def download(url: str, checksum: str) -> bytes:
    """Fetch an upstream artifact and reject unexpected content."""
    # The IBM font host rejects urllib's default user agent.
    request = Request(
        url, headers={"User-Agent": "airgradient-esphome/prepare-display-fonts"}
    )
    with urlopen(request, timeout=60) as response:
        data = response.read()
    if sha256(data).hexdigest() != checksum:
        raise ValueError(f"Checksum mismatch: {url}")
    return data


def prepare_inter() -> None:
    """Bake Inter's ss01 alternate digits into its Unicode character maps."""
    data = download(SOURCE_URL, SOURCE_SHA256)
    with ZipFile(BytesIO(data)) as archive:
        with TTFont(
            BytesIO(archive.read("extras/ttf/Inter-SemiBold.ttf")),
            recalcTimestamp=False,
        ) as font:
            gsub = font["GSUB"].table
            feature = next(
                record.Feature
                for record in gsub.FeatureList.FeatureRecord
                if record.FeatureTag == "ss01"
            )
            # ESPHome loads glyphs by code point without applying OpenType substitutions.
            for index in feature.LookupListIndex:
                lookup = gsub.LookupList.Lookup[index]
                if lookup.LookupType != 1:
                    raise ValueError("ss01 requires a single-glyph substitution")
                for subtable in lookup.SubTable:
                    for table in font["cmap"].tables:
                        if table.isUnicode():
                            table.cmap = {
                                codepoint: subtable.mapping.get(glyph, glyph)
                                for codepoint, glyph in table.cmap.items()
                            }
            font.save(OUTPUT_DIR / "Inter-SemiBold-ss01.ttf")
        (OUTPUT_DIR / "LICENSE.txt").write_bytes(archive.read("LICENSE.txt"))


def prepare_profont() -> None:
    """Copy ProFont's native 11-pixel bitmap and its upstream license."""
    data = download(PROFONT_URL, PROFONT_SHA256)
    (OUTPUT_DIR / "ProFont-11.bdf").write_bytes(data)
    license_data = download(PROFONT_LICENSE_URL, PROFONT_LICENSE_SHA256)
    with ZipFile(BytesIO(license_data)) as archive:
        (OUTPUT_DIR / "LICENSE-ProFont.txt").write_bytes(
            archive.read("ProFont_Distribution_2.2_with_license/LICENSE")
        )


def prepare_ibm() -> None:
    """Prepare the IBM EGA bitmap with its micro sign lowered by one pixel."""
    data = download(IBM_URL, IBM_SHA256)
    with ZipFile(BytesIO(data)) as archive:
        with TTFont(
            BytesIO(archive.read("otb - Bm (linux bitmap)/BmPlus_IBM_EGA_8x14.otb")),
            recalcTimestamp=False,
        ) as font:
            glyph = font["EBDT"].strikeData[0][font.getBestCmap()[ord("µ")]]
            bitmap = glyph.imageData
            if glyph.getFormat() != 5 or len(bitmap) != 14 or bitmap[-1] != 0:
                raise ValueError("Unexpected IBM EGA micro sign bitmap")
            # Format 5 shares metrics across glyphs; shifting the bitmap moves only µ.
            glyph.imageData = b"\x00" + bitmap[:-1]
            # OTB is a TrueType container; this suffix lets ESPHome load its bitmap strike.
            font.save(OUTPUT_DIR / "IBM-EGA-8x14.ttf")
        (OUTPUT_DIR / "LICENSE-IBM.txt").write_bytes(archive.read("LICENSE.TXT"))


def main() -> None:
    """Rebuild all font assets from verified upstream sources."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    prepare_inter()
    prepare_profont()
    prepare_ibm()


if __name__ == "__main__":
    main()
