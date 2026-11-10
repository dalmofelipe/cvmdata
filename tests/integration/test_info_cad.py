"""Testes de integração do módulo cadastral: load_cadastro e classify_cadastro.

A classificação é orientada pelo layout reportado (assinatura estrutural), não
pelo setor — ver :mod:`cvmdata.transform.profile`. Os testes abaixo fixam os
comportamentos que sustentam isso: o universo vem das clean, o ``SIT`` não
filtra, e a assinatura exige os dois sinais concordando.
"""

from __future__ import annotations

import pytest

from cvmdata.ingestion.loader import load_info_cad
from cvmdata.transform.info_cad import (
    MissingCadCiaAbertaTableError,
    MissingCleanTablesError,
    classify_info_cad,
)
from cvmdata.transform.profile import FALLBACK_PROFILE
from tests.support import make_cad_csv, seed_classification_rows, setup_classify_schema

pytestmark = pytest.mark.integration

CNPJ_BANCO = "42.737.954/0001-21"
CNPJ_IND = "33.000.167/0001-01"

# Layout financeiro real: o rótulo do 1.01 difere do layout padrão, e o do 2.01
# também. Os dois juntos é o que separa banco de não-banco.
BPA_CAIXA_FINANCEIRO = "Caixa e Equivalentes de Caixa"
BPP_PASSIVOS_FINANCEIROS = "Passivos Financeiros Avaliados ao Valor Justo"
# Layout padrão: "Ativo Circulante"/"Passivo Circulante".
BPA_CAIXA_PADRAO = "Ativo Circulante"
BPP_PASSIVO_CIRCULANTE = "Passivo Circulante"


def _columns(db, table: str) -> list[str]:
    return [r[0] for r in db.execute(f"DESCRIBE {table}").fetchall()]


def _clean_schema(db, *tables: str) -> None:
    """Cria as clean indicadas — a coluna que a classificação usa é CNPJ_CIA —
    e o schema onde a classificação será reconstruída.

    Sem argumento, cria as três; com argumento, só as nomeadas, para exercitar
    universo incompleto.

    `cad_cia_aberta_raw` sai vazia: a classificação exige que ela exista, e
    "cadastro vazio" é diferente de "cadastro ausente".
    """
    setup_classify_schema(db)
    for table in tables or ("bpa_clean", "bpp_clean", "dre_clean"):
        db.execute(
            f"""
            CREATE TABLE {table} (
                CNPJ_CIA  VARCHAR,
                DT_REFER  DATE,
                CD_CVM    VARCHAR,
                DENOM_CIA VARCHAR,
                CD_CONTA  VARCHAR,
                DS_CONTA  VARCHAR
            )
            """
        )


def _insert_clean(
    db,
    table: str,
    cnpj: str,
    cd_conta: str,
    ds_conta: str,
    *,
    cd_cvm: str = "00123",
    denom: str = "EMPRESA TESTE",
    dt_refer: str = "2024-12-31",
) -> None:
    db.execute(
        f"""
        INSERT INTO {table}
            (CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA, CD_CONTA, DS_CONTA)
        VALUES (?, TRY_CAST(? AS DATE), ?, ?, ?, ?)
        """,
        [cnpj, dt_refer, cd_cvm, denom, cd_conta, ds_conta],
    )


def _seed_layout_financeiro(db, cnpj: str, **overrides) -> None:
    """Assinatura completa de banco — os dois sinais concordando."""
    bpa_101 = overrides.get("bpa_101", BPA_CAIXA_FINANCEIRO)
    bpp_201 = overrides.get("bpp_201", BPP_PASSIVOS_FINANCEIROS)
    _insert_clean(db, "bpa_clean", cnpj, "1.01", bpa_101)
    _insert_clean(db, "bpp_clean", cnpj, "2.01", bpp_201)


def _seed_layout_padrao(db, cnpj: str) -> None:
    """Layout de empresa não financeira: mesma posição de código, rótulo comum."""
    _insert_clean(db, "bpa_clean", cnpj, "1.01", BPA_CAIXA_PADRAO)
    _insert_clean(db, "bpp_clean", cnpj, "2.01", BPP_PASSIVO_CIRCULANTE)


def _snapshot(db) -> list[tuple]:
    """Linhas relevantes da classificação — ``updated_at`` fica de fora porque
    muda a cada run e não faz parte da idempotência."""
    return db.execute(
        "SELECT cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,"
        " profile_id, rule_applied"
        " FROM company_classification ORDER BY cnpj_cia"
    ).fetchall()


def _classify_row(db, cnpj: str) -> tuple:
    return db.execute(
        "SELECT profile_id, rule_applied, setor_ativ, cd_cvm, denom_social, denom_comerc"
        " FROM company_classification WHERE cnpj_cia = ?",
        [cnpj],
    ).fetchone()


# ── load_cadastro ─────────────────────────────────────────────────────────────


def test_load_cadastro_returns_row_count(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA", "SETOR_ATIV": "Alimentos"},
            {"CNPJ_CIA": "33.333.333/0001-33", "SIT": "ATIVO", "SETOR_ATIV": ""},
        ],
    )
    inserted = load_info_cad(db, csv_path)
    assert inserted == 3


def test_load_cadastro_table_contains_all_rows(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11"},
            {"CNPJ_CIA": "22.222.222/0001-22"},
        ],
    )
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_idempotent(tmp_path, db):
    rows = [
        {"CNPJ_CIA": "11.111.111/0001-11"},
        {"CNPJ_CIA": "22.222.222/0001-22"},
    ]
    csv_path = make_cad_csv(tmp_path / "cad.csv", rows)
    load_info_cad(db, csv_path)
    load_info_cad(db, csv_path)
    count = db.execute("SELECT COUNT(*) FROM cad_cia_aberta_raw").fetchone()[0]
    assert count == 2


def test_load_cadastro_has_loaded_at_column(tmp_path, db):
    csv_path = make_cad_csv(tmp_path / "cad.csv", [{"CNPJ_CIA": "11.111.111/0001-11"}])
    load_info_cad(db, csv_path)
    count = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE loaded_at IS NOT NULL"
    ).fetchone()[0]
    assert count == 1


def test_load_cadastro_preserves_cancelled_rows(tmp_path, db):
    csv_path = make_cad_csv(
        tmp_path / "cad.csv",
        [
            {"CNPJ_CIA": "11.111.111/0001-11", "SIT": "ATIVO"},
            {"CNPJ_CIA": "22.222.222/0001-22", "SIT": "CANCELADA"},
        ],
    )
    load_info_cad(db, csv_path)
    cancelled = db.execute(
        "SELECT COUNT(*) FROM cad_cia_aberta_raw WHERE SIT = 'CANCELADA'"
    ).fetchone()[0]
    assert cancelled == 1


# ── universo ──────────────────────────────────────────────────────────────────


def test_classify_raises_without_clean_tables(db):
    """Sem clean não existe universo — e sem universo não há classificação."""
    setup_classify_schema(db)
    with pytest.raises(MissingCleanTablesError, match="clean faltando"):
        classify_info_cad(db)


def test_classify_raises_with_partial_clean_tables(db):
    """Clean parcial também falha.

    As regras de assinatura citam ``bpa_clean``/``bpp_clean`` por nome, então um
    universo montado sobre um subconjunto não classificaria. E o que ele
    classificaria, se deixasse, seria pior que o erro: o CNPJ entraria sem o BPA
    que decide o perfil e cairia no ``default`` por ausência de dado.
    """
    _clean_schema(db, "bpp_clean", "dre_clean")
    with pytest.raises(MissingCleanTablesError, match=r"faltando \(bpa_clean\)"):
        classify_info_cad(db)


def test_classify_universe_is_union_of_clean_tables(db):
    """O universo é a união das clean: um CNPJ que só aparece na DRE conta."""
    _clean_schema(db)
    _insert_clean(db, "bpa_clean", CNPJ_BANCO, "1", "Ativo Total")
    _insert_clean(db, "dre_clean", CNPJ_IND, "3.01", "Receita")

    counts = classify_info_cad(db)

    assert counts["total"] == 2
    assert {r[0] for r in db.execute("SELECT cnpj_cia FROM company_classification").fetchall()} == {
        CNPJ_BANCO,
        CNPJ_IND,
    }


def test_classify_skips_cnpj_without_clean(db):
    """Cadastro sem demonstrativo não gera linha — a tabela é derivada do
    universo, e classificaria empresa que nunca reportou nada."""
    seed_classification_rows(db, [{"CNPJ_CIA": CNPJ_IND, "SIT": "ATIVO", "SETOR_ATIV": "Bancos"}])
    _clean_schema(db)
    _insert_clean(db, "bpa_clean", CNPJ_BANCO, "1", "Ativo Total")

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_IND) is None


def test_classify_classifies_cancelled_company(db):
    """SIT != 'ATIVO' não impede classificação: seis bancos do universo real
    estão com SIT cancelada e layout financeiro — perdiam tudo antes."""
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": CNPJ_BANCO, "SIT": "CANCELADA", "SETOR_ATIV": "Bancos"},
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    counts = classify_info_cad(db)

    assert counts["total"] == 1
    assert _classify_row(db, CNPJ_BANCO)[0] == "banking"


def test_classify_without_cadastro_table_raises(db):
    """Cadastro ausente interrompe: o perfil sairia certo (a assinatura é lida
    das clean), mas `denom_comerc` e `setor_ativ` ficariam NULL e todo default
    cairia em `sem_cadastro` — indicador sem nome de empresa. Melhor falhar."""
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)
    db.execute("DROP TABLE cad_cia_aberta_raw")

    with pytest.raises(MissingCadCiaAbertaTableError, match="load_info_cad"):
        classify_info_cad(db)

    assert _snapshot(db) == []


def test_classify_with_empty_cadastro_keeps_clean_descriptors(db):
    """Cadastro vazio não é cadastro ausente: classifica, e o descritor vem da
    clean (`CD_CVM`/`DENOM_CIA`). `denom_comerc` e `setor_ativ` ficam NULL porque
    só o cadastro os tem — e não são fabricados."""
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_IND)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {"default": 1}
    row = _classify_row(db, CNPJ_IND)
    assert row[1] == "default:sem_cadastro:sem_assinatura"
    assert row[3] == "00123"          # cd_cvm veio da clean
    assert row[4] == "EMPRESA TESTE"  # denom_social veio da clean
    assert row[5] is None             # denom_comerc só existe no cadastro


# ── assinatura estrutural ─────────────────────────────────────────────────────


def test_structural_signature_requires_both_signals_to_agree(db):
    """Layout financeiro exige BPA 1.01 e BPP 2.01 juntos."""
    _clean_schema(db)
    _insert_clean(db, "bpa_clean", CNPJ_BANCO, "1.01", BPA_CAIXA_FINANCEIRO)
    _insert_clean(db, "bpp_clean", CNPJ_BANCO, "2.01", BPP_PASSIVO_CIRCULANTE)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {FALLBACK_PROFILE: 1}


def test_structural_signature_requires_both_signals_to_agree_asset_side(db):
    """Só o lado do passivo não basta: BPP financeiro com BPA padrão é
    exatamente o layout híbrido que faz o sinal único errar."""
    _clean_schema(db)
    _insert_clean(db, "bpa_clean", CNPJ_BANCO, "1.01", BPA_CAIXA_PADRAO)
    _insert_clean(db, "bpp_clean", CNPJ_BANCO, "2.01", BPP_PASSIVOS_FINANCEIROS)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {FALLBACK_PROFILE: 1}


def test_structural_signature_matches_and_records_rule(db):
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {"banking": 1}
    assert _classify_row(db, CNPJ_BANCO)[1] == "structure:banking:bpa.1.01+bpp.2.01"


def test_structural_signature_ignores_sector(db):
    """Setor bancário com layout padrão é default. BRBI BR PARTNERS é o caso
    real: setor 'Bancos', demonstrativo de empresa não financeira."""
    seed_classification_rows(
        db, [{"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Bancos"}]
    )
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_BANCO)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {FALLBACK_PROFILE: 1}


def test_intermediacao_financeira_is_not_banking(db):
    """Regressão do seed antigo: 'Intermediacao Financeira' → banking colocava
    Cielo e Itaúsa (layout padrão) no perfil errado, zerando indicadores."""
    seed_classification_rows(
        db,
        [{"CNPJ_CIA": CNPJ_IND, "SIT": "ATIVO", "SETOR_ATIV": "Intermediacao Financeira"}],
    )
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_IND)

    counts = classify_info_cad(db)

    assert counts["by_profile"] == {FALLBACK_PROFILE: 1}
    assert _classify_row(db, CNPJ_IND)[1] == "default:setor:Intermediacao Financeira"


# ── setor não decide ──────────────────────────────────────────────────────────


def test_sector_alone_does_not_grant_banking(db):
    """Seguradora que reporta layout padrão é ``default``, mesmo com o setor que
    o seed antigo mandava para banking.

    O perfil existe para ler o demonstrativo, e o demonstrativo da seguradora é
    padrão. Um override setorial aqui colocaria no mapa financeiro uma empresa
    cujos rótulos não são financeiros — foi o erro que motivou a assinatura.
    """
    seed_classification_rows(
        db, [{"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Seguradoras"}]
    )
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_BANCO)

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_BANCO)[0] == FALLBACK_PROFILE


def test_sector_label_is_recorded_on_default(db):
    """O setor entra no ``rule_applied`` do default — é o que permite auditar
    *qual* empresa caiu no default e em que setor ela estava."""
    seed_classification_rows(
        db, [{"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Seguradoras"}]
    )
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_BANCO)

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_BANCO)[1] == "default:setor:Seguradoras"


def test_bank_outside_banking_sector_is_banking_by_signature(db):
    """O inverso do caso do setor: empresa com layout financeiro em setor não
    bancário é ``banking``, porque quem decide é o layout.

    Regressão do seed antigo, que só pegaria quem estivesse em "Bancos" e deixaria
    estas no perfil errado.
    """
    seed_classification_rows(
        db,
        [{"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Securitização de Recebíveis"}],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    classify_info_cad(db)

    row = _classify_row(db, CNPJ_BANCO)
    assert row[0] == "banking"
    assert row[1] == "structure:banking:bpa.1.01+bpp.2.01"


# ── campos descritivos ────────────────────────────────────────────────────────


def test_absent_cnpj_is_enriched_from_clean_without_fabricating_comerc(db):
    """Empresa fora do cadastro recebe cd_cvm/denom_social das clean, mas
    denom_comerc fica NULL: fabricar o nome comercial ensinaria o
    scripts/indicators.py a não achar ticker onde não há."""
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    classify_info_cad(db)

    row = _classify_row(db, CNPJ_BANCO)
    assert row[3] == "00123"
    assert row[4] == "EMPRESA TESTE"
    assert row[5] is None
    assert row[2] is None


def test_cadastro_descriptors_win_over_clean(db):
    seed_classification_rows(
        db,
        [
            {
                "CNPJ_CIA": CNPJ_BANCO,
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "DENOM_SOCIAL": "NOME DO CADASTRO",
                "DENOM_COMERC": "BANCO",
                "CD_CVM": "777",
            }
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    classify_info_cad(db)

    row = _classify_row(db, CNPJ_BANCO)
    assert row[3] == "777"
    assert row[4] == "NOME DO CADASTRO"
    assert row[5] == "BANCO"


def test_picks_most_recent_dt_ini_sit_for_descriptors(db):
    seed_classification_rows(
        db,
        [
            {
                "CNPJ_CIA": CNPJ_BANCO,
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "DENOM_SOCIAL": "BANCO ANTIGO",
                "CD_CVM": "100",
                "DT_INI_SIT": "2010-01-01",
            },
            {
                "CNPJ_CIA": CNPJ_BANCO,
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "DENOM_SOCIAL": "BANCO ATUAL",
                "CD_CVM": "100",
                "DT_INI_SIT": "2023-01-01",
            },
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_BANCO)[4] == "BANCO ATUAL"


def test_multi_tp_merc_same_cnpj_yields_single_row(db):
    """TP_MERC distinto por linha do cadastro (BOLSA e BALCÃO) não duplica a
    classificação: o universo é por CNPJ."""
    seed_classification_rows(
        db,
        [
            {
                "CNPJ_CIA": CNPJ_BANCO,
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "TP_MERC": "BOLSA",
                "DT_INI_SIT": "2020-01-01",
            },
            {
                "CNPJ_CIA": CNPJ_BANCO,
                "SIT": "ATIVO",
                "SETOR_ATIV": "Bancos",
                "TP_MERC": "BALCAO ORGANIZADO",
                "DT_INI_SIT": "2021-01-01",
            },
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)

    counts = classify_info_cad(db)

    assert counts["total"] == 1


def test_multi_denom_cia_in_clean_picks_most_recent(db):
    """28 CNPJs do universo mudam de DENOM_CIA entre anos; sem consolidar, a
    linha de classificação ficaria não-deterministica."""
    _clean_schema(db)
    for denom, dt_refer in (("NOME ANTIGO", "2022-12-31"), ("NOME ATUAL", "2024-12-31")):
        _insert_clean(
            db, "bpp_clean", CNPJ_IND, "2.01", BPP_PASSIVO_CIRCULANTE,
            denom=denom, dt_refer=dt_refer,
        )

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_IND)[4] == "NOME ATUAL"


# ── rule_applied ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "setor_ativ, esperado",
    [
        ("", "default:setor_vazio"),
        ("Alimentos", "default:setor:Alimentos"),
    ],
)
def test_rule_applied_for_default(db, setor_ativ, esperado):
    seed_classification_rows(
        db, [{"CNPJ_CIA": CNPJ_IND, "SIT": "ATIVO", "SETOR_ATIV": setor_ativ}]
    )
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_IND)

    classify_info_cad(db)

    assert _classify_row(db, CNPJ_IND)[1] == esperado


# ── idempotência e contagens ──────────────────────────────────────────────────


def test_classify_is_idempotent(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": CNPJ_IND, "SIT": "ATIVO", "SETOR_ATIV": "Alimentos"},
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)
    _seed_layout_padrao(db, CNPJ_IND)

    c1 = classify_info_cad(db)
    antes = _snapshot(db)
    c2 = classify_info_cad(db)

    assert c1 == c2
    assert _snapshot(db) == antes


def test_classify_rebuild_drops_stale_rows(db):
    """Reconstrução completa: CNPJ que saiu das clean precisa sumir. Um
    INSERT OR REPLACE deixaria a linha obsoluta para sempre."""
    setup_classify_schema(db)
    _clean_schema(db)
    _seed_layout_padrao(db, CNPJ_IND)
    db.execute(
        "INSERT INTO company_classification (cnpj_cia, profile_id, rule_applied, updated_at)"
        " VALUES ('99.999.999/0001-99', 'default', 'obsoleto', current_timestamp)"
    )

    counts = classify_info_cad(db)

    assert counts["total"] == 1
    assert _classify_row(db, "99.999.999/0001-99") is None


def test_classify_returns_counts_by_profile_and_rule(db):
    seed_classification_rows(
        db,
        [
            {"CNPJ_CIA": CNPJ_BANCO, "SIT": "ATIVO", "SETOR_ATIV": "Bancos"},
            {"CNPJ_CIA": CNPJ_IND, "SIT": "ATIVO", "SETOR_ATIV": ""},
        ],
    )
    _clean_schema(db)
    _seed_layout_financeiro(db, CNPJ_BANCO)
    _seed_layout_padrao(db, CNPJ_IND)

    counts = classify_info_cad(db)

    assert counts["total"] == 2
    assert counts["by_profile"] == {"default": 1, "banking": 1}
    assert counts["by_rule"]["structure:banking:bpa.1.01+bpp.2.01"] == 1
    assert counts["by_rule"]["default:setor_vazio"] == 1
