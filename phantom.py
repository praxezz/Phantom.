"""
PHANTOM - Steganography Toolkit
================================
Hide and extract encrypted messages/files inside images (LSB steganography).

Author: Praveen K
See also: PASSEC — a password strength checker, also by Praveen K.
"""

from PIL import Image
import numpy as np
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import hashlib
import zlib
import os
import sys
import glob
import json
import struct
import shutil

from rich.console import Console
from rich.theme import Theme as RichTheme
from rich.text import Text
from rich.align import Align
from rich.rule import Rule

try:
    from colorama import init as _colorama_init, Style
    _colorama_init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False
    class _Dummy:
        RESET_ALL = ""
    Style = _Dummy()

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif")


# ============================================================================
# COLOR ENGINE (two-tone gradients, truecolor ANSI)
# ============================================================================

class Theme:
    """Two accent colors used across the whole UI (double-colour banner)."""
    A = (56, 189, 248)    # electric blue
    B = (192, 38, 211)    # magenta/violet
    OK = (74, 222, 128)   # green
    WARN = (250, 204, 21)  # amber
    ERR = (248, 113, 113)  # red
    DIM = (120, 120, 130)
    WHITE = (240, 240, 245)


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    return True


COLOR_ON = _supports_color()


def rgb(r, g, b, text):
    if not COLOR_ON:
        return text
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def bold(text):
    if not COLOR_ON:
        return text
    return f"\x1b[1m{text}\x1b[0m"


def c_ok(text):
    return rgb(*Theme.OK, text)


def c_warn(text):
    return rgb(*Theme.WARN, text)


def c_err(text):
    return rgb(*Theme.ERR, text)


def c_dim(text):
    return rgb(*Theme.DIM, text)


def c_a(text):
    return rgb(*Theme.A, text)


def c_b(text):
    return rgb(*Theme.B, text)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def gradient_line(text, c1, c2):
    """Colors each character of a single line along a gradient c1 -> c2."""
    n = max(len(text) - 1, 1)
    out = []
    for i, ch in enumerate(text):
        r, g, b = lerp(c1, c2, i / n)
        out.append(rgb(r, g, b, ch) if ch != " " else ch)
    return "".join(out)


def gradient_block(lines, c1, c2):
    """Colors a block of ASCII-art lines top -> bottom along a gradient."""
    n = max(len(lines) - 1, 1)
    out = []
    for i, line in enumerate(lines):
        r, g, b = lerp(c1, c2, i / n)
        out.append(rgb(r, g, b, line) if line.strip() else line)
    return out


# ============================================================================
# BANNER — Rich, cyberpunk orange-on-black (matches PASSEC's banner styling)
# ============================================================================

PHANTOM_THEME = RichTheme({
    # Banner-only palette — left untouched.
    "accent":   "bold dark_orange",
    "accent2":  "orange3",
    "banner2":  "bold cyan",
    "border":   "dark_orange",

    # UI palette (menus, section headers, everything besides the banner) —
    # deliberately a different pair of colors: sea green + terracotta.
    "ui1":       "bold sea_green3",
    "ui2":       "bold indian_red",
    "ui_border": "sea_green3",
    "ui_title":  "bold sea_green3 on grey11",

    "good":     "bold spring_green3",
    "warn":     "bold yellow3",
    "bad":      "bold red3",
    "critical": "bold white on red3",
    "dim":      "grey58",
    "title":    "bold dark_orange on grey11",
})

rich_console = Console(theme=PHANTOM_THEME)

LOGO = [
    r" ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗",
    r" ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║",
    r" ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║",
    r" ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║",
    r" ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║",
    r" ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝",
]

WIDTH = 74


def print_banner():
    """Cyberpunk banner — now recolored to match the rest of the UI:
    sea green/terracotta, alternating per line, with a matching border rule."""
    styles = ["ui1", "ui2"]
    rich_console.print()
    for i, line in enumerate(LOGO):
        rich_console.print(Align.left(Text(line, style=styles[i % 2])))
    rich_console.print(Align.left(Text("", style="dim")))

    rich_console.print(Rule(style="ui_border"))

def section(title):
    rich_console.print()
    rich_console.rule(f"[ui1]{title}[/]", style="ui_border", characters="─")


# ============================================================================
# PROGRESS BAR
# ============================================================================

def progress_bar(done, total, label="", width=36):
    total = max(total, 1)
    pct = min(done / total, 1.0)
    filled = int(width * pct)
    r, g, b = lerp(Theme.A, Theme.B, pct)
    bar = rgb(r, g, b, "█" * filled) + c_dim("░" * (width - filled))
    sys.stdout.write(f"\r  {label} [{bar}] {pct*100:5.1f}%")
    sys.stdout.flush()
    if done >= total:
        sys.stdout.write("\n")


def capacity_bar(used, total, width=40):
    total = max(total, 1)
    pct = min(used / total, 1.0)
    filled = int(width * pct)
    if pct < 0.6:
        col = Theme.OK
    elif pct < 0.85:
        col = Theme.WARN
    else:
        col = Theme.ERR
    bar = rgb(*col, "█" * filled) + c_dim("░" * (width - filled))
    used_kb = used / 1024
    total_kb = total / 1024
    return f"[{bar}] {pct*100:5.1f}%  ({used_kb:,.1f} KB / {total_kb:,.1f} KB)"


# ============================================================================
# ASCII IMAGE PREVIEW
# ============================================================================

RAMP = " .:-=+*#%@"


def ascii_preview(image_path, out_width=64, print_output=True):
    """Renders an ASCII/ANSI preview of an image.

    Returns a tuple of:
      colored_lines - list of terminal-ready lines (truecolor ANSI codes)
      plain_lines   - list of the same lines with no color codes (for .txt)
      cell_data     - list of rows of (char, r, g, b) tuples (for .html export)
    """
    img = Image.open(image_path).convert("L")
    w, h = img.size
    aspect = h / w
    out_height = max(1, int(out_width * aspect * 0.5))  # chars are taller than wide
    img_small = img.resize((out_width, out_height))
    color_img = Image.open(image_path).convert("RGB").resize((out_width, out_height))
    gray = np.array(img_small, dtype=np.uint8)
    color = np.array(color_img, dtype=np.uint8)

    colored_lines = []
    plain_lines = []
    cell_data = []
    for y in range(out_height):
        colored_row = []
        plain_row = []
        cell_row = []
        for x in range(out_width):
            intensity = gray[y, x] / 255.0
            ch = RAMP[min(int(intensity * (len(RAMP) - 1)), len(RAMP) - 1)]
            r, g, b = color[y, x]
            colored_row.append(rgb(int(r), int(g), int(b), ch))
            plain_row.append(ch)
            cell_row.append((ch, int(r), int(g), int(b)))
        colored_lines.append("".join(colored_row))
        plain_lines.append("".join(plain_row))
        cell_data.append(cell_row)

    if print_output:
        print("\n".join(colored_lines))

    return colored_lines, plain_lines, cell_data


def export_ascii_preview(out_path, colored_lines, plain_lines, cell_data):
    """Saves an ASCII preview to disk. Format is chosen by file extension:
      .txt / (anything else) -> plain characters, no color
      .ans                   -> truecolor ANSI (view with `cat file.ans` in
                                 a terminal that supports 24-bit color)
      .html                  -> colored HTML page, viewable in any browser
    """
    ext = os.path.splitext(out_path)[1].lower()

    if ext == ".ans":
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(colored_lines) + "\n")
    elif ext == ".html":
        rows_html = []
        for row in cell_data:
            spans = []
            for ch, r, g, b in row:
                ch_html = " " if ch == " " else ch
                spans.append(f'<span style="color:rgb({r},{g},{b})">{ch_html}</span>')
            rows_html.append("".join(spans))
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>PHANTOM ASCII Preview</title></head>"
            "<body style=\"background:#111;margin:0;padding:16px;\">"
            "<pre style=\"font-family:monospace;line-height:1;font-size:8px;"
            "white-space:pre;\">" + "\n".join(rows_html) + "</pre>"
            "</body></html>"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        if not ext:
            out_path += ".txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(plain_lines) + "\n")

    return out_path


# ============================================================================
# CORE STEGANOGRAPHY ENGINE
# ============================================================================

class SteganographyError(Exception):
    pass


class WrongPasswordError(SteganographyError):
    pass


class NoHiddenDataError(SteganographyError):
    pass


class CapacityError(SteganographyError):
    pass


class SimpleSteganography:
    def __init__(self):
        self.MAGIC_HEADER = b"STEG"
        self.VERSION = b"\x01\x00"
        self.SALT_SIZE = 16
        self.IV_SIZE = 16
        self.KEY_SIZE = 32

    # ---- crypto -----------------------------------------------------
    def generate_key(self, password, salt):
        if isinstance(password, str):
            password = password.encode("utf-8")
        return PBKDF2(password, salt, dkLen=self.KEY_SIZE, count=100000)

    def encrypt_data(self, data, password):
        salt = get_random_bytes(self.SALT_SIZE)
        iv = get_random_bytes(self.IV_SIZE)
        key = self.generate_key(password, salt)
        pad_length = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_length] * pad_length)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded_data)
        return salt + iv + encrypted

    def decrypt_data(self, encrypted_data, password):
        salt = encrypted_data[:self.SALT_SIZE]
        iv = encrypted_data[self.SALT_SIZE:self.SALT_SIZE + self.IV_SIZE]
        ciphertext = encrypted_data[self.SALT_SIZE + self.IV_SIZE:]
        key = self.generate_key(password, salt)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        try:
            decrypted = cipher.decrypt(ciphertext)
            pad_length = decrypted[-1]
            if pad_length < 1 or pad_length > 16 or len(decrypted) < pad_length:
                raise ValueError("bad padding")
            return decrypted[:-pad_length]
        except Exception:
            raise WrongPasswordError(
                "Could not decrypt — wrong password, or the image doesn't "
                "contain valid PHANTOM data."
            )

    # ---- bit helpers (numpy-vectorized) ------------------------------
    @staticmethod
    def _bits_from_bytes(data: bytes) -> np.ndarray:
        return np.unpackbits(np.frombuffer(data, dtype=np.uint8))

    @staticmethod
    def _bytes_from_bits(bits: np.ndarray) -> bytes:
        return np.packbits(bits).tobytes()

    def calculate_capacity(self, image_path):
        img = Image.open(image_path).convert("RGB")
        width, height = img.size
        total_bits = width * height * 3
        usable_bytes = int(total_bits * 0.7) // 8
        return usable_bytes

    # ---- hide ---------------------------------------------------------
    def hide_message(self, image_path, output_path, message, password, progress=True):
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img, dtype=np.uint8)
        height, width, channels = img_array.shape

        if isinstance(message, str):
            message = message.encode("utf-8")

        compressed = False
        if len(message) > 100:
            compressed_data = zlib.compress(message, level=9)
            if len(compressed_data) < len(message):
                message = compressed_data
                compressed = True

        encrypted = self.encrypt_data(message, password)

        metadata = {"compressed": compressed, "size": len(encrypted), "type": "text"}
        meta_bytes = json.dumps(metadata).encode("utf-8")
        meta_len = struct.pack(">I", len(meta_bytes))

        payload = self.MAGIC_HEADER + self.VERSION + meta_len + meta_bytes + encrypted
        bits = self._bits_from_bytes(payload)

        total_pixels = height * width * channels
        max_capacity = int(total_pixels * 0.7)

        if len(bits) > max_capacity:
            raise CapacityError(
                f"Image too small for this payload.\n"
                f"    Needed:  {len(bits):,} bits ({len(bits)//8:,} bytes)\n"
                f"    Capacity: {max_capacity:,} bits ({max_capacity//8:,} bytes)\n"
                f"    Try a larger image or a shorter message/file."
            )

        flat_img = img_array.flatten()
        n = len(bits)
        chunk = max(1, n // 24)
        for start in range(0, n, chunk):
            end = min(start + chunk, n)
            flat_img[start:end] = (flat_img[start:end] & 0xFE) | bits[start:end]
            if progress:
                progress_bar(end, n, label="Embedding")

        encoded_img = flat_img.reshape((height, width, channels))
        result = Image.fromarray(encoded_img.astype("uint8"), "RGB")

        if not output_path.lower().endswith(".png"):
            output_path = os.path.splitext(output_path)[0] + ".png"

        result.save(output_path, format="PNG")
        return output_path, len(bits) // 8, max_capacity // 8

    # ---- extract --------------------------------------------------------
    def extract_message(self, image_path, password, progress=True):
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img, dtype=np.uint8)
        flat_img = img_array.flatten()
        total_available = len(flat_img)

        def read_bits(start, count):
            end = start + count
            if end > total_available:
                raise NoHiddenDataError(
                    "No hidden message found — image is too small to contain "
                    "PHANTOM data, or it wasn't encoded by this tool."
                )
            return flat_img[start:end] & 1

        header_bits = read_bits(0, 48)
        header = self._bytes_from_bits(header_bits)

        if header[:4] != self.MAGIC_HEADER:
            raise NoHiddenDataError(
                "No hidden message found in this image (magic header missing). "
                "Make sure you selected the correct encoded PNG."
            )

        meta_len_bits = read_bits(48, 32)
        meta_len = struct.unpack(">I", self._bytes_from_bits(meta_len_bits))[0]

        start = 80
        meta_bits = read_bits(start, meta_len * 8)
        meta_bytes = self._bytes_from_bits(meta_bits)
        try:
            metadata = json.loads(meta_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise NoHiddenDataError("Metadata is corrupted or this isn't a PHANTOM image.")

        data_size = metadata["size"]
        start = start + meta_len * 8
        n = data_size * 8
        end = start + n

        bits = np.zeros(n, dtype=np.uint8)
        chunk = max(1, n // 24)
        for s in range(0, n, chunk):
            e = min(s + chunk, n)
            bits[s:e] = read_bits(start + s, e - s)
            if progress:
                progress_bar(e, n, label="Extracting")

        encrypted = self._bytes_from_bits(bits)
        decrypted = self.decrypt_data(encrypted, password)

        if metadata.get("compressed"):
            try:
                decrypted = zlib.decompress(decrypted)
            except zlib.error:
                raise SteganographyError("Decompression failed — data may be corrupted.")

        return decrypted

    # ---- file wrappers ----------------------------------------------------
    def hide_file(self, image_path, output_path, file_path, password, progress=True):
        with open(file_path, "rb") as f:
            file_data = f.read()
        filename = os.path.basename(file_path)
        header = {"filename": filename, "size": len(file_data), "type": "file"}
        header_json = json.dumps(header).encode("utf-8")
        header_len = struct.pack(">I", len(header_json))
        complete_data = header_len + header_json + file_data
        return self.hide_message(image_path, output_path, complete_data, password, progress=progress)

    def extract_file(self, image_path, password, output_dir=".", progress=True):
        raw_data = self.extract_message(image_path, password, progress=progress)

        header_len = struct.unpack(">I", raw_data[:4])[0]
        header_json = raw_data[4:4 + header_len]
        file_header = json.loads(header_json.decode("utf-8"))

        if file_header.get("type") != "file":
            return {"type": "text", "content": raw_data.decode("utf-8")}

        file_data = raw_data[4 + header_len:]
        filename = file_header["filename"]
        output_path = os.path.join(output_dir, filename)

        counter = 1
        base, ext = os.path.splitext(output_path)
        while os.path.exists(output_path):
            output_path = f"{base}_{counter}{ext}"
            counter += 1

        with open(output_path, "wb") as f:
            f.write(file_data)

        return {"type": "file", "path": output_path, "size": len(file_data)}


# ============================================================================
# INPUT HELPERS
# ============================================================================

def ask(prompt):
    return input(rgb(*Theme.A, "› ") + prompt).strip().strip('"\'')


def resolve_images(raw):
    """Accepts a folder path, or a comma-separated list of file paths, and
    returns a flat list of existing image file paths."""
    raw = raw.strip()
    paths = []
    if os.path.isdir(raw):
        for ext in IMAGE_EXTS:
            paths.extend(glob.glob(os.path.join(raw, f"*{ext}")))
            paths.extend(glob.glob(os.path.join(raw, f"*{ext.upper()}")))
    else:
        for part in raw.split(","):
            part = part.strip().strip('"\'')
            if part:
                paths.append(part)
    return sorted(set(paths))


def confirm(prompt):
    return ask(prompt + " (y/n): ").lower() == "y"


# ============================================================================
# GUIDE
# ============================================================================

def print_guide():
    section("QUICK START GUIDE")
    guide = f"""
{bold("WHAT PHANTOM DOES")}
  PHANTOM hides a text message or an entire file inside an ordinary-looking
  image using LSB (least-significant-bit) steganography. Your data is
  compressed, then encrypted with AES before a single bit of it ever
  touches the image — so even if someone suspects the picture, they can't
  read the contents without your password.

{bold("MENU OPTIONS")}

  1  Hide Text Message      — pick an image, type a message, set a password
  2  Extract Text Message   — pick the encoded PNG, enter the same password
  3  Hide File               — hide any file type (PDF, ZIP, DOCX, etc.)
  4  Extract File             — recovers the file with its original name
  5  Check Capacity          — see how much data an image can hold
  6  Preview Image             — ASCII-art render, with option to export it
  7  Batch Hide                — hide the same message/file into many images
  8  Batch Extract              — extract from many images in one pass

{bold("STEP-BY-STEP: YOUR FIRST HIDDEN MESSAGE")}
  1. Pick a cover image. A busier, more detailed photo hides the change
     better than a flat-color graphic. PNG, JPG, BMP, WEBP and TIFF are
     all accepted as input — the output is always saved as PNG, since
     lossy formats would destroy the hidden bits.
  2. Run option 1: choose the image, type your message, set a password.
     Give the output a new filename — never overwrite the original.
  3. Immediately run option 2 on the new file with the same password to
     confirm it comes back correctly, before you send or store it anywhere.
  4. Share the encoded PNG however you like. Anyone without the password
     just sees a normal-looking picture.

{bold("HIDING FILES INSTEAD OF TEXT")}
  Options 3/4 work the same way but for whole files (documents, zips,
  other images, etc). Run option 5 first to check the cover image's
  capacity against your file's size — if the file is too large for the
  image, PHANTOM will tell you before you waste time encoding.

{bold("BATCH MODE")}
  Options 7/8 let you point at a folder (or a comma-separated list of
  paths) to hide or extract across many images in one pass — handy if
  you're distributing the same message/file across a set of cover images.

{bold("CHOOSING A GOOD PASSWORD")}
  The encryption is only as strong as the password protecting it. Avoid
  dictionary words, names, or anything reused elsewhere — a short or
  predictable password is the weakest link in this whole system, no
  matter how strong the underlying AES/PBKDF2 is. If you'd like a hand
  picking or checking one before you use it here, try {bold("PASSEC")}, my
  password strength checker — it's a quick way to make sure whatever
  you type into PHANTOM can actually hold up.

{bold("TIPS")}
  {c_ok("✓")} Use strong, unique passwords (8+ characters, mixed types)
  {c_ok("✓")} Keep output as PNG (lossless) — never re-save as JPG
  {c_ok("✓")} Test extraction right after hiding, before sharing the image
  {c_ok("✓")} Use option 5 before hiding a large file, so you know it'll fit
  {c_err("✗")} Don't reuse the input filename as the output filename
  {c_err("✗")} Don't edit, crop, filter or recompress the encoded image
  {c_err("✗")} Don't upload the encoded image to platforms that recompress
     images automatically (many social media and messaging apps do this)

{bold("SECURITY")}
  AES-256-CBC encryption, PBKDF2 (100,000 iterations), random salt + IV
  per file, automatic zlib compression, LSB steganography.

{bold("CAPACITY (approximate)")}
  800x600      → ~50 KB        1920x1080  → ~300 KB        3840x2160 → ~1.2 MB
  Use option 5 for an exact figure for your image.
"""
    print(guide)
    input(c_dim("\nPress Enter to return to the menu..."))


# ============================================================================
# MENU ACTIONS
# ============================================================================

def action_hide_text(stego):
    section("HIDE TEXT MESSAGE")
    img_path = ask("Input image: ")
    if not os.path.exists(img_path):
        print(c_err(f"✗ Not found: {img_path}"))
        return
    out_path = ask("Output image: ")
    message = ask("Secret message: ")
    password = ask("Password: ")
    if len(password) < 6:
        print(c_warn(" Password should be 6+ characters"))
        if not confirm("Continue anyway?"):
            return
    try:
        out, used, cap = stego.hide_message(img_path, out_path, message, password)
        print(c_ok(f"\n✓ Saved to: {out}"))
        print("  " + capacity_bar(used, cap))
    except SteganographyError as e:
        print(c_err(f"\n✗ {e}"))
    except Exception as e:
        print(c_err(f"\n✗ Unexpected error: {e}"))


def action_extract_text(stego):
    section("EXTRACT TEXT MESSAGE")
    img_path = ask("Encoded image: ")
    if not os.path.exists(img_path):
        print(c_err(f"✗ Not found: {img_path}"))
        return
    password = ask("Password: ")
    try:
        result = stego.extract_message(img_path, password)
        print()
        section("EXTRACTED MESSAGE")
        print(result.decode("utf-8"))
    except WrongPasswordError as e:
        print(c_err(f"\n✗ {e}"))
    except NoHiddenDataError as e:
        print(c_err(f"\n✗ {e}"))
    except SteganographyError as e:
        print(c_err(f"\n✗ {e}"))
    except Exception as e:
        print(c_err(f"\n✗ Unexpected error: {e}"))


def action_hide_file(stego):
    section("HIDE FILE")
    img_path = ask("Cover image: ")
    file_path = ask("File to hide: ")
    out_path = ask("Output image: ")
    password = ask("Password: ")
    if not os.path.exists(img_path):
        print(c_err(f"✗ Image not found: {img_path}"))
        return
    if not os.path.exists(file_path):
        print(c_err(f"✗ File not found: {file_path}"))
        return

    file_size = os.path.getsize(file_path)
    capacity = stego.calculate_capacity(img_path)
    print(f"\n  File: {file_size:,} bytes   Capacity: {capacity:,} bytes")
    print("  " + capacity_bar(file_size, capacity))
    if file_size > capacity * 0.7:
        print(c_warn("\n File is large relative to this image's capacity."))
        if not confirm("Continue anyway?"):
            return
    try:
        out, used, cap = stego.hide_file(img_path, out_path, file_path, password)
        print(c_ok(f"\n✓ Saved to: {out}"))
        print("  " + capacity_bar(used, cap))
    except SteganographyError as e:
        print(c_err(f"\n✗ {e}"))
    except Exception as e:
        print(c_err(f"\n✗ Unexpected error: {e}"))


def action_extract_file(stego):
    section("EXTRACT FILE")
    img_path = ask("Encoded image: ")
    password = ask("Password: ")
    out_dir = ask("Output folder (. for current): ") or "."
    if not os.path.exists(img_path):
        print(c_err(f"✗ Not found: {img_path}"))
        return
    try:
        result = stego.extract_file(img_path, password, out_dir)
        if result["type"] == "text":
            print(c_warn("\n This payload is a text message, not a file:\n"))
            print(result["content"])
        else:
            print(c_ok(f"\n✓ File saved: {result['path']}"))
            print(f"  Size: {result['size']:,} bytes")
    except WrongPasswordError as e:
        print(c_err(f"\n✗ {e}"))
    except NoHiddenDataError as e:
        print(c_err(f"\n✗ {e}"))
    except SteganographyError as e:
        print(c_err(f"\n✗ {e}"))
    except Exception as e:
        print(c_err(f"\n✗ Unexpected error: {e}"))


def action_capacity(stego):
    section("IMAGE CAPACITY CHECK")
    img_path = ask("Image path: ")
    if not os.path.exists(img_path):
        print(c_err(f"✗ Not found: {img_path}"))
        return
    capacity = stego.calculate_capacity(img_path)
    img = Image.open(img_path)
    w, h = img.size
    print(f"\n  Image: {w}x{h} pixels")
    print(f"  Capacity: {capacity:,} bytes (~{capacity/1024:.1f} KB, ~{capacity:,} text characters)")
    print("  " + capacity_bar(0, capacity))


def action_preview(stego):
    section("IMAGE PREVIEW")
    img_path = ask("Image path: ")
    if not os.path.exists(img_path):
        print(c_err(f"✗ Not found: {img_path}"))
        return
    try:
        term_width = shutil.get_terminal_size((80, 24)).columns
        w = max(20, min(term_width - 4, 100))
        colored_lines, plain_lines, cell_data = ascii_preview(img_path, out_width=w)
    except Exception as e:
        print(c_err(f"✗ Could not preview image: {e}"))
        return

    if confirm("\nExport this ASCII preview to a file?"):
        out_path = ask("Output path (.txt / .ans / .html): ").strip()
        if not out_path:
            print(c_err("✗ No path given, skipping export."))
            return
        try:
            saved_path = export_ascii_preview(out_path, colored_lines, plain_lines, cell_data)
            print(c_ok(f"✓ Saved to: {saved_path}"))
        except Exception as e:
            print(c_err(f"✗ Could not export preview: {e}"))


def action_batch_hide(stego):
    section("BATCH HIDE")
    print(c_dim("  Enter a folder path, or several image paths separated by commas."))
    raw = ask("Cover images (folder or list): ")
    images = resolve_images(raw)
    if not images:
        print(c_err("✗ No images found."))
        return
    print(c_dim(f"  Found {len(images)} image(s)."))

    mode = ask("Hide (t)ext or (f)ile? [t/f]: ").lower()
    password = ask("Password: ")
    out_dir = ask("Output folder: ") or "."
    os.makedirs(out_dir, exist_ok=True)

    file_path = None
    message = None
    if mode == "f":
        file_path = ask("File to hide: ")
        if not os.path.exists(file_path):
            print(c_err(f"✗ File not found: {file_path}"))
            return
    else:
        message = ask("Secret message: ")

    results = []
    for idx, img_path in enumerate(images, 1):
        name = os.path.basename(img_path)
        out_path = os.path.join(out_dir, os.path.splitext(name)[0] + "_encoded.png")
        print(f"\n{c_a(f'[{idx}/{len(images)}]')} {name}")
        try:
            if mode == "f":
                out, used, cap = stego.hide_file(img_path, out_path, file_path, password, progress=True)
            else:
                out, used, cap = stego.hide_message(img_path, out_path, message, password, progress=True)
            print(c_ok(f"  ✓ {out}"))
            results.append((name, True, None))
        except SteganographyError as e:
            print(c_err(f"  ✗ {e}"))
            results.append((name, False, str(e)))
        except Exception as e:
            print(c_err(f"  ✗ Unexpected error: {e}"))
            results.append((name, False, str(e)))

    print()
    section("BATCH SUMMARY")
    ok_count = sum(1 for r in results if r[1])
    for name, ok, err in results:
        mark = c_ok("✓") if ok else c_err("✗")
        print(f"  {mark} {name}" + ("" if ok else f"  {c_dim(err)}"))
    print(f"\n  {ok_count}/{len(results)} succeeded.")


def action_batch_extract(stego):
    section("BATCH EXTRACT")
    print(c_dim("  Enter a folder path, or several image paths separated by commas."))
    raw = ask("Encoded images (folder or list): ")
    images = resolve_images(raw)
    if not images:
        print(c_err("✗ No images found."))
        return
    print(c_dim(f"  Found {len(images)} image(s)."))

    password = ask("Password: ")
    out_dir = ask("Output folder for extracted files (. for current): ") or "."
    os.makedirs(out_dir, exist_ok=True)

    results = []
    for idx, img_path in enumerate(images, 1):
        name = os.path.basename(img_path)
        print(f"\n{c_a(f'[{idx}/{len(images)}]')} {name}")
        try:
            result = stego.extract_file(img_path, password, out_dir, progress=True)
            if result["type"] == "text":
                print(c_ok("  ✓ Text message:"))
                print("    " + result["content"].replace("\n", "\n    "))
            else:
                print(c_ok(f"  ✓ Saved: {result['path']} ({result['size']:,} bytes)"))
            results.append((name, True, None))
        except SteganographyError as e:
            print(c_err(f"  ✗ {e}"))
            results.append((name, False, str(e)))
        except Exception as e:
            print(c_err(f"  ✗ Unexpected error: {e}"))
            results.append((name, False, str(e)))

    print()
    section("BATCH SUMMARY")
    ok_count = sum(1 for r in results if r[1])
    for name, ok, err in results:
        mark = c_ok("✓") if ok else c_err("✗")
        print(f"  {mark} {name}" + ("" if ok else f"  {c_dim(err)}"))
    print(f"\n  {ok_count}/{len(results)} succeeded.")


# ============================================================================
# MAIN MENU
# ============================================================================

MENU_ITEMS = [
    ("1", "Hide Text Message"),
    ("2", "Extract Text Message"),
    ("3", "Hide File"),
    ("4", "Extract File"),
    ("5", "Check Image Capacity"),
    ("6", "Preview Image"),
    ("7", "Batch Hide"),
    ("8", "Batch Extract"),
    ("9", "Quick Start Guide"),
    ("0", "Exit"),
]


def print_menu():
    """Plain, no-emoji menu in a two-column layout. Uses the separate
    sea green/terracotta UI palette (ui1/ui2) — kept distinct from the banner's
    orange/cyan — with one color per column rather than per row."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.box import ROUNDED

    half = (len(MENU_ITEMS) + 1) // 2
    left_items = MENU_ITEMS[:half]
    right_items = MENU_ITEMS[half:]

    grid = Table.grid(padding=(0, 3))
    grid.add_column(justify="right")
    grid.add_column()
    grid.add_column(justify="right")
    grid.add_column()

    for i in range(half):
        lk, ll = left_items[i]
        row = [Text(f"{lk}.", style="ui1"), Text(ll, style="ui1")]
        if i < len(right_items):
            rk, rl = right_items[i]
            row += [Text(f"{rk}.", style="ui2"), Text(rl, style="ui2")]
        else:
            row += [Text(""), Text("")]
        grid.add_row(*row)

    rich_console.print()
    rich_console.print(Panel.fit(grid, title="[ui_title] MAIN MENU [/]", border_style="ui_border", box=ROUNDED))


def main():
    print_banner()
    stego = SimpleSteganography()

    actions = {
        "1": action_hide_text,
        "2": action_extract_text,
        "3": action_hide_file,
        "4": action_extract_file,
        "5": action_capacity,
        "6": action_preview,
        "7": action_batch_hide,
        "8": action_batch_extract,
    }

    while True:
        print_menu()
        choice = ask("Select (0-9): ")

        if choice == "9":
            print_guide()
            continue
        if choice == "0":
            print()
            print(gradient_line("Thank you for using PHANTOM!".center(WIDTH), Theme.A, Theme.B))
            print()
            break

        action = actions.get(choice)
        if not action:
            print(c_err("✗ Invalid choice! Select 0-9."))
            continue

        try:
            action(stego)
        except KeyboardInterrupt:
            print(c_warn("\n Cancelled."))
        except Exception as e:
            print(c_err(f"\n✗ Error: {e}"))
            print(c_dim("  Double-check the password and that the image is valid."))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c_warn("\n\n Interrupted. Exiting..."))
    except Exception as e:
        print(c_err(f"\n✗ Fatal error: {e}"))
