# cvmdata

Pipeline de dados CVM para cálculo de **indicadores de análise fundamentalista** de companhias abertas brasileiras.

Baixa os demonstrativos contábeis publicados na CVM (BPA, BPP, DRE), calcula indicadores por empresa/período.

### Exemplo de uso: Consulta de indicadores trimestrais da `PETROBRAS` dos últimos 5 anos.

```sh
uv run cvmdata query --cnpj "33.000.167/0001-01"
```

<details>
<summary><span style="font-size:18px;color:limegreen;">RESULTADO</span></summary>

```sh
PS > uv run cvmdata query --cnpj "33.000.167/0001-01"
            Indicadores — 33.000.167/0001-01
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ dt_refer   ┃ indicador           ┃             valor ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 2021-03-31 │ cobertura_juros     │           -1.0789 │
│ 2021-03-31 │ divida_bruta        │ 404316000000.0000 │
│ 2021-03-31 │ divida_liquida      │ 332862000000.0000 │
│ 2021-03-31 │ divida_liquida_pl   │            1.0394 │
│ 2021-03-31 │ endividamento_geral │           67.9204 │
│ 2021-03-31 │ giro_ativo          │            0.0863 │
│ 2021-03-31 │ liquidez_corrente   │            1.2370 │
│ 2021-03-31 │ liquidez_geral      │            0.3952 │
│ 2021-03-31 │ liquidez_imediata   │            0.5476 │
│ 2021-03-31 │ liquidez_seca       │            0.9178 │
│ 2021-03-31 │ margem_bruta        │           51.0978 │
│ 2021-03-31 │ margem_liquida      │            1.4807 │
│ 2021-03-31 │ margem_operacional  │           39.3437 │
│ 2021-03-31 │ roa                 │            0.1278 │
│ 2021-03-31 │ roe                 │            0.3984 │
│ 2021-06-30 │ cobertura_juros     │           -3.9567 │
│ 2021-06-30 │ divida_bruta        │ 318569000000.0000 │
│ 2021-06-30 │ divida_liquida      │ 266430000000.0000 │
│ 2021-06-30 │ divida_liquida_pl   │            0.7352 │
│ 2021-06-30 │ endividamento_geral │           61.5071 │
│ 2021-06-30 │ giro_ativo          │            0.2091 │
│ 2021-06-30 │ liquidez_corrente   │            1.3072 │
│ 2021-06-30 │ liquidez_geral      │            0.3863 │
│ 2021-06-30 │ liquidez_imediata   │            0.4238 │
│ 2021-06-30 │ liquidez_seca       │            0.9963 │
│ 2021-06-30 │ margem_bruta        │           51.3185 │
│ 2021-06-30 │ margem_liquida      │           22.5092 │
│ 2021-06-30 │ margem_operacional  │           43.7237 │
│ 2021-06-30 │ roa                 │            4.7073 │
│ 2021-06-30 │ roe                 │           12.2291 │
│ 2021-09-30 │ cobertura_juros     │           -3.1501 │
│ 2021-09-30 │ divida_bruta        │ 324124000000.0000 │
│ 2021-09-30 │ divida_liquida      │ 261810000000.0000 │
│ 2021-09-30 │ divida_liquida_pl   │            0.6969 │
│ 2021-09-30 │ endividamento_geral │           61.4555 │
│ 2021-09-30 │ giro_ativo          │            0.3267 │
│ 2021-09-30 │ liquidez_corrente   │            1.1995 │
│ 2021-09-30 │ liquidez_geral      │            0.4073 │
│ 2021-09-30 │ liquidez_imediata   │            0.4283 │
│ 2021-09-30 │ liquidez_seca       │            0.9141 │
│ 2021-09-30 │ margem_bruta        │           50.4242 │
│ 2021-09-30 │ margem_liquida      │           23.7194 │
│ 2021-09-30 │ margem_operacional  │           47.8972 │
│ 2021-09-30 │ roa                 │            7.7503 │
│ 2021-09-30 │ roe                 │           20.1073 │
│ 2021-12-31 │ cobertura_juros     │           -3.3090 │
│ 2021-12-31 │ divida_bruta        │ 327818000000.0000 │
│ 2021-12-31 │ divida_liquida      │ 265778000000.0000 │
│ 2021-12-31 │ divida_liquida_pl   │            0.6822 │
│ 2021-12-31 │ endividamento_geral │           59.9588 │
│ 2021-12-31 │ giro_ativo          │            0.4653 │
│ 2021-12-31 │ liquidez_corrente   │            1.2471 │
│ 2021-12-31 │ liquidez_geral      │            0.4255 │
│ 2021-12-31 │ liquidez_imediata   │            0.4329 │
│ 2021-12-31 │ liquidez_seca       │            0.9470 │
│ 2021-12-31 │ margem_bruta        │           48.5205 │
│ 2021-12-31 │ margem_liquida      │           23.6960 │
│ 2021-12-31 │ margem_operacional  │           46.5752 │
│ 2021-12-31 │ roa                 │           11.0246 │
│ 2021-12-31 │ roe                 │           27.5332 │
│ 2022-03-31 │ cobertura_juros     │           -7.9018 │
│ 2022-03-31 │ divida_bruta        │ 277418000000.0000 │
│ 2022-03-31 │ divida_liquida      │ 189850000000.0000 │
│ 2022-03-31 │ divida_liquida_pl   │            0.4344 │
│ 2022-03-31 │ endividamento_geral │           56.2353 │
│ 2022-03-31 │ giro_ativo          │            0.5088 │
│ 2022-03-31 │ liquidez_corrente   │            1.5321 │
│ 2022-03-31 │ liquidez_geral      │            0.5076 │
│ 2022-03-31 │ liquidez_imediata   │            0.6266 │
│ 2022-03-31 │ liquidez_seca       │            1.1608 │
│ 2022-03-31 │ margem_bruta        │           49.2723 │
│ 2022-03-31 │ margem_liquida      │           29.6714 │
│ 2022-03-31 │ margem_operacional  │           47.6891 │
│ 2022-03-31 │ roa                 │           15.0973 │
│ 2022-03-31 │ roe                 │           34.4966 │
│ 2022-06-30 │ cobertura_juros     │           -4.8453 │
│ 2022-06-30 │ divida_bruta        │ 280637000000.0000 │
│ 2022-06-30 │ divida_liquida      │ 180369000000.0000 │
│ 2022-06-30 │ divida_liquida_pl   │            0.4369 │
│ 2022-06-30 │ endividamento_geral │           58.9101 │
│ 2022-06-30 │ giro_ativo          │            0.5657 │
│ 2022-06-30 │ liquidez_corrente   │            1.3133 │
│ 2022-06-30 │ liquidez_geral      │            0.5259 │
│ 2022-06-30 │ liquidez_imediata   │            0.4984 │
│ 2022-06-30 │ liquidez_seca       │            1.0222 │
│ 2022-06-30 │ margem_bruta        │           50.8856 │
│ 2022-06-30 │ margem_liquida      │           28.5395 │
│ 2022-06-30 │ margem_operacional  │           50.4197 │
│ 2022-06-30 │ roa                 │           16.1446 │
│ 2022-06-30 │ roe                 │           39.2911 │
│ 2022-09-30 │ cobertura_juros     │           -6.8284 │
│ 2022-09-30 │ divida_bruta        │ 293403000000.0000 │
│ 2022-09-30 │ divida_liquida      │ 256715000000.0000 │
│ 2022-09-30 │ divida_liquida_pl   │            0.6862 │
│ 2022-09-30 │ endividamento_geral │           60.5197 │
│ 2022-09-30 │ giro_ativo          │            0.6510 │
│ 2022-09-30 │ liquidez_corrente   │            1.1732 │
│ 2022-09-30 │ liquidez_geral      │            0.4395 │
│ 2022-09-30 │ liquidez_imediata   │            0.1741 │
│ 2022-09-30 │ liquidez_seca       │            0.7842 │
│ 2022-09-30 │ margem_bruta        │           51.3093 │
│ 2022-09-30 │ margem_liquida      │           28.7300 │
│ 2022-09-30 │ margem_operacional  │           47.7790 │
│ 2022-09-30 │ roa                 │           18.7031 │
│ 2022-09-30 │ roe                 │           47.3733 │
│ 2022-12-31 │ cobertura_juros     │          -10.2610 │
│ 2022-12-31 │ divida_bruta        │ 280703000000.0000 │
│ 2022-12-31 │ divida_liquida      │ 224510000000.0000 │
│ 2022-12-31 │ divida_liquida_pl   │            0.6161 │
│ 2022-12-31 │ endividamento_geral │           62.6926 │
│ 2022-12-31 │ giro_ativo          │            0.6565 │
│ 2022-12-31 │ liquidez_corrente   │            0.9959 │
│ 2022-12-31 │ liquidez_geral      │            0.4471 │
│ 2022-12-31 │ liquidez_imediata   │            0.2548 │
│ 2022-12-31 │ liquidez_seca       │            0.7161 │
│ 2022-12-31 │ margem_bruta        │           52.1009 │
│ 2022-12-31 │ margem_liquida      │           29.4742 │
│ 2022-12-31 │ margem_operacional  │           45.8873 │
│ 2022-12-31 │ roa                 │           19.3512 │
│ 2022-12-31 │ roe                 │           51.8696 │
│ 2023-03-31 │ cobertura_juros     │           -8.0474 │
│ 2023-03-31 │ divida_bruta        │ 271031000000.0000 │
│ 2023-03-31 │ divida_liquida      │ 204125000000.0000 │
│ 2023-03-31 │ divida_liquida_pl   │            0.5060 │
│ 2023-03-31 │ endividamento_geral │           58.7764 │
│ 2023-03-31 │ giro_ativo          │            0.6527 │
│ 2023-03-31 │ liquidez_corrente   │            1.2238 │
│ 2023-03-31 │ liquidez_geral      │            0.4801 │
│ 2023-03-31 │ liquidez_imediata   │            0.4070 │
│ 2023-03-31 │ liquidez_seca       │            0.9086 │
│ 2023-03-31 │ margem_bruta        │           52.0830 │
│ 2023-03-31 │ margem_liquida      │           28.5790 │
│ 2023-03-31 │ margem_operacional  │           45.2578 │
│ 2023-03-31 │ roa                 │           18.6525 │
│ 2023-03-31 │ roe                 │           45.2471 │
│ 2023-06-30 │ cobertura_juros     │          -11.7707 │
│ 2023-06-30 │ divida_bruta        │ 279375000000.0000 │
│ 2023-06-30 │ divida_liquida      │ 218390000000.0000 │
│ 2023-06-30 │ divida_liquida_pl   │            0.5866 │
│ 2023-06-30 │ endividamento_geral │           62.4133 │
│ 2023-06-30 │ giro_ativo          │            0.5872 │
│ 2023-06-30 │ liquidez_corrente   │            0.9025 │
│ 2023-06-30 │ liquidez_geral      │            0.4199 │
│ 2023-06-30 │ liquidez_imediata   │            0.3290 │
│ 2023-06-30 │ liquidez_seca       │            0.6436 │
│ 2023-06-30 │ margem_bruta        │           50.6334 │
│ 2023-06-30 │ margem_liquida      │           26.9929 │
│ 2023-06-30 │ margem_operacional  │           40.3380 │
│ 2023-06-30 │ roa                 │           15.8493 │
│ 2023-06-30 │ roe                 │           42.1673 │
│ 2023-09-30 │ cobertura_juros     │           -9.4596 │
│ 2023-09-30 │ divida_bruta        │ 305451000000.0000 │
│ 2023-09-30 │ divida_liquida      │ 238304000000.0000 │
│ 2023-09-30 │ divida_liquida_pl   │            0.6150 │
│ 2023-09-30 │ endividamento_geral │           62.2144 │
│ 2023-09-30 │ giro_ativo          │            0.5230 │
│ 2023-09-30 │ liquidez_corrente   │            0.9530 │
│ 2023-09-30 │ liquidez_geral      │            0.4366 │
│ 2023-09-30 │ liquidez_imediata   │            0.3923 │
│ 2023-09-30 │ liquidez_seca       │            0.6974 │
│ 2023-09-30 │ margem_bruta        │           51.0789 │
│ 2023-09-30 │ margem_liquida      │           25.6389 │
│ 2023-09-30 │ margem_operacional  │           38.6946 │
│ 2023-09-30 │ roa                 │           13.4086 │
│ 2023-09-30 │ roe                 │           35.4861 │
│ 2023-12-31 │ cobertura_juros     │           -8.3477 │
│ 2023-12-31 │ divida_bruta        │ 303062000000.0000 │
│ 2023-12-31 │ divida_liquida      │ 227799000000.0000 │
│ 2023-12-31 │ divida_liquida_pl   │            0.5958 │
│ 2023-12-31 │ endividamento_geral │           63.6174 │
│ 2023-12-31 │ giro_ativo          │            0.4872 │
│ 2023-12-31 │ liquidez_corrente   │            0.9582 │
│ 2023-12-31 │ liquidez_geral      │            0.4290 │
│ 2023-12-31 │ liquidez_imediata   │            0.3759 │
│ 2023-12-31 │ liquidez_seca       │            0.7314 │
│ 2023-12-31 │ margem_bruta        │           52.7219 │
│ 2023-12-31 │ margem_liquida      │           24.4468 │
│ 2023-12-31 │ margem_operacional  │           36.9813 │
│ 2023-12-31 │ roa                 │           11.9105 │
│ 2023-12-31 │ roe                 │           32.7368 │
│ 2024-03-31 │ cobertura_juros     │           -5.8946 │
│ 2024-03-31 │ divida_bruta        │ 308955000000.0000 │
│ 2024-03-31 │ divida_liquida      │ 227194000000.0000 │
│ 2024-03-31 │ divida_liquida_pl   │            0.5542 │
│ 2024-03-31 │ endividamento_geral │           61.5923 │
│ 2024-03-31 │ giro_ativo          │            0.4597 │
│ 2024-03-31 │ liquidez_corrente   │            1.0786 │
│ 2024-03-31 │ liquidez_geral      │            0.4500 │
│ 2024-03-31 │ liquidez_imediata   │            0.3749 │
│ 2024-03-31 │ liquidez_seca       │            0.8131 │
│ 2024-03-31 │ margem_bruta        │           52.4456 │
│ 2024-03-31 │ margem_liquida      │           22.5557 │
│ 2024-03-31 │ margem_operacional  │           35.2946 │
│ 2024-03-31 │ roa                 │           10.3691 │
│ 2024-03-31 │ roe                 │           26.9976 │
│ 2024-06-30 │ cobertura_juros     │           -2.5175 │
│ 2024-06-30 │ divida_bruta        │ 331473000000.0000 │
│ 2024-06-30 │ divida_liquida      │ 263796000000.0000 │
│ 2024-06-30 │ divida_liquida_pl   │            0.7015 │
│ 2024-06-30 │ endividamento_geral │           64.4806 │
│ 2024-06-30 │ giro_ativo          │            0.4714 │
│ 2024-06-30 │ liquidez_corrente   │            0.8951 │
│ 2024-06-30 │ liquidez_geral      │            0.4139 │
│ 2024-06-30 │ liquidez_imediata   │            0.2463 │
│ 2024-06-30 │ liquidez_seca       │            0.6659 │
│ 2024-06-30 │ margem_bruta        │           52.2355 │
│ 2024-06-30 │ margem_liquida      │           15.8733 │
│ 2024-06-30 │ margem_operacional  │           33.0105 │
│ 2024-06-30 │ roa                 │            7.4827 │
│ 2024-06-30 │ roe                 │           21.0664 │
│ 2024-09-30 │ cobertura_juros     │           -2.8697 │
│ 2024-09-30 │ divida_bruta        │ 322157000000.0000 │
│ 2024-09-30 │ divida_liquida      │ 244319000000.0000 │
│ 2024-09-30 │ divida_liquida_pl   │            0.6184 │
│ 2024-09-30 │ endividamento_geral │           63.3480 │
│ 2024-09-30 │ giro_ativo          │            0.4674 │
│ 2024-09-30 │ liquidez_corrente   │            0.9354 │
│ 2024-09-30 │ liquidez_geral      │            0.4247 │
│ 2024-09-30 │ liquidez_imediata   │            0.2647 │
│ 2024-09-30 │ liquidez_seca       │            0.7088 │
│ 2024-09-30 │ margem_bruta        │           51.7948 │
│ 2024-09-30 │ margem_liquida      │           16.8977 │
│ 2024-09-30 │ margem_operacional  │           32.4839 │
│ 2024-09-30 │ roa                 │            7.8985 │
│ 2024-09-30 │ roe                 │           21.5500 │
│ 2024-12-31 │ cobertura_juros     │           -1.4759 │
│ 2024-12-31 │ divida_bruta        │ 373467000000.0000 │
│ 2024-12-31 │ divida_liquida      │ 326816000000.0000 │
│ 2024-12-31 │ divida_liquida_pl   │            0.8893 │
│ 2024-12-31 │ endividamento_geral │           67.3262 │
│ 2024-12-31 │ giro_ativo          │            0.4364 │
│ 2024-12-31 │ liquidez_corrente   │            0.6941 │
│ 2024-12-31 │ liquidez_geral      │            0.3471 │
│ 2024-12-31 │ liquidez_imediata   │            0.1040 │
│ 2024-12-31 │ liquidez_seca       │            0.4808 │
│ 2024-12-31 │ margem_bruta        │           50.2134 │
│ 2024-12-31 │ margem_liquida      │            7.5401 │
│ 2024-12-31 │ margem_operacional  │           27.9529 │
│ 2024-12-31 │ roa                 │            3.2903 │
│ 2024-12-31 │ roe                 │           10.0701 │
│ 2025-03-31 │ cobertura_juros     │           -1.8975 │
│ 2025-03-31 │ divida_bruta        │ 370314000000.0000 │
│ 2025-03-31 │ divida_liquida      │ 326276000000.0000 │
│ 2025-03-31 │ divida_liquida_pl   │            0.8206 │
│ 2025-03-31 │ endividamento_geral │           65.3570 │
│ 2025-03-31 │ giro_ativo          │            0.4324 │
│ 2025-03-31 │ liquidez_corrente   │            0.7183 │
│ 2025-03-31 │ liquidez_geral      │            0.3402 │
│ 2025-03-31 │ liquidez_imediata   │            0.1551 │
│ 2025-03-31 │ liquidez_seca       │            0.4722 │
│ 2025-03-31 │ margem_bruta        │           49.6663 │
│ 2025-03-31 │ margem_liquida      │            9.7793 │
│ 2025-03-31 │ margem_operacional  │           27.4486 │
│ 2025-03-31 │ roa                 │            4.2284 │
│ 2025-03-31 │ roe                 │           12.2056 │
│ 2025-06-30 │ cobertura_juros     │           -4.5463 │
│ 2025-06-30 │ divida_bruta        │ 371437000000.0000 │
│ 2025-06-30 │ divida_liquida      │ 319590000000.0000 │
│ 2025-06-30 │ divida_liquida_pl   │            0.7954 │
│ 2025-06-30 │ endividamento_geral │           65.8026 │
│ 2025-06-30 │ giro_ativo          │            0.4197 │
│ 2025-06-30 │ liquidez_corrente   │            0.7582 │
│ 2025-06-30 │ liquidez_geral      │            0.3421 │
│ 2025-06-30 │ liquidez_imediata   │            0.2131 │
│ 2025-06-30 │ liquidez_seca       │            0.5075 │
│ 2025-06-30 │ margem_bruta        │           49.0958 │
│ 2025-06-30 │ margem_liquida      │           15.7809 │
│ 2025-06-30 │ margem_operacional  │           26.9992 │
│ 2025-06-30 │ roa                 │            6.6235 │
│ 2025-06-30 │ roe                 │           19.3685 │
│ 2025-09-30 │ cobertura_juros     │           -5.0238 │
│ 2025-09-30 │ divida_bruta        │ 376083000000.0000 │
│ 2025-09-30 │ divida_liquida      │ 314082000000.0000 │
│ 2025-09-30 │ divida_liquida_pl   │            0.7391 │
│ 2025-09-30 │ endividamento_geral │           64.9383 │
│ 2025-09-30 │ giro_ativo          │            0.4055 │
│ 2025-09-30 │ liquidez_corrente   │            0.8190 │
│ 2025-09-30 │ liquidez_geral      │            0.3583 │
│ 2025-09-30 │ liquidez_imediata   │            0.2614 │
│ 2025-09-30 │ liquidez_seca       │            0.5653 │
│ 2025-09-30 │ margem_bruta        │           48.1520 │
│ 2025-09-30 │ margem_liquida      │           15.8695 │
│ 2025-09-30 │ margem_operacional  │           26.5160 │
│ 2025-09-30 │ roa                 │            6.4346 │
│ 2025-09-30 │ roe                 │           18.3523 │
│ 2025-12-31 │ cobertura_juros     │          -43.9300 │
│ 2025-12-31 │ divida_bruta        │ 384025000000.0000 │
│ 2025-12-31 │ divida_liquida      │ 333417000000.0000 │
│ 2025-12-31 │ divida_liquida_pl   │            0.7984 │
│ 2025-12-31 │ endividamento_geral │           65.8664 │
│ 2025-12-31 │ giro_ativo          │            0.4067 │
│ 2025-12-31 │ liquidez_corrente   │            0.7059 │
│ 2025-12-31 │ liquidez_geral      │            0.3498 │
│ 2025-12-31 │ liquidez_imediata   │            0.1795 │
│ 2025-12-31 │ liquidez_seca       │            0.4782 │
│ 2025-12-31 │ margem_bruta        │           47.6331 │
│ 2025-12-31 │ margem_liquida      │           22.2300 │
│ 2025-12-31 │ margem_operacional  │           29.2691 │
│ 2025-12-31 │ roa                 │            9.0409 │
│ 2025-12-31 │ roe                 │           26.4867 │
└────────────┴─────────────────────┴───────────────────┘
```

</details>



## Indicadores calculados

Fórmulas completas e mapeamento de contas CVM: [`docs/analise_fundamentalista.md`](docs/analise_fundamentalista.md).



## Instalação

```bash
git clone https://github.com/dalmofelipe/cvmdata.git
cd cvmdata
uv sync
```

Para desenvolvimento (linter + testes + cobertura):

```bash
uv sync --extra dev
```


## Pipeline

Em ambiente Linux

```bash
make all
make cadastro
```

Ou passo a passo:

```bash
make download            # baixa ZIPs CVM para data/raw/ (ITR + DFP, 2021–2025)
make load                # ingere CSVs em DuckDB (data/db/cvmdata.duckdb)
make normalize           # dedup + cast de tipos → tabelas *_clean
make indicators          # calcula 15 indicadores → tabela indicators
```

No Windows:

```bash
uv run cvmdata download
uv run cvmdata load
uv run cvmdata normalize
uv run cvmdata indicators
```

O processamento do pipeline completo, depende da configuração da maquina. Geralmente leva entre **3 a 6 min**.



## Configuração (`.env`) para personalizar o Pipeline

Copie `.env.example` e ajuste conforme necessário:

```bash
cp .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `DATA_DIR` | `data` | Diretório raiz dos dados |
| `DB_PATH` | `data/db/cvmdata.duckdb` | Caminho do arquivo DuckDB |
| `YEARS` | `2021,2022,2023,2024,2025` | Anos a baixar/processar |
| `ITR_URL` | URL CVM ITR | Base URL dos ZIPs de ITR |
| `DFP_URL` | URL CVM DFP | Base URL dos ZIPs de DFP |
