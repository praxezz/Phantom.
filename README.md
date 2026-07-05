# 👻 PHANTOM — Steganography Toolkit

**PHANTOM** hides encrypted text messages or entire files inside ordinary-looking images using LSB (least-significant-bit) steganography. Every payload is compressed and AES-256 encrypted *before* a single bit touches the image — so even someone who suspects a picture is hiding something can't read it without the password.

```
 ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
 ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
 ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
 ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
 ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
```

> **Status:** actively developed personal security tool. See [Disclaimer](#-disclaimer).
>
> See also: **[PASSEC](https://github.com/<your-username>/passec)** — a password strength/breach auditor, also by Praveen K. PHANTOM's own Quick Start Guide recommends it for checking your PHANTOM password before you use it.

---

## ✨ Features

- **LSB steganography** — embeds data bit-by-bit into pixel color channels, so the output image looks visually identical to the original.
- **AES-256-CBC encryption** — every payload is encrypted with a PBKDF2-derived key (100,000 iterations, random salt + IV per file) before embedding, so even an attacker who extracts the raw bits gets ciphertext, not your data.
- **Automatic compression** — payloads over 100 bytes are zlib-compressed first when it actually reduces size, fitting more into the same image.
- **Hide text or entire files** — messages, PDFs, ZIPs, DOCX, other images, anything — extracted files come back with their original name and content intact.
- **Capacity checking** — calculates exactly how many bytes an image can hold before you try to hide something too large for it.
- **ASCII/ANSI image preview** — render any image as colored ASCII art in the terminal, with export to `.txt`, `.ans` (truecolor ANSI), or `.html`.
- **Batch mode** — hide or extract the same message/file across an entire folder (or comma-separated list) of images in one pass, with a per-image success/failure summary.
- **Built-in Quick Start Guide** — a full walkthrough of best practices, capacity estimates, and security notes, available from the in-app menu.
- **Rich terminal UI** — gradient banner, colored progress/capacity bars, two-column menu.

---

## 🚀 Getting Started

### Requirements

- Python 3.8+
- Windows, macOS, or Linux

### Installation

```bash
git clone https://github.com/<your-username>/phantom.git
cd phantom
pip install -r requirements.txt
```

### Run it

```bash
python phantom.py
```

You'll land on an interactive menu — no CLI flags to remember.

---

## 🧰 Menu Options

| Option | What it does |
|---|---|
| **1. Hide Text Message** | Embed a text message into a cover image, protected by a password. |
| **2. Extract Text Message** | Recover a hidden text message from an encoded image. |
| **3. Hide File** | Embed an entire file (any type) into a cover image. |
| **4. Extract File** | Recover a hidden file with its original name and size. |
| **5. Check Image Capacity** | See exactly how many bytes/characters an image can hold. |
| **6. Preview Image** | Render an ASCII/ANSI art preview, with optional export. |
| **7. Batch Hide** | Hide the same message/file into every image in a folder or list. |
| **8. Batch Extract** | Extract from every image in a folder or list in one pass. |
| **9. Quick Start Guide** | Full in-app walkthrough, tips, and security notes. |
| **0. Exit** | Quit. |

---

## 🔑 How it works

1. **Compress** — payloads over 100 bytes are zlib-compressed if that actually shrinks them.
2. **Encrypt** — the (possibly compressed) payload is encrypted with AES-256-CBC, using a key derived from your password via PBKDF2 (100,000 iterations) with a fresh random salt and IV every time.
3. **Package** — a small header (magic bytes, version, metadata) is prepended so PHANTOM can recognize and correctly decode its own output later.
4. **Embed** — the encrypted payload's bits replace the least-significant bit of ~70% of the image's pixel color values, using vectorized NumPy operations. The output is always saved as **PNG** (lossless) — JPG/other lossy formats would destroy the hidden bits.
5. **Extract** — reverses the process: reads the LSBs, verifies the magic header, decrypts with the password you provide, decompresses if needed, and restores the original message or file.

### Capacity (approximate)

| Image size | Approx. capacity |
|---|---|
| 800×600 | ~50 KB |
| 1920×1080 | ~300 KB |
| 3840×2160 | ~1.2 MB |

Use menu option 5 for an exact figure for any specific image.

---

## ⚙️ Dependencies

| Package | Required? | Purpose |
|---|---|---|
| `Pillow` | ✅ Required | Image loading/saving (PNG, JPG, BMP, WEBP, TIFF) |
| `numpy` | ✅ Required | Vectorized pixel/bit manipulation |
| `pycryptodome` | ✅ Required | AES-256-CBC encryption + PBKDF2 key derivation |
| `rich` | ✅ Required | Banner, menus, panels |
| `colorama` | Optional | ANSI color fallback on terminals without truecolor support |

```bash
pip install -r requirements.txt
```

---

## 💡 Tips

- ✅ Use a strong, unique password — see [PASSEC](https://github.com/<your-username>/passec) if you want a quick strength/breach check first.
- ✅ Keep the output as PNG — never re-save an encoded image as JPG or another lossy format.
- ✅ Test extraction immediately after hiding, before sharing or storing the image anywhere.
- ✅ Run Check Capacity (option 5) before hiding a large file, so you know it'll fit.
- ❌ Don't reuse the input filename as the output filename.
- ❌ Don't edit, crop, filter, or recompress an encoded image.
- ❌ Don't upload encoded images to platforms that automatically recompress images (many social/messaging apps do this and will destroy the hidden data).

---

## 🗺️ Roadmap ideas

- [ ] Non-interactive/scriptable CLI flags for automation
- [ ] Additional embedding methods (DCT-based, for JPEG survivability)
- [ ] Optional Reed-Solomon error correction to survive minor image edits
- [ ] Progress bars for batch mode aggregated across all images

Have another idea? Open an issue!

---

## 🤝 Contributing

Contributions are welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup instructions and guidelines before opening a PR.

## 🔒 Security

Found a security issue in PHANTOM itself? See **[SECURITY.md](SECURITY.md)**.

## ⚠️ Disclaimer

PHANTOM protects the *confidentiality* of your data (via AES-256 encryption) but LSB steganography does not guarantee *undetectability* — dedicated statistical steganalysis tools can sometimes flag that an image was modified, even without being able to read its contents. Don't rely on PHANTOM as your only layer of protection for highly sensitive data, and never re-upload encoded images to platforms that recompress images (this will destroy the hidden payload entirely, not just make it detectable).

## 📄 License

Released under the [MIT License](LICENSE) — Copyright (c) 2025 Praveen K.
