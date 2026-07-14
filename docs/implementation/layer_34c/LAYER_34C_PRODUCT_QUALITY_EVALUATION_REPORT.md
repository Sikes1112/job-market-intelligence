# Layer 34C Product Quality Evaluation Report

The generated product-quality evaluation artifact path is:

`docs/implementation/layer_34c/artifacts/product_quality_evaluation_report.json`

The backend report object exposes the same value as `artifact_path`.

Generation is read-only with respect to canonical data: callers serialize
`MarketIntelligenceService.product_quality_evaluation_report(...).as_dict()` to
the path above for audit consumption. The service composes existing calibration,
robustness, contradiction, grounding, explanation-quality, and differentiation
outputs; it does not import data, refresh sources, call external services, or
write canonical tables.

The report also exposes the Layer 34C differentiation gate:

- `differentiation_threshold`
- `differentiation_passed`
- `differentiation_notes`

Unsupported or abstained diagnostic rankings are not counted as substantive
cross-goal differentiation wins. The notes explain when an identical ordering is
diagnostic because one of the goals abstains or is not supported.
