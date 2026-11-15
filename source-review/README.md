# Reviewed Intel supplement

The remaining-source request is `90672035-350b-43ad-88d6-025885cfbd65`. The narrower review request is `a8046978-b5fa-4e1b-9363-d18ee24c5a45`, delivered on November 15, 2026.

The three files under `copies/` are complete **redacted review copies**, stored as `.review.txt` so they are not collected or executed as tests. Intel applied the unchanged context redactor to each complete original before chunking. Mac checked all part and whole-copy hashes and independently read back all fifteen supplement/session notes through authenticated MCP. [RECEIPT.json](RECEIPT.json) records original hashes, redacted hashes, changed lines, stated fixture purpose, exact artifact checks and readback hashes.

| Original path | Original bytes | Redacted copy bytes | Status |
| --- | ---: | ---: | --- |
| `morph-station/server/stationProxy.test.ts` | 17,218 | 17,151 | Original absent; complete review copy received |
| `HachingJunction/station/tests/test_analysis.py` | 52,823 | 52,807 | Original absent; complete review copy received |
| `HachingJunction/setup/provider-check/test_check.py` | 11,561 | 11,513 | Original absent; complete review copy received |

The flagged values are reported as synthetic authentication/configuration fixtures; their surrounding code was reviewed separately. Redaction changes test behavior, and the provider-check copy has a syntax error caused by the existing redactor at line 24. These copies are not repaired, used as executable substitutes or counted as original-source receipt. Keep the originals with their Intel owner until a reviewed delivery path is available.

The same supplement supplies two exact original artifacts now included in `intel-runtime/`: 162-byte station ignore rules and a 159-byte synthetic 64×64 PNG. Its PNG has only IHDR, IDAT and IEND chunks, with validated CRCs and no metadata. Original inventory receipt is now **237 of 240 files**.

Intel also reports a fresh check at **2026-11-15T03:48:06.194996+00:00** confirming that the referenced 68-byte synthetic evidence blob matches the existing test constant. The package's fixture was derived from that already received constant; no runtime blob or unrelated evidence was transferred.

[MANIFEST.json](MANIFEST.json) seals the three review copies. This receipt establishes source/review availability, not complete test-suite execution, deployment or physical acceptance.
