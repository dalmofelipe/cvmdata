from __future__ import annotations

import pytest

from cvmdata.pipeline.steps import (
    step_calculate_indicators,
    step_classify_info_cad,
    step_load_cvm,
    step_load_info_cad,
    step_normalize_financial,
)
from tests.support import (
    BPA_ROWS,
    BPP_ROWS,
    DRE_ROWS,
    make_balance_csv,
    make_cad_csv,
    make_flow_csv,
)

pytestmark = pytest.mark.integration


def test_pipeline_steps_process_local_fixtures(tmp_path, db):
    raw_dir = tmp_path / "raw"
    csv_dir = raw_dir / "itr" / "2024"
    csv_dir.mkdir(parents=True)

    make_balance_csv(
        csv_dir / "itr_cia_aberta_BPA_con_2024.csv",
        data_rows=BPA_ROWS,
    )
    make_balance_csv(
        csv_dir / "itr_cia_aberta_BPP_con_2024.csv",
        data_rows=BPP_ROWS,
    )
    make_flow_csv(
        csv_dir / "itr_cia_aberta_DRE_con_2024.csv",
        data_rows=DRE_ROWS,
    )
    cad_path = make_cad_csv(
        tmp_path / "cad.csv",
        [{"CNPJ_CIA": "00.000.000/0001-91", "SETOR_ATIV": "Alimentos"}],
    )

    assert step_load_info_cad(db, cad_path).status == "success"
    assert step_load_cvm(db, [2024], tmp_path).status == "success"
    assert step_normalize_financial(db).status == "success"
    assert step_classify_info_cad(db).status == "success"
    indicators = step_calculate_indicators(db)

    assert indicators.status == "success"
    assert indicators.metrics["rows"] > 0
