# Contributing to PHANTOM

Thanks for your interest in improving PHANTOM! Contributions are welcome — new export formats, capacity/performance improvements, additional image format support, and documentation fixes all help.

## Getting started

1. Fork the repo and clone your fork.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create a branch for your change: `git checkout -b feature/my-improvement`.

## Running it

```bash
python phantom.py
```

A good sanity check after any change to the encoding/decoding path: hide a text message in a test image (option 1), then immediately extract it with the same password (option 2), and confirm you get the original text back exactly.

## Guidelines

- Never weaken the crypto path (AES-256-CBC + PBKDF2 with a random salt/IV per file) to "simplify" something — if a change touches `encrypt_data`/`decrypt_data`, round-trip test it thoroughly.
- Keep the output format PNG-only — lossy formats (JPG, etc.) destroy the hidden LSB data, so this isn't a style choice.
- New menu actions should follow the existing `action_*(stego)` pattern and use the shared `SteganographyError` subclasses for user-facing error messages instead of raw exceptions.
- Match the existing UI style (`c_ok`/`c_err`/`c_warn`/`c_dim` helpers, `section()` headers) rather than plain `print()`.
- If you add support for a new image format, update `IMAGE_EXTS` and confirm `Image.open(...).convert("RGB")` behaves correctly for it.

## Reporting bugs / suggesting features

Open a GitHub Issue with your OS/Python version, the menu option you used, and what happened vs. what you expected (a sample image helps, but never attach one containing anything sensitive).

## Security issues

See [SECURITY.md](SECURITY.md).
