# GHOST PROTOCOL — AI Metadata Eraser

**GHOST PROTOCOL** is a dual-mode (Web & CLI) metadata erasure engine designed to strip AI-related signatures and spoof origin data in images. It ensures your digital assets appear as original, human-created works while providing an extra layer of privacy.

![Ghost Protocol](ghost-protocol.html) <!-- Note: This is a placeholder for a screenshot if you have one -->

## 🌟 Features

- **Strip EXIF/XMP:** Removes all metadata fields, including GPS, camera info, and editing history.
- **Spoof Origin Data:** Injects realistic Adobe Illustrator-style metadata.
- **GPS Spoofing:** Stamp your images with coordinates from global cities or custom locations.
- **AI Watermark Disruption:** Adds a subtle pixel noise layer to break invisible AI watermarks.
- **Dual Interface:** Use the sleek, modern Web UI for batch processing or the Python CLI for power users.

## 🛠️ Technical Stack

- **Web:** HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (Canvas API).
- **CLI:** Python 3, Pillow, piexif.

## 🚀 Getting Started

### Web Interface
Simply open `ghost-protocol.html` in any modern web browser. It works entirely locally—no data ever leaves your device.

### CLI Tool
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the cleaner:
   ```bash
   python metadata_cleaner.py input_image.jpg
   ```
3. See help for more options:
   ```bash
   python metadata_cleaner.py --help
   ```

## 🔒 Privacy First
Ghost Protocol operates entirely on your local machine. No images are uploaded to any server. Your privacy is built-in by design.

---

Built with ❤️ for the creative community.
