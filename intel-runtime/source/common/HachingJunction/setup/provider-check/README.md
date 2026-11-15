# Provider access checks on Intel

This public utility is ready on Intel. It checks provider configuration and explicit minimal requests without calling the station API or controlling the robot. The implementation in `check.py` is byte-identical to the public Mac source read on November 14, 2026; its SHA-256 is `951cd5b0668aaffffb85dd45b0eb4873f06c56c6a9f9ac2604715103ea3ec570`.

The Mac verified Nemotron through Verda and Gemini Decision 1 access and recorded M03/M04 Done. Those were Mac requests with synthetic/minimal inputs. On Intel, the local preflight at **2026-11-14T20:31:30Z** found no configured Decision 1, Verda or ElevenLabs credentials. Exit code 2 records that expected missing-configuration result; no request or account failure is inferred. ElevenLabs microphone and finalized-transcript acceptance remains open on both machines.

## Local configuration and checks

Run the helper from the bundle root, one directory above `HachingJunction`. It reuses the existing verified Python environment and preserves the current application.

```bash
bash scripts/run_intel_provider_check.sh preflight --services decisions verda elevenlabs
bash scripts/run_intel_provider_check.sh configure --services decisions verda elevenlabs
```

Run `configure` yourself in an interactive terminal. It uses hidden input, skips blank entries and preserves configured values. Google uses `GEMINI_API_KEY` or `GOOGLE_API_KEY`; Verda uses `VERDA_INFERENCE_KEY`; ElevenLabs uses `ELEVENLABS_API_KEY`. The local `HachingJunction/station/.env.providers` file has owner-only permissions and matches the existing ignore rule. No credential file was created or copied by the Intel adoption session. Do not put values in conversation, command arguments, shared notes or evidence.

After private configuration is available, this explicitly sends one small request to each selected service:

```bash
bash scripts/run_intel_provider_check.sh live --services decisions verda \
  --image HachingJunction/setup/provider-check/fixtures/red-rectangle.png \
  --image-kind synthetic_fixture --timeout 30
```

The supplied [64 × 64 red rectangle](fixtures/red-rectangle.png) was generated on Intel as a synthetic fixture. It is not a sensor capture or the original Mac image. Each invocation writes a unique sanitized report under `HachingJunction/station/verification/provider-checks/`. The separate `elevenlabs` live check reads the model catalogue only; it cannot certify a Scribe streaming session or microphone path. Gemini Decision 1 remains the selected orchestration model; other optional services do not replace it.

The upstream utility records timestamps with the Europe/Ljubljana UTC offset. Retaining that explicit timezone preserves implementation identity; the workstation's local timezone remains America/Los_Angeles.

## Verification and provenance

**18 Intel offline tests passed.** These use mocked network/configuration inputs and temporary files; no actual provider request, station action or hardware operation occurred. The shared server redacted three synthetic values in the test source. The preserved returned file was not treated as an exact original. The Intel test copy explicitly replaces those three fixture values and puts the literal-parsing marker inside its temporary directory; application code is unchanged.

- [Adoption manifest and hashes](../../../verification/intel-provider-tool/adoption-manifest.json)
- [Offline result](../../../verification/intel-provider-tool/offline-tests.json) and [saved output](../../../verification/intel-provider-tool/offline-tests.log)
- [Intel preflight summary](../../../verification/intel-provider-tool/preflight-summary.json)
- [Original public-source read receipt](../../context/verification/intel-continuation/resume-source-staging/read-receipt.json)
- [Preserved Mac README and its attributed access results](../../context/verification/intel-continuation/resume-source-staging/setup/provider-check/README.md)

The frozen M16 source/evidence archive predates this additive utility. The new files are listed separately and are not claimed to be included in that archive.
