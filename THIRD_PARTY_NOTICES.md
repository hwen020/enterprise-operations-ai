# Provenance and licenses

The application, UI, tests, protocol helper, sample data, vectors, PDF generator and screenshots were newly authored for this independent repository. No other application's source, company material, UI kit, font, stock photo or icon pack is vendored. Generic protocol constants and standard API usage are not imported application code.

Original project code and authored assets use MIT. The owner must confirm authority to release the work and accept MIT before publication. This implementation inventory is not a legal opinion or waiver of another party's rights.

| Item | Use | Handling |
| --- | --- | --- |
| Python / standard library | Runtime and tests | Python license stack including PSF-2.0; not vendored |
| SQLite | Python runtime module | Public domain; no separate binary vendored |
| Browser APIs | UI | No bundled third-party package |
| Chrome/Chromium | Optional local browser tests | Installed external tool; no binary redistributed |
| Node.js | Optional syntax checks | External tool, not needed to build/run |
| Official Python Docker image / OS | Optional container | Their own notices remain applicable; not covered by project MIT |

Zero third-party pip/npm application dependencies. requirements.txt is comments-only. No dependency archive or hidden vendored source is included. The example PDF uses the standard PDF base font Helvetica, without embedding a font binary.

References:
- https://www.python.org/about/legal/
- https://docs.python.org/3/license.html
- https://www.sqlite.org/copyright.html

Future copied sources, packages or assets require a new license review and preserved notices.
