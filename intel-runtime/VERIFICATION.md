# Intel package verification

The final offline run finished at `2026-11-15T03:46:02.648469+00:00` on macOS with Python 3.12.13. It passed 158 tests and five subtests, reported as 163 JUnit cases, with zero failures, errors, or skips. This is source and simulated behavior verification, not Intel hardware acceptance.

The checked modules cover persistent records, idempotence, outcome corrections and reviews, HTTP authentication and unavailable control routes, export auditing, motor discovery using a fake bus, and shared-context polling using a fake client. All 125 original/aliased/derived files retained their SHA-256 values before and after execution. Forty-two original Python files parsed successfully, and nine shell scripts passed `bash -n`.

The portable launcher help command created no runtime data. Explicit initialization in a temporary directory produced zero records, zero events, and a private API token with mode `0600`; that temporary runtime was deleted. No token value was included in evidence. Five reviewed export-audit CLI children and two launcher children ran with process-local offline guards. The run recorded zero denied-operation attempts.

Evidence:

- [Final structured result](verification/offline-02/result.json)
- [Final pytest output](verification/offline-02/pytest.log)
- [Final JUnit cases](verification/offline-02/tests.xml)
- [Initial offline result](verification/offline-01/result.json), before launcher smoke and synthetic PNG addition
- [Source and fixture provenance](SOURCE_ORIGINS.json)
- [Unreceived files and absent implementation](SOURCE_GAPS.json)

The guards deny socket connections/listeners, DNS, real hardware-library imports, device opens, unreviewed subprocesses, and signals to external processes. The Gemma provider call is separately replaced with a denying function. The tests' deliberately fake bus and client implementations remain usable. These guards are process-local checks rather than an OS sandbox; the original test and diagnostic source was reviewed before selecting the test set.

The package does not include the current Intel analyst tests or provider-check tests. No provider, camera, motor, Studio, training, watcher, tunnel, or service was launched. Historical Intel reports under `source/` retain their original timestamps and claims; they are not fresh Mac verification. The service difference between main port 8000 and isolated port 52197 remains a dated observation, not a claim of current deployment.

After that offline run, the reviewed supplement supplied two exact original files: the 162-byte station ignore rules and the 159-byte synthetic provider PNG. [Supplement verification](verification/supplement.json) records their hash checks and independent PNG signature, dimensions, and chunk CRC checks. All 127 current provenance entries were rehashed successfully. Application code remained unchanged, so the previously passing suite was not repeated. The three redacted test copies remain separate review material and were not run. Intel's dated confirmation of the 68-byte evidence blob is recorded separately from the original local AST fixture derivation.

Run `python tools/verify_package.py` to verify the final seal and `python tools/verify_offline.py` in an environment with the pinned station requirements to repeat the selected checks. New test output goes to a new ignored `.runtime/verification/` directory by default. The complete final file seal is `SOURCE_MANIFEST.json`; it excludes its own self-reference and ignored runtime/cache directories.
