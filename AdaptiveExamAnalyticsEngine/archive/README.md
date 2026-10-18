# Archive — superseded sample / demo scripts

These scripts were part of earlier data-generation iterations and are kept for history only.
They are **not** used at runtime and should not be imported.

- `generate_sample_v2.py` — one-off generator for gradev2 (superseded by `load_sample_v3.py` + `app/sample_data/`)
- `load_sample_v2.py` — loader for gradev2 (use `load_sample_v3.py` instead)
- `migrate_sample_v2.py` — migration from `app/sample_data/` to v2 shape (superseded)
- `run_lec_sample.py` — lecturer demo runner (logic now in `app/api/lecturer.py` + `tests/test_api_lecturer.py`; imports from `run_sample.py` fragile — archived)

Canonical entry points:
- `../run_sample.py` — seed + materialize + compute exam analytics
- `../load_sample_v3.py` — load v3 extended JSON
- `../switch_llm.py` — toggle local / colab LLM
