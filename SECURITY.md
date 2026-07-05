# Security

PHANTOM encrypts real secrets (messages/files) before hiding them, so if you spot a way that data could leak, get logged, or be recovered without the password, I'd like to know.

## Found a problem?

- Open an issue on this repo, or
- Reach out to the maintainer directly (see profile) if it's something sensitive you'd rather not put in a public issue.

When you do, please include:
- PHANTOM version / commit hash
- OS and Python version
- Steps to reproduce
- What actually happened vs. what you expected

## Scope notes

- Payloads are AES-256-CBC encrypted with a PBKDF2-derived key (100,000 iterations, random salt + IV per file) before a single bit touches the image — issues in that crypto path are in scope.
- Steganographic detectability (i.e., whether a statistical stego-analysis tool can tell an image was modified) is a known, inherent limitation of LSB steganography in general, not a PHANTOM-specific bug — but if you find a way to recover the *plaintext* without the password, that's in scope.
