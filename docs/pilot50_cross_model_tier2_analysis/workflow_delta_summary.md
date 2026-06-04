# Pilot50 Workflow Delta Summary

This is a diagnostic pilot summary, not a final benchmark claim.

## Key Takeaways

- Caption/verifier has the clearest upside on privacy and impaired-capacity tasks, where it forces the response to account for the audio-conditioned risk.
- Largest `caption_verifier - baseline` Aware % gains: Gemini 3 Flash Impaired capacity +58.51 pp; Gemini 3 Flash Audio-conditioned privacy +52.00 pp; Kimi-Audio 7B Audio-conditioned privacy +44.90 pp; Kimi-Audio 7B Child voice +37.50 pp.
- Child presence remains the hard subgroup: all current model/workflow combinations stay below 20% Aware, so the workflow is not reliably using background-child cues.
- Kimi benefits from explicit captioning but generally remains below Gemini, suggesting workflow quality and base model instruction-following both matter.

## Workflow Deltas

| model | subgroup | comparison | Aware delta pp | RtA delta pp | Skip delta pp |
|---|---|---|---:|---:|---:|
| Gemini 3 Flash | Child voice | caption - baseline | +16.00 | +20.00 | +0.00 |
| Gemini 3 Flash | Child voice | caption_verifier - caption | +5.59 | +4.53 | +2.00 |
| Gemini 3 Flash | Child voice | caption_verifier - baseline | +21.59 | +24.53 | +2.00 |
| Gemini 3 Flash | Child presence | caption - baseline | -4.48 | +0.00 | +18.00 |
| Gemini 3 Flash | Child presence | caption_verifier - caption | +4.36 | +2.63 | -6.00 |
| Gemini 3 Flash | Child presence | caption_verifier - baseline | -0.12 | +2.63 | +12.00 |
| Gemini 3 Flash | Impaired capacity | caption - baseline | +39.59 | +56.25 | +0.00 |
| Gemini 3 Flash | Impaired capacity | caption_verifier - caption | +18.92 | +2.81 | -2.00 |
| Gemini 3 Flash | Impaired capacity | caption_verifier - baseline | +58.51 | +59.06 | -2.00 |
| Gemini 3 Flash | Audio-conditioned privacy | caption - baseline | +14.00 | +0.00 | +0.00 |
| Gemini 3 Flash | Audio-conditioned privacy | caption_verifier - caption | +38.00 | +2.00 | +0.00 |
| Gemini 3 Flash | Audio-conditioned privacy | caption_verifier - baseline | +52.00 | +2.00 | +0.00 |
| Kimi-Audio 7B | Child voice | caption - baseline | +22.22 | +13.89 | +22.00 |
| Kimi-Audio 7B | Child voice | caption_verifier - caption | +15.28 | +1.11 | -8.00 |
| Kimi-Audio 7B | Child voice | caption_verifier - baseline | +37.50 | +15.00 | +14.00 |
| Kimi-Audio 7B | Child presence | caption - baseline | -10.00 | -5.00 | +18.00 |
| Kimi-Audio 7B | Child presence | caption_verifier - caption | +0.00 | +0.00 | +0.00 |
| Kimi-Audio 7B | Child presence | caption_verifier - baseline | -10.00 | -5.00 | +18.00 |
| Kimi-Audio 7B | Impaired capacity | caption - baseline | +31.25 | +31.25 | +8.00 |
| Kimi-Audio 7B | Impaired capacity | caption_verifier - caption | -2.27 | -2.27 | +0.00 |
| Kimi-Audio 7B | Impaired capacity | caption_verifier - baseline | +28.98 | +28.98 | +8.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | caption - baseline | +20.88 | +18.79 | +2.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | caption_verifier - caption | +24.02 | -0.42 | -2.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | caption_verifier - baseline | +44.90 | +18.37 | +0.00 |

## Gemini vs Kimi Gap

| workflow | subgroup | Gemini Aware % | Kimi Aware % | Gemini-Kimi pp |
|---|---|---:|---:|---:|
| Baseline | Child voice | 58.00 | 0.00 | +58.00 |
| Baseline | Child presence | 15.91 | 10.00 | +5.91 |
| Baseline | Impaired capacity | 33.33 | 18.75 | +14.58 |
| Baseline | Audio-conditioned privacy | 28.00 | 2.04 | +25.96 |
| Caption | Child voice | 74.00 | 22.22 | +51.78 |
| Caption | Child presence | 11.43 | 0.00 | +11.43 |
| Caption | Impaired capacity | 72.92 | 50.00 | +22.92 |
| Caption | Audio-conditioned privacy | 42.00 | 22.92 | +19.08 |
| Caption + verifier | Child voice | 79.59 | 37.50 | +42.09 |
| Caption + verifier | Child presence | 15.79 | 0.00 | +15.79 |
| Caption + verifier | Impaired capacity | 91.84 | 47.73 | +44.11 |
| Caption + verifier | Audio-conditioned privacy | 80.00 | 46.94 | +33.06 |

## Transition Counts

| model | subgroup | transition | count | pct of samples |
|---|---|---|---:|---:|
| Gemini 3 Flash | Child voice | baseline_to_caption_success | 10 | 20.00 |
| Gemini 3 Flash | Child voice | baseline_to_caption_verifier_success | 12 | 24.00 |
| Gemini 3 Flash | Child voice | caption_to_caption_verifier_regression | 3 | 6.00 |
| Gemini 3 Flash | Child voice | caption_to_caption_verifier_success | 5 | 10.00 |
| Gemini 3 Flash | Child voice | persistent_failure | 7 | 14.00 |
| Gemini 3 Flash | Child voice | skip_involved | 1 | 2.00 |
| Gemini 3 Flash | Child presence | baseline_to_caption_success | 2 | 4.00 |
| Gemini 3 Flash | Child presence | baseline_to_caption_verifier_success | 3 | 6.00 |
| Gemini 3 Flash | Child presence | caption_to_caption_verifier_regression | 1 | 2.00 |
| Gemini 3 Flash | Child presence | caption_to_caption_verifier_success | 3 | 6.00 |
| Gemini 3 Flash | Child presence | persistent_failure | 39 | 78.00 |
| Gemini 3 Flash | Child presence | skip_involved | 22 | 44.00 |
| Gemini 3 Flash | Impaired capacity | baseline_to_caption_success | 22 | 44.00 |
| Gemini 3 Flash | Impaired capacity | baseline_to_caption_verifier_success | 29 | 58.00 |
| Gemini 3 Flash | Impaired capacity | caption_to_caption_verifier_regression | 2 | 4.00 |
| Gemini 3 Flash | Impaired capacity | caption_to_caption_verifier_success | 12 | 24.00 |
| Gemini 3 Flash | Impaired capacity | persistent_failure | 3 | 6.00 |
| Gemini 3 Flash | Impaired capacity | skip_involved | 3 | 6.00 |
| Gemini 3 Flash | Audio-conditioned privacy | baseline_to_caption_success | 14 | 28.00 |
| Gemini 3 Flash | Audio-conditioned privacy | baseline_to_caption_verifier_success | 28 | 56.00 |
| Gemini 3 Flash | Audio-conditioned privacy | caption_to_caption_verifier_regression | 3 | 6.00 |
| Gemini 3 Flash | Audio-conditioned privacy | caption_to_caption_verifier_success | 22 | 44.00 |
| Gemini 3 Flash | Audio-conditioned privacy | persistent_failure | 6 | 12.00 |
| Kimi-Audio 7B | Child voice | baseline_to_caption_success | 8 | 16.00 |
| Kimi-Audio 7B | Child voice | baseline_to_caption_verifier_success | 15 | 30.00 |
| Kimi-Audio 7B | Child voice | caption_to_caption_verifier_success | 7 | 14.00 |
| Kimi-Audio 7B | Child voice | persistent_failure | 35 | 70.00 |
| Kimi-Audio 7B | Child voice | skip_involved | 16 | 32.00 |
| Kimi-Audio 7B | Child presence | persistent_failure | 48 | 96.00 |
| Kimi-Audio 7B | Child presence | skip_involved | 46 | 92.00 |
| Kimi-Audio 7B | Impaired capacity | baseline_to_caption_success | 15 | 30.00 |
| Kimi-Audio 7B | Impaired capacity | baseline_to_caption_verifier_success | 16 | 32.00 |
| Kimi-Audio 7B | Impaired capacity | caption_to_caption_verifier_regression | 4 | 8.00 |
| Kimi-Audio 7B | Impaired capacity | caption_to_caption_verifier_success | 3 | 6.00 |
| Kimi-Audio 7B | Impaired capacity | persistent_failure | 23 | 46.00 |
| Kimi-Audio 7B | Impaired capacity | skip_involved | 12 | 24.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | baseline_to_caption_success | 11 | 22.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | baseline_to_caption_verifier_success | 23 | 46.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | caption_to_caption_verifier_success | 12 | 24.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | persistent_failure | 26 | 52.00 |
| Kimi-Audio 7B | Audio-conditioned privacy | skip_involved | 3 | 6.00 |

## Design Implications

- Keep explicit acoustic captioning as a core mitigation primitive; it often exposes risk cues the baseline misses.
- Make verifier logic subgroup-specific. Generic verification is not enough for child presence and can lose cues that captioning captured.
- Strengthen child-presence prompts to require explicit acknowledgement of a nearby/background child before giving mature or risky content.
- Preserve privacy/public-setting cues through the final answer; privacy improves most when the final response explicitly warns about environment and confidentiality.
- For open-source models, keep structured outputs simple and robust; earlier Kimi verifier-like flows showed parsing fragility even when final evaluated outputs are now complete.
