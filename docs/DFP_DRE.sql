SELECT CNPJ_CIA, DENOM_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA
FROM read_csv(
    '~/Documentos/cvmdata/files/dfp_cia_aberta_DRE_con_20*.csv', 
    delim=';', 
    encoding='latin-1',
    header=true,
    union_by_name = true,
    filename = true
)
WHERE lower(strip_accents(trim(DS_CONTA))) = 'resultado antes dos tributos sobre o lucro'
-- Contas retornadas: 3.05 Banking; 3.07 Default; 3.09 Seguradoras;
--WHERE lower(strip_accents(trim(DS_CONTA))) = 'imposto de renda e contribuicao social sobre o lucro'
-- Contas retornadas: 3.06 Banking; 3.08 Default; 3.10 Seguradoras;
--WHERE lower(strip_accents(trim(DS_CONTA))) = 'resultado liquido das operacoes continuadas'
-- Contas retornadas: 3.07 Banking / 3.09 Default / 3.10 Seguradoras
--WHERE lower(strip_accents(trim(DS_CONTA))) = 'lucro/prejuizo liquido das operacoes descontinuadas'
-- Contas retornadas: 3.08.01 Banking / 3.10.01 Default / 3.12.01 Seguradoras
--WHERE lower(strip_accents(trim(DS_CONTA))) = 'resultado liquido de operacoes descontinuadas'
-- Contas retornadas: 3.10 Default / 3.12 Seguradoras | Banking sem registros
--WHERE lower(strip_accents(trim(DS_CONTA))) = 'resultado liquido das operacoes descontinuadas'
-- Contas retornadas: 3.08 Banking / 3.10.01.01 OUTLIER | Default sem registros
ORDER BY DT_REFER;