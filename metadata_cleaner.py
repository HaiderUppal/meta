#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              IMAGE METADATA CLEANER & SPOOFER                   ║
║                                                                  ║
║  Strips all AI-related metadata from images and replaces it      ║
║  with Adobe Illustrator-style EXIF/XMP data so the file          ║
║  appears to be an original vector-exported illustration.         ║
║                                                                  ║
║  Usage:                                                          ║
║    python metadata_cleaner.py input.png                          ║
║    python metadata_cleaner.py input.jpg -o cleaned.jpg           ║
║    python metadata_cleaner.py input.png --verify-only            ║
║    python metadata_cleaner.py input.png --ai-version 2024        ║
║                                                                  ║
║  Supports: PNG, JPEG, TIFF, WEBP                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

import argparse
import io
import os
import struct
import sys
import json
import hashlib
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

try:
    from PIL import Image, PngImagePlugin
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False
    print("WARNING: piexif not found. EXIF spoofing for JPEG will be limited.")
    print("         Install with: pip install piexif")


# ─────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp"}

# AI-related metadata keys/patterns to detect and strip
AI_SIGNATURES = [
    # Common AI tool markers
    "ai", "artificial", "machine learning", "neural", "deep learning",
    "stable diffusion", "midjourney", "dall-e", "dalle", "openai",
    "comfyui", "automatic1111", "a1111", "invoke", "novelai",
    "topaz", "gigapixel", "upscale", "super resolution",
    "generative", "gen_ai", "ai_generated", "c2pa",
    "content_credentials", "contentcredentials",
    "digitalsourcetype", "compositeWithTrainedAlgorithmicMedia",
    "trainedAlgorithmicMedia",
    # Adobe Content Authenticity
    "contentauthenticity", "cai", "c2pa",
    # XMP AI markers
    "photoshop:AIGenerative", "xmp:CreatorTool",
]

# XMP namespace patterns that often carry AI provenance
AI_XMP_NAMESPACES = [
    "c2pa", "steg", "cai", "contentauth",
    "Iptc4xmpExt:DigitalSourceType",
]

# Adobe Illustrator version configs
AI_VERSIONS = {
    "2024": {
        "creator": "Adobe Illustrator 28.3 (Macintosh)",
        "producer": "Adobe PDF library 17.00",
        "xmp_toolkit": "Adobe XMP Core 9.1-c002 79.a6a6396, 2024/03/13-12:12:12",
        "version": "28.3",
    },
    "2023": {
        "creator": "Adobe Illustrator 27.9 (Macintosh)",
        "producer": "Adobe PDF library 17.00",
        "xmp_toolkit": "Adobe XMP Core 6.0-c006 79.dab7c67, 2023/01/12-09:46:17",
        "version": "27.9",
    },
    "cc2022": {
        "creator": "Adobe Illustrator 26.5 (Macintosh)",
        "producer": "Adobe PDF library 16.07",
        "xmp_toolkit": "Adobe XMP Core 5.6-c017 91.162038, 2022/01/20-09:42:42",
        "version": "26.5",
    },
}

# Location profiles — GPS coords with slight random jitter applied at runtime
LOCATION_PROFILES = {
    "paris": {
        "label": "Paris, France",
        "lat": 48.8566,
        "lng": 2.3522,
        "alt": 35.0,
        "tz_offset": "+01:00",
        "tz_offset_summer": "+02:00",
        "jitter": 0.012,
    },
    "tokyo": {
        "label": "Tokyo, Japan",
        "lat": 35.6762,
        "lng": 139.6503,
        "alt": 40.0,
        "tz_offset": "+09:00",
        "tz_offset_summer": "+09:00",
        "jitter": 0.013,
    },
    "nyc": {
        "label": "New York, USA",
        "lat": 40.7128,
        "lng": -74.0060,
        "alt": 10.0,
        "tz_offset": "-05:00",
        "tz_offset_summer": "-04:00",
        "jitter": 0.012,
    },
    "london": {
        "label": "London, UK",
        "lat": 51.5074,
        "lng": -0.1278,
        "alt": 11.0,
        "tz_offset": "+00:00",
        "tz_offset_summer": "+01:00",
        "jitter": 0.010,
    },
    "berlin": {
        "label": "Berlin, Germany",
        "lat": 52.5200,
        "lng": 13.4050,
        "alt": 34.0,
        "tz_offset": "+01:00",
        "tz_offset_summer": "+02:00",
        "jitter": 0.010,
    },
    "rome": {
        "label": "Rome, Italy",
        "lat": 41.9028,
        "lng": 12.4964,
        "alt": 21.0,
        "tz_offset": "+01:00",
        "tz_offset_summer": "+02:00",
        "jitter": 0.011,
    },
    "lahore": {
        "label": "Lahore, Pakistan",
        "lat": 31.5204,
        "lng": 74.3587,
        "alt": 217.0,
        "tz_offset": "+05:00",
        "tz_offset_summer": "+05:00",
        "jitter": 0.012,
    },
    "dubai": {
        "label": "Dubai, UAE",
        "lat": 25.2048,
        "lng": 55.2708,
        "alt": 5.0,
        "tz_offset": "+04:00",
        "tz_offset_summer": "+04:00",
        "jitter": 0.013,
    },
    "mumbai": {
        "label": "Mumbai, India",
        "lat": 19.0760,
        "lng": 72.8777,
        "alt": 14.0,
        "tz_offset": "+05:30",
        "tz_offset_summer": "+05:30",
        "jitter": 0.012,
    },
    "singapore": {
        "label": "Singapore",
        "lat": 1.3521,
        "lng": 103.8198,
        "alt": 15.0,
        "tz_offset": "+08:00",
        "tz_offset_summer": "+08:00",
        "jitter": 0.010,
    },
    "sydney": {
        "label": "Sydney, Australia",
        "lat": -33.8688,
        "lng": 151.2093,
        "alt": 58.0,
        "tz_offset": "+11:00",
        "tz_offset_summer": "+10:00",
        "jitter": 0.012,
    },
    "moscow": {
        "label": "Moscow, Russia",
        "lat": 55.7558,
        "lng": 37.6173,
        "alt": 156.0,
        "tz_offset": "+03:00",
        "tz_offset_summer": "+03:00",
        "jitter": 0.011,
    },
}


# ─────────────────────────────────────────────────
#  VERIFICATION / ANALYSIS
# ─────────────────────────────────────────────────

class MetadataReport:
    """Analyzes an image and produces a detailed metadata report."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.findings = []
        self.ai_flags = []
        self.all_metadata = {}

    def analyze(self) -> dict:
        """Run full analysis on the image file."""
        path = Path(self.filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}")

        # Basic file info
        stat = path.stat()
        self.all_metadata["file"] = {
            "name": path.name,
            "size_bytes": stat.st_size,
            "size_human": self._human_size(stat.st_size),
            "format": ext,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

        img = Image.open(self.filepath)
        self.all_metadata["image"] = {
            "dimensions": f"{img.width}x{img.height}",
            "mode": img.mode,
            "format": img.format,
        }

        # Extract all metadata layers
        self._extract_exif(img)
        self._extract_xmp(img)
        self._extract_png_chunks(img, ext)
        self._extract_iptc(img)

        # Scan for AI signatures
        self._scan_for_ai()

        return {
            "metadata": self.all_metadata,
            "ai_flags": self.ai_flags,
            "is_suspicious": len(self.ai_flags) > 0,
        }

    def _extract_exif(self, img: Image.Image):
        """Extract EXIF data."""
        exif_data = {}
        raw_exif = img.getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, f"Unknown-{tag_id}")
                try:
                    exif_data[tag_name] = str(value)
                except Exception:
                    exif_data[tag_name] = repr(value)

            # IFD blocks
            for ifd_key in raw_exif.get_ifd(0x8769) if 0x8769 in raw_exif else {}:
                tag_name = TAGS.get(ifd_key, f"ExifIFD-{ifd_key}")
                try:
                    exif_data[tag_name] = str(raw_exif.get_ifd(0x8769)[ifd_key])
                except Exception:
                    pass

        if exif_data:
            self.all_metadata["exif"] = exif_data

    def _extract_xmp(self, img: Image.Image):
        """Extract XMP/XML metadata."""
        xmp_data = None

        # Try PIL's built-in XMP
        if hasattr(img, "getxmp"):
            try:
                xmp = img.getxmp()
                if xmp:
                    xmp_data = xmp
            except Exception:
                pass

        # Also try raw info
        for key in ["XML:com.adobe.xmp", "xmp"]:
            if key in img.info:
                raw = img.info[key]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                self.all_metadata["xmp_raw"] = raw[:2000]  # truncate for display
                break

        if xmp_data:
            self.all_metadata["xmp"] = self._flatten_dict(xmp_data)

    def _extract_png_chunks(self, img: Image.Image, ext: str):
        """Extract PNG text chunks."""
        if ext != ".png":
            return
        chunks = {}
        if hasattr(img, "text"):
            for k, v in img.text.items():
                chunks[k] = str(v)[:500]
        if chunks:
            self.all_metadata["png_text_chunks"] = chunks

    def _extract_iptc(self, img: Image.Image):
        """Extract IPTC data if available."""
        iptc = {}
        if hasattr(img, "tag_v2"):
            try:
                for tag_id in img.tag_v2:
                    tag_name = TAGS.get(tag_id, f"IPTC-{tag_id}")
                    iptc[tag_name] = str(img.tag_v2[tag_id])
            except Exception:
                pass
        if iptc:
            self.all_metadata["iptc"] = iptc

    def _scan_for_ai(self):
        """Scan all metadata for AI-related signatures."""
        import re
        flat = json.dumps(self.all_metadata, default=str).lower()

        # Whitelist patterns from our own spoofed Illustrator metadata
        whitelist = [
            "adobe illustrator",
            "adobe xmp core",
            "adobe pdf library",
            "xmp:creatortool",  # we inject this ourselves
            "illustrator:type",
            "illustrator:startupprofile",
        ]

        # Remove whitelisted content before scanning
        clean_flat = flat
        for wl in whitelist:
            clean_flat = clean_flat.replace(wl.lower(), "")

        for sig in AI_SIGNATURES:
            sig_lower = sig.lower()
            # Use word boundary for short signatures to avoid false positives
            if len(sig_lower) <= 3:
                if re.search(r'\b' + re.escape(sig_lower) + r'\b', clean_flat):
                    # Extra check: "ai" alone should only flag if not part of normal words
                    if sig_lower == "ai":
                        # Look for standalone "ai" that isn't part of a longer word
                        matches = re.findall(r'(?<![a-z])ai(?![a-z])', clean_flat)
                        if matches:
                            self.ai_flags.append(f"Found AI signature: '{sig}'")
                    else:
                        self.ai_flags.append(f"Found AI signature: '{sig}'")
            else:
                if sig_lower in clean_flat:
                    self.ai_flags.append(f"Found AI signature: '{sig}'")

        for ns in AI_XMP_NAMESPACES:
            if ns.lower() in clean_flat:
                self.ai_flags.append(f"Found AI-related XMP namespace: '{ns}'")

    def _flatten_dict(self, d, prefix=""):
        """Flatten nested dicts for easier scanning."""
        items = {}
        if isinstance(d, dict):
            for k, v in d.items():
                new_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    items.update(self._flatten_dict(v, new_key))
                elif isinstance(v, list):
                    items[new_key] = str(v)
                else:
                    items[new_key] = str(v)
        return items

    @staticmethod
    def _human_size(nbytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} TB"


# ─────────────────────────────────────────────────
#  CLEANING & SPOOFING
# ─────────────────────────────────────────────────

class MetadataCleaner:
    """Strips all metadata and injects Adobe Illustrator-style metadata."""

    def __init__(self, filepath: str, ai_version: str = "2024", location: str = None):
        self.filepath = filepath
        self.ext = Path(filepath).suffix.lower()
        self.config = AI_VERSIONS.get(ai_version, AI_VERSIONS["2024"])
        self.location = LOCATION_PROFILES.get(location) if location else None

        # Determine timezone offset from location
        if self.location:
            # Simple DST check: Apr–Oct = summer for northern hemisphere
            month = datetime.now().month
            is_summer = 4 <= month <= 10
            self.tz_offset = self.location["tz_offset_summer"] if is_summer else self.location["tz_offset"]
        else:
            self.tz_offset = "+05:00"  # default PKT

        # Generate a believable creation date (1-14 days ago, during work hours)
        days_ago = random.randint(1, 14)
        hour = random.randint(9, 18)
        minute = random.randint(0, 59)
        self.fake_date = (
            datetime.now() - timedelta(days=days_ago)
        ).replace(hour=hour, minute=minute, second=random.randint(0, 59))

    def clean_and_spoof(self, output_path: str) -> str:
        """Main pipeline: strip → rebuild → spoof → save."""
        img = Image.open(self.filepath)

        # Step 1: Create a completely clean pixel copy
        clean_img = self._strip_all(img)

        # Step 2: Inject Adobe Illustrator metadata
        if self.ext in {".jpg", ".jpeg"}:
            self._save_jpeg_with_spoof(clean_img, output_path)
        elif self.ext == ".png":
            self._save_png_with_spoof(clean_img, output_path)
        elif self.ext in {".tiff", ".tif"}:
            self._save_tiff_with_spoof(clean_img, output_path)
        elif self.ext == ".webp":
            self._save_webp_clean(clean_img, output_path)
        else:
            clean_img.save(output_path)

        return output_path

    def _strip_all(self, img: Image.Image) -> Image.Image:
        """
        Create a pixel-perfect copy with ZERO metadata.
        This is the nuclear option — copies only raw pixel data.
        """
        # Convert to RGB/RGBA to ensure clean pixel data
        if img.mode in ("RGBA", "LA", "PA"):
            src = img.convert("RGBA")
            clean = Image.new("RGBA", img.size)
            clean.paste(src)
        elif img.mode == "P":
            src = img.convert("RGB")
            clean = Image.new("RGB", img.size)
            clean.paste(src)
        else:
            src = img.convert("RGB")
            clean = Image.new("RGB", img.size)
            clean.paste(src)

        return clean

    def _build_illustrator_xmp(self) -> bytes:
        """Build a realistic Adobe Illustrator XMP packet."""
        doc_id = "".join(random.choices(string.hexdigits.lower(), k=32))
        instance_id = "".join(random.choices(string.hexdigits.lower(), k=32))
        original_id = "".join(random.choices(string.hexdigits.lower(), k=32))
        date_str = self.fake_date.strftime(f"%Y-%m-%dT%H:%M:%S{self.tz_offset}")

        xmp = f"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:illustrator="http://ns.adobe.com/illustrator/1.0/"
   xmp:CreatorTool="{self.config['creator']}"
   xmp:CreateDate="{date_str}"
   xmp:ModifyDate="{date_str}"
   xmp:MetadataDate="{date_str}"
   xmpMM:DocumentID="xmp.did:{doc_id}"
   xmpMM:InstanceID="xmp.iid:{instance_id}"
   xmpMM:OriginalDocumentID="xmp.did:{original_id}"
   xmpMM:RenditionClass="proof:pdf"
   pdf:Producer="{self.config['producer']}"
   illustrator:Type="Document"
   illustrator:StartupProfile="Print">
   <xmpMM:History>
    <rdf:Seq>
     <rdf:li
      stEvt:action="created"
      stEvt:instanceID="xmp.iid:{original_id}"
      stEvt:when="{date_str}"
      stEvt:softwareAgent="{self.config['creator']}"/>
     <rdf:li
      stEvt:action="saved"
      stEvt:instanceID="xmp.iid:{instance_id}"
      stEvt:when="{date_str}"
      stEvt:softwareAgent="{self.config['creator']}"
      stEvt:changed="/"/>
    </rdf:Seq>
   </xmpMM:History>
   <dc:format>image/png</dc:format>
   <dc:title>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">Untitled-1</rdf:li>
    </rdf:Alt>
   </dc:title>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
        return xmp.encode("utf-8")

    def _build_exif_dict(self) -> dict:
        """Build a piexif-compatible EXIF dict mimicking Illustrator export."""
        date_str = self.fake_date.strftime("%Y:%m:%d %H:%M:%S")

        exif_dict = {
            "0th": {
                piexif.ImageIFD.Software: self.config["creator"].encode(),
                piexif.ImageIFD.DateTime: date_str.encode(),
                piexif.ImageIFD.Make: b"",
                piexif.ImageIFD.Model: b"",
                piexif.ImageIFD.XResolution: (300, 1),
                piexif.ImageIFD.YResolution: (300, 1),
                piexif.ImageIFD.ResolutionUnit: 2,  # inches
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: date_str.encode(),
                piexif.ExifIFD.DateTimeDigitized: date_str.encode(),
                piexif.ExifIFD.ColorSpace: 1,  # sRGB
            },
            "1st": {},
            "GPS": {},
        }

        # Inject GPS if a location was specified
        if self.location:
            lat = self.location["lat"] + random.uniform(-self.location["jitter"], self.location["jitter"])
            lng = self.location["lng"] + random.uniform(-self.location["jitter"], self.location["jitter"])
            alt = self.location["alt"] + random.uniform(-2.0, 5.0)

            exif_dict["GPS"] = {
                piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
                piexif.GPSIFD.GPSLatitude: self._decimal_to_dms(abs(lat)),
                piexif.GPSIFD.GPSLongitudeRef: b"E" if lng >= 0 else b"W",
                piexif.GPSIFD.GPSLongitude: self._decimal_to_dms(abs(lng)),
                piexif.GPSIFD.GPSAltitudeRef: 0,  # above sea level
                piexif.GPSIFD.GPSAltitude: (int(abs(alt) * 100), 100),
                piexif.GPSIFD.GPSDateStamp: self.fake_date.strftime("%Y:%m:%d").encode(),
                piexif.GPSIFD.GPSTimeStamp: (
                    (self.fake_date.hour, 1),
                    (self.fake_date.minute, 1),
                    (self.fake_date.second, 1),
                ),
            }

        return exif_dict

    @staticmethod
    def _decimal_to_dms(decimal_deg: float) -> tuple:
        """Convert decimal degrees to EXIF DMS rational format ((d,1),(m,1),(s*100,100))."""
        d = int(decimal_deg)
        m_float = (decimal_deg - d) * 60
        m = int(m_float)
        s = (m_float - m) * 60
        # Use high precision for seconds
        s_num = int(round(s * 10000))
        return ((d, 1), (m, 1), (s_num, 10000))

    def _save_jpeg_with_spoof(self, img: Image.Image, output_path: str):
        """Save JPEG with spoofed EXIF + XMP."""
        if img.mode == "RGBA":
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95, subsampling=0)

        if HAS_PIEXIF:
            exif_dict = self._build_exif_dict()
            exif_bytes = piexif.dump(exif_dict)
            buf.seek(0)
            piexif.insert(exif_bytes, buf.getvalue(), output_path)
        else:
            buf.seek(0)
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())

        # Inject XMP into the JPEG
        self._inject_xmp_into_jpeg(output_path)

    def _inject_xmp_into_jpeg(self, filepath: str):
        """Inject XMP packet into JPEG file via APP1 marker."""
        xmp_data = self._build_illustrator_xmp()
        xmp_header = b"http://ns.adobe.com/xap/1.0/\x00"
        xmp_payload = xmp_header + xmp_data

        with open(filepath, "rb") as f:
            data = f.read()

        # Find position after SOI marker (FF D8)
        if data[:2] != b"\xff\xd8":
            return

        # Build APP1 marker for XMP
        length = len(xmp_payload) + 2
        app1 = b"\xff\xe1" + struct.pack(">H", length) + xmp_payload

        # Insert after SOI
        new_data = data[:2] + app1 + data[2:]

        with open(filepath, "wb") as f:
            f.write(new_data)

    def _save_png_with_spoof(self, img: Image.Image, output_path: str):
        """Save PNG with spoofed metadata in text chunks + XMP."""
        meta = PngImagePlugin.PngInfo()

        # Add standard Adobe-style text chunks
        meta.add_text("Software", self.config["creator"])
        meta.add_text("Creation Time", self.fake_date.strftime(f"%Y-%m-%dT%H:%M:%S{self.tz_offset}"))

        # Embed XMP as iTXt chunk
        xmp_data = self._build_illustrator_xmp()
        meta.add_text("XML:com.adobe.xmp", xmp_data.decode("utf-8"))

        img.save(output_path, format="PNG", pnginfo=meta, optimize=True)

    def _save_tiff_with_spoof(self, img: Image.Image, output_path: str):
        """Save TIFF with spoofed EXIF."""
        if img.mode == "RGBA":
            img = img.convert("RGB")

        if HAS_PIEXIF:
            exif_dict = self._build_exif_dict()
            exif_bytes = piexif.dump(exif_dict)
            img.save(output_path, format="TIFF", exif=exif_bytes)
        else:
            img.save(output_path, format="TIFF")

    def _save_webp_clean(self, img: Image.Image, output_path: str):
        """Save WEBP — clean only, limited metadata support."""
        if img.mode == "RGBA":
            img.save(output_path, format="WEBP", quality=95, lossless=False)
        else:
            img.convert("RGB").save(output_path, format="WEBP", quality=95)


# ─────────────────────────────────────────────────
#  CLI INTERFACE
# ─────────────────────────────────────────────────

def print_report(report: dict, filepath: str):
    """Pretty-print the metadata analysis report."""
    print("\n" + "=" * 64)
    print(f"  METADATA ANALYSIS REPORT")
    print(f"  File: {filepath}")
    print("=" * 64)

    meta = report["metadata"]

    # File info
    if "file" in meta:
        f = meta["file"]
        print(f"\n  FILE INFO")
        print(f"  ├─ Name:       {f['name']}")
        print(f"  ├─ Size:       {f['size_human']} ({f['size_bytes']} bytes)")
        print(f"  ├─ Format:     {f['format']}")
        print(f"  └─ Modified:   {f['modified']}")

    # Image info
    if "image" in meta:
        im = meta["image"]
        print(f"\n  IMAGE INFO")
        print(f"  ├─ Dimensions: {im['dimensions']}")
        print(f"  ├─ Mode:       {im['mode']}")
        print(f"  └─ Format:     {im['format']}")

    # EXIF
    if "exif" in meta:
        print(f"\n  EXIF DATA ({len(meta['exif'])} fields)")
        for i, (k, v) in enumerate(meta["exif"].items()):
            prefix = "└─" if i == len(meta["exif"]) - 1 else "├─"
            val = str(v)[:80]
            print(f"  {prefix} {k}: {val}")

    # XMP
    if "xmp" in meta:
        print(f"\n  XMP DATA ({len(meta['xmp'])} fields)")
        for i, (k, v) in enumerate(meta["xmp"].items()):
            prefix = "└─" if i == len(meta["xmp"]) - 1 else "├─"
            val = str(v)[:80]
            print(f"  {prefix} {k}: {val}")

    # PNG chunks
    if "png_text_chunks" in meta:
        print(f"\n  PNG TEXT CHUNKS ({len(meta['png_text_chunks'])} chunks)")
        for i, (k, v) in enumerate(meta["png_text_chunks"].items()):
            prefix = "└─" if i == len(meta["png_text_chunks"]) - 1 else "├─"
            val = str(v)[:80]
            print(f"  {prefix} {k}: {val}")

    # XMP raw (truncated)
    if "xmp_raw" in meta:
        print(f"\n  RAW XMP (first 300 chars)")
        print(f"  {meta['xmp_raw'][:300]}")

    # AI detection results
    print("\n" + "─" * 64)
    if report["ai_flags"]:
        print(f"  ⚠️  AI SIGNATURES DETECTED ({len(report['ai_flags'])} flags):")
        for flag in report["ai_flags"]:
            print(f"     • {flag}")
    else:
        print(f"  ✅  NO AI SIGNATURES DETECTED")
    print("─" * 64 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Strip AI metadata from images and spoof Adobe Illustrator origin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python metadata_cleaner.py photo.png                    # Clean + spoof → photo_cleaned.png
  python metadata_cleaner.py photo.jpg -o output.jpg      # Custom output path
  python metadata_cleaner.py photo.png --verify-only       # Only analyze, don't modify
  python metadata_cleaner.py photo.png --ai-version 2023   # Spoof as AI 2023
        """,
    )
    parser.add_argument("input", help="Input image file path")
    parser.add_argument("-o", "--output", help="Output file path (default: <name>_cleaned.<ext>)")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only analyze and report metadata, don't clean",
    )
    parser.add_argument(
        "--ai-version",
        choices=list(AI_VERSIONS.keys()),
        default="2024",
        help="Adobe Illustrator version to spoof (default: 2024)",
    )
    parser.add_argument(
        "--location",
        choices=list(LOCATION_PROFILES.keys()),
        default=None,
        help="Spoof GPS location (paris, tokyo, nyc, london, berlin, rome, lahore, dubai, mumbai, singapore, sydney, moscow)",
    )
    parser.add_argument(
        "--verify-after",
        action="store_true",
        default=True,
        help="Verify the output file after cleaning (default: True)",
    )
    parser.add_argument(
        "--no-verify-after",
        action="store_true",
        help="Skip post-clean verification",
    )

    args = parser.parse_args()

    input_path = args.input
    if not Path(input_path).exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    ext = Path(input_path).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        print(f"ERROR: Unsupported format '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS)}")
        sys.exit(1)

    # ── VERIFY (always runs first) ──
    print("\n🔍 ANALYZING INPUT FILE...")
    reporter = MetadataReport(input_path)
    input_report = reporter.analyze()
    print_report(input_report, input_path)

    if args.verify_only:
        sys.exit(0)

    # ── CLEAN + SPOOF ──
    if args.output:
        output_path = args.output
    else:
        stem = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{stem}_cleaned{ext}")

    print(f"🧹 CLEANING METADATA...")
    print(f"   Spoofing as: {AI_VERSIONS[args.ai_version]['creator']}")
    if args.location:
        print(f"   GPS location: {LOCATION_PROFILES[args.location]['label']}")

    cleaner = MetadataCleaner(input_path, ai_version=args.ai_version, location=args.location)
    result = cleaner.clean_and_spoof(output_path)

    print(f"✅ SAVED: {result}")

    # ── POST-CLEAN VERIFICATION ──
    if not args.no_verify_after:
        print("\n🔍 VERIFYING OUTPUT FILE...")
        out_reporter = MetadataReport(output_path)
        out_report = out_reporter.analyze()
        print_report(out_report, output_path)

        if out_report["ai_flags"]:
            print("⚠️  WARNING: AI signatures still detected in output!")
            print("   This may require manual inspection.")
        else:
            print("✅ OUTPUT IS CLEAN — no AI signatures detected.")
            print(f"   Metadata shows: {AI_VERSIONS[args.ai_version]['creator']}")
            if args.location:
                print(f"   GPS spoofed to: {LOCATION_PROFILES[args.location]['label']}")


if __name__ == "__main__":
    main()
