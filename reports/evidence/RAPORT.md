> Note (2026-11-13): annual ROC, final capital and yields above the 8% alarm threshold are NOT results — see reports/audit/FSA_2026-11-13_F1.md §(2). Hard evidence = CLV with cluster-bootstrap CI.

# Backtest finansowy Filaru 1 — commit `4599dca`

Wygenerowano: 2026-10-18T13:37:47.939431+00:00; reguła observed_at: `friday_tuesday_1800_london`; mecze: 51653; min. stawka 0.50 zł.

## ALARM — wnioski wstrzymane (plan §6, CLAUDE.md: domyślnie błąd)

- A3 (agregat): yield +9.64% > 8%
- A3 (najwyższe): yield +11.06% > 8%
- A3 (strefa pośrednia): yield +9.51% > 8%
- B365 (najwyższe): yield +9.55% > 8%
- B-BW (agregat): yield +18.77% > 8%
- B-BW (strefa pośrednia): yield +21.27% > 8%
- B-WH (agregat): yield +11.44% > 8%
- B-WH (strefa pośrednia): yield +12.49% > 8%
- C (agregat): yield +16.11% > 8%
- C (najwyższe): yield +23.08% > 8%
- C (strefa pośrednia): yield +16.13% > 8%
- C-udział-kupony (agregat): yield +16.11% > 8%
- C-udział-kupony (najwyższe): yield +23.08% > 8%
- C-udział-kupony (strefa pośrednia): yield +16.13% > 8%
- F (agregat): yield +78.48% > 8%
- F (strefa pośrednia): yield +78.48% > 8%
- B-BW@θ0.01 (agregat): yield +13.74% > 8%
- B-BW@θ0.01 (strefa pośrednia): yield +16.30% > 8%
- B-WH@θ0.01 (agregat): yield +9.21% > 8%
- B-WH@θ0.01 (strefa pośrednia): yield +10.44% > 8%
- A@θ0.03 (agregat): yield +8.89% > 8%
- A@θ0.03 (strefa pośrednia): yield +9.44% > 8%
- A3@θ0.03 (agregat): yield +11.85% > 8%
- A3@θ0.03 (najwyższe): yield +14.01% > 8%
- A3@θ0.03 (strefa pośrednia): yield +11.66% > 8%
- B-BW@θ0.03 (agregat): yield +22.25% > 8%
- B-BW@θ0.03 (strefa pośrednia): yield +24.85% > 8%
- B-WH@θ0.03 (agregat): yield +13.50% > 8%
- B-WH@θ0.03 (strefa pośrednia): yield +14.63% > 8%
- C@θ0.03 (strefa pośrednia): yield +10.64% > 8%
- A3@θ0.05 (agregat): yield +13.19% > 8%
- A3@θ0.05 (strefa pośrednia): yield +14.79% > 8%
- B-BW@θ0.05 (agregat): yield +23.71% > 8%
- B-BW@θ0.05 (strefa pośrednia): yield +28.67% > 8%
- B-WH@θ0.05 (agregat): yield +23.94% > 8%
- B-WH@θ0.05 (strefa pośrednia): yield +25.13% > 8%
- C@1000zł (agregat): yield +19.85% > 8%
- C@1000zł (strefa pośrednia): yield +23.51% > 8%
- C-bez-wyłącznika (agregat): yield +16.11% > 8%
- C-bez-wyłącznika (najwyższe): yield +23.08% > 8%
- C-bez-wyłącznika (strefa pośrednia): yield +16.13% > 8%

Werdykt i rekomendacja NIE są generowane. Szukaj przyczyny przed jakimkolwiek wnioskiem.

## Przebiegi główne (θ = 0.02, kapitał 10 000 zł)

| przebieg | kuponów | real | obrót | zysk | yield [CI 95%] | CLV [CI 95%] | okazje/100 meczów |
|---|---|---|---|---|---|---|---|
| A | 2628 | 2628 | 184845.74 | +13377.58 | +7.24% [+0.92%, +13.61%] | +0.0197 [+0.0152, +0.0242] (n=2628, kl.=261) | 5.1 |
| A3 | 3146 | 3146 | 388329.91 | +37437.61 | +9.64% [+2.56%, +16.61%] | +0.0265 [+0.0219, +0.0312] (n=3146, kl.=253) | 6.1 |
| B365 | 2461 | 2461 | 124663.78 | +4617.56 | +3.70% [-3.12%, +10.20%] | +0.0154 [+0.0104, +0.0202] (n=2461, kl.=273) | 4.8 |
| B-BW | 446 | 446 | 34964.22 | +6562.87 | +18.77% [+3.66%, +33.94%] | +0.0200 [+0.0083, +0.0309] (n=446, kl.=179) | 0.9 |
| B-WH | 1041 | 1041 | 106541.44 | +12184.49 | +11.44% [+0.76%, +22.44%] | +0.0347 [+0.0245, +0.0444] (n=1041, kl.=224) | 2.0 |
| D | 2628 | 479 | 16419.17 | -2290.28 | -13.95% [-27.10%, -2.54%] | -0.1027 [-0.1067, -0.0987] (n=2628, kl.=261) | 5.1 |
| E | 8559 | 8559 | 1498734.79 | +53239.71 | +3.55% [+0.25%, +6.88%] | +0.0321 [+0.0293, +0.0346] (n=8556, kl.=293) | 16.6 |
| C | 1424 | 1424 | 37574.00 | +6054.47 | +16.11% [-1.17%, +35.99%] | +0.0376 [+0.0287, +0.0464] (n=1424, kl.=259) | 2.8 |
| F | 10 | 10 | 640.94 | +502.98 | +78.48% [+5.45%, +186.62%] | +0.0513 [+0.0339, +0.0801] (n=10, kl.=5) | 12.5 |

## Grupy lig i rynki (przebiegi główne)

| przebieg | kuponów | real | obrót | zysk | yield [CI 95%] | CLV [CI 95%] | okazje/100 meczów |
|---|---|---|---|---|---|---|---|
| A — najwyższe | 338 | 338 | 20879.56 | +1418.37 | +6.79% [-14.40%, +30.77%] | +0.0224 [+0.0081, +0.0375] (n=338, kl.=163) | 2.7 |
| A — strefa pośrednia | 2290 | 2290 | 163966.18 | +11959.21 | +7.29% [+0.51%, +14.17%] | +0.0193 [+0.0146, +0.0239] (n=2290, kl.=254) | 5.8 |
| A — rynek 1x2 | 2427 | 2427 | 151601.75 | +9383.11 | +6.19% [-0.87%, +13.81%] | +0.0180 [+0.0133, +0.0225] (n=2427, kl.=258) | 4.7 |
| A — rynek over_under | 201 | 201 | 33243.99 | +3994.47 | +12.02% [-5.56%, +30.07%] | +0.0401 [+0.0254, +0.0576] (n=201, kl.=102) | 0.4 |
| A3 — najwyższe | 419 | 419 | 32780.26 | +3626.32 | +11.06% [-12.06%, +35.30%] | +0.0192 [+0.0033, +0.0349] (n=419, kl.=173) | 3.4 |
| A3 — strefa pośrednia | 2727 | 2727 | 355549.65 | +33811.29 | +9.51% [+2.41%, +16.93%] | +0.0276 [+0.0230, +0.0322] (n=2727, kl.=246) | 6.9 |
| A3 — rynek 1x2 | 2951 | 2951 | 337841.56 | +30264.52 | +8.96% [+1.38%, +16.36%] | +0.0255 [+0.0207, +0.0304] (n=2951, kl.=244) | 5.7 |
| A3 — rynek over_under | 195 | 195 | 50488.35 | +7173.09 | +14.21% [-3.40%, +32.08%] | +0.0424 [+0.0274, +0.0593] (n=195, kl.=101) | 0.4 |
| B365 — najwyższe | 270 | 270 | 11972.58 | +1143.85 | +9.55% [-16.43%, +35.92%] | +0.0190 [+0.0009, +0.0369] (n=270, kl.=155) | 2.2 |
| B365 — strefa pośrednia | 2191 | 2191 | 112691.20 | +3473.71 | +3.08% [-3.61%, +9.75%] | +0.0149 [+0.0100, +0.0197] (n=2191, kl.=266) | 5.6 |
| B365 — rynek 1x2 | 2260 | 2260 | 100846.46 | +1751.00 | +1.74% [-5.93%, +9.11%] | +0.0132 [+0.0080, +0.0181] (n=2260, kl.=272) | 4.4 |
| B365 — rynek over_under | 201 | 201 | 23817.32 | +2866.56 | +12.04% [-5.01%, +29.45%] | +0.0401 [+0.0254, +0.0576] (n=201, kl.=102) | 0.4 |
| B-BW — najwyższe | 94 | 94 | 4980.67 | +184.71 | +3.71% [-28.23%, +38.44%] | +0.0092 [-0.0189, +0.0332] (n=94, kl.=65) | 0.8 |
| B-BW — strefa pośrednia | 352 | 352 | 29983.55 | +6378.16 | +21.27% [+5.72%, +36.79%] | +0.0229 [+0.0097, +0.0353] (n=352, kl.=166) | 0.9 |
| B-BW — rynek 1x2 | 446 | 446 | 34964.22 | +6562.87 | +18.77% [+3.66%, +33.94%] | +0.0200 [+0.0083, +0.0309] (n=446, kl.=179) | 0.9 |
| B-WH — najwyższe | 136 | 136 | 4094.99 | -606.02 | -14.80% [-51.97%, +28.28%] | -0.0113 [-0.0422, +0.0198] (n=136, kl.=92) | 1.1 |
| B-WH — strefa pośrednia | 905 | 905 | 102446.45 | +12790.51 | +12.49% [+1.61%, +23.72%] | +0.0416 [+0.0315, +0.0519] (n=905, kl.=214) | 2.3 |
| B-WH — rynek 1x2 | 1041 | 1041 | 106541.44 | +12184.49 | +11.44% [+0.76%, +22.44%] | +0.0347 [+0.0245, +0.0444] (n=1041, kl.=224) | 2.0 |
| D — najwyższe | 338 | 48 | 970.36 | -111.79 | -11.52% [-47.50%, +21.50%] | -0.1002 [-0.1129, -0.0870] (n=338, kl.=163) | 2.7 |
| D — strefa pośrednia | 2290 | 431 | 15448.81 | -2178.49 | -14.10% [-28.05%, -1.86%] | -0.1030 [-0.1071, -0.0989] (n=2290, kl.=254) | 5.8 |
| D — rynek 1x2 | 2427 | 470 | 15722.18 | -2309.58 | -14.69% [-28.17%, -2.35%] | -0.1042 [-0.1083, -0.1002] (n=2427, kl.=258) | 4.7 |
| D — rynek over_under | 201 | 9 | 696.99 | +19.30 | +2.77% [-49.31%, +38.41%] | -0.0847 [-0.0976, -0.0693] (n=201, kl.=102) | 0.4 |
| E — najwyższe | 2570 | 2570 | 402144.20 | +5917.19 | +1.47% [-4.69%, +7.87%] | +0.0410 [+0.0357, +0.0466] (n=2570, kl.=244) | 20.9 |
| E — strefa pośrednia | 5989 | 5989 | 1096590.59 | +47322.52 | +4.32% [+0.33%, +8.16%] | +0.0282 [+0.0252, +0.0311] (n=5986, kl.=292) | 15.2 |
| E — rynek 1x2 | 7344 | 7344 | 1131137.73 | +19626.60 | +1.74% [-2.19%, +5.60%] | +0.0311 [+0.0282, +0.0339] (n=7342, kl.=293) | 14.2 |
| E — rynek over_under | 1215 | 1215 | 367597.06 | +33613.11 | +9.14% [+2.11%, +16.44%] | +0.0380 [+0.0327, +0.0432] (n=1214, kl.=268) | 2.4 |
| C — najwyższe | 80 | 80 | 2417.79 | +557.97 | +23.08% [-18.84%, +84.14%] | +0.0664 [+0.0082, +0.1208] (n=80, kl.=62) | 0.7 |
| C — strefa pośrednia | 1114 | 1114 | 30974.33 | +4995.26 | +16.13% [-2.92%, +35.93%] | +0.0360 [+0.0263, +0.0461] (n=1114, kl.=252) | 2.8 |
| C — rynek 1x2 | 1237 | 1237 | 28101.44 | +4887.53 | +17.39% [-3.51%, +39.29%] | +0.0346 [+0.0256, +0.0433] (n=1237, kl.=256) | 2.4 |
| C — rynek mieszany | 148 | 148 | 5765.81 | -29.56 | -0.51% [-41.74%, +46.12%] | +0.0453 [+0.0216, +0.0695] (n=148, kl.=84) | 0.3 |
| C — rynek over_under | 39 | 39 | 3706.75 | +1196.50 | +32.28% [-28.30%, +115.18%] | +0.1047 [+0.0363, +0.1776] (n=39, kl.=30) | 0.1 |
| F — najwyższe | 0 | 0 | 0.00 | +0.00 | n/d [n/d, n/d] | n/d [n/d, n/d] (n=0, kl.=0) | n/d |
| F — strefa pośrednia | 10 | 10 | 640.94 | +502.98 | +78.48% [+5.45%, +186.62%] | +0.0513 [+0.0339, +0.0801] (n=10, kl.=5) | 12.5 |
| F — rynek 1x2 | 10 | 10 | 640.94 | +502.98 | +78.48% [+5.45%, +186.62%] | +0.0513 [+0.0339, +0.0801] (n=10, kl.=5) | 12.5 |

## Wrażliwość (tylko raport, bez wpływu na werdykt)

| przebieg | kuponów | real | obrót | zysk | yield [CI 95%] | CLV [CI 95%] | okazje/100 meczów |
|---|---|---|---|---|---|---|---|
| C-udział-kupony | 1424 | 1424 | 37574.00 | +6054.47 | +16.11% [-1.17%, +35.99%] | +0.0376 [+0.0287, +0.0464] (n=1424, kl.=259) | 2.8 |
| A@θ0.01 | 4330 | 4330 | 221691.13 | +11035.14 | +4.98% [-0.21%, +10.12%] | +0.0137 [+0.0101, +0.0172] (n=4329, kl.=272) | 8.4 |
| A3@θ0.01 | 4926 | 4926 | 445293.22 | +29412.31 | +6.61% [+0.93%, +11.88%] | +0.0194 [+0.0159, +0.0231] (n=4925, kl.=263) | 9.5 |
| B365@θ0.01 | 3970 | 3970 | 147079.98 | +3490.25 | +2.37% [-3.29%, +7.86%] | +0.0094 [+0.0055, +0.0132] (n=3970, kl.=283) | 7.7 |
| B-BW@θ0.01 | 887 | 887 | 51515.51 | +7079.20 | +13.74% [+3.43%, +24.45%] | +0.0139 [+0.0066, +0.0215] (n=886, kl.=224) | 1.7 |
| B-WH@θ0.01 | 1494 | 1494 | 127936.72 | +11783.10 | +9.21% [-0.22%, +18.41%] | +0.0257 [+0.0176, +0.0336] (n=1494, kl.=236) | 2.9 |
| D@θ0.01 | 4330 | 524 | 15495.84 | -2556.32 | -16.50% [-31.15%, -3.35%] | -0.1080 [-0.1111, -0.1049] (n=4329, kl.=272) | 8.4 |
| E@θ0.01 | 11033 | 11033 | 1819840.83 | +54111.08 | +2.97% [+0.08%, +5.86%] | +0.0269 [+0.0247, +0.0292] (n=11030, kl.=294) | 21.4 |
| C@θ0.01 | 2148 | 633 | 8668.66 | -2268.13 | -26.16% [-46.65%, -2.54%] | +0.0280 [+0.0205, +0.0354] (n=2147, kl.=263) | 4.2 |
| A@θ0.03 | 1675 | 1675 | 138371.77 | +12299.29 | +8.89% [+0.62%, +17.14%] | +0.0252 [+0.0191, +0.0311] (n=1675, kl.=254) | 3.2 |
| A3@θ0.03 | 2096 | 2096 | 314113.09 | +37220.74 | +11.85% [+3.60%, +20.05%] | +0.0353 [+0.0290, +0.0414] (n=2096, kl.=248) | 4.1 |
| B365@θ0.03 | 1606 | 1606 | 102927.63 | +5361.93 | +5.21% [-2.96%, +13.50%] | +0.0191 [+0.0127, +0.0256] (n=1606, kl.=266) | 3.1 |
| B-BW@θ0.03 | 253 | 253 | 23401.48 | +5207.09 | +22.25% [+3.68%, +41.08%] | +0.0306 [+0.0148, +0.0458] (n=253, kl.=134) | 0.5 |
| B-WH@θ0.03 | 738 | 738 | 93012.08 | +12555.49 | +13.50% [+1.06%, +26.07%] | +0.0493 [+0.0363, +0.0618] (n=738, kl.=201) | 1.4 |
| D@θ0.03 | 1675 | 560 | 22883.45 | -2325.26 | -10.16% [-22.16%, +1.61%] | -0.0978 [-0.1032, -0.0926] (n=1675, kl.=254) | 3.2 |
| E@θ0.03 | 6318 | 6318 | 1032647.26 | +51777.23 | +5.01% [+0.91%, +9.01%] | +0.0364 [+0.0331, +0.0396] (n=6317, kl.=292) | 12.2 |
| C@θ0.03 | 881 | 881 | 23838.60 | +1349.69 | +5.66% [-15.82%, +28.26%] | +0.0477 [+0.0350, +0.0602] (n=881, kl.=248) | 1.7 |
| A@θ0.05 | 708 | 708 | 56280.99 | +2708.37 | +4.81% [-7.05%, +16.97%] | +0.0350 [+0.0240, +0.0458] (n=708, kl.=224) | 1.4 |
| A3@θ0.05 | 991 | 991 | 149262.76 | +19695.07 | +13.19% [+2.00%, +24.51%] | +0.0520 [+0.0414, +0.0629] (n=991, kl.=230) | 1.9 |
| B365@θ0.05 | 680 | 680 | 45066.45 | +79.97 | +0.18% [-12.64%, +13.44%] | +0.0246 [+0.0126, +0.0366] (n=680, kl.=229) | 1.3 |
| B-BW@θ0.05 | 120 | 120 | 14066.64 | +3334.79 | +23.71% [-1.74%, +50.36%] | +0.0466 [+0.0207, +0.0717] (n=120, kl.=77) | 0.2 |
| B-WH@θ0.05 | 429 | 429 | 68548.28 | +16409.95 | +23.94% [+7.74%, +40.82%] | +0.0670 [+0.0497, +0.0846] (n=429, kl.=166) | 0.8 |
| D@θ0.05 | 708 | 689 | 40258.26 | -2534.26 | -6.30% [-16.98%, +4.10%] | -0.0892 [-0.0989, -0.0797] (n=708, kl.=224) | 1.4 |
| E@θ0.05 | 2961 | 1889 | 231860.82 | +10523.52 | +4.54% [-3.06%, +12.12%] | +0.0467 [+0.0412, +0.0523] (n=2961, kl.=283) | 5.7 |
| C@θ0.05 | 305 | 305 | 10318.62 | -968.95 | -9.39% [-42.99%, +24.41%] | +0.0692 [+0.0453, +0.0935] (n=305, kl.=175) | 0.6 |
| A@1000zł | 2626 | 2626 | 18495.75 | +1339.47 | +7.24% [+0.93%, +13.61%] | +0.0198 [+0.0152, +0.0243] (n=2626, kl.=261) | 5.1 |
| A-bez-wyłącznika | 2628 | 2628 | 184845.74 | +13377.58 | +7.24% [+0.92%, +13.61%] | +0.0197 [+0.0152, +0.0242] (n=2628, kl.=261) | 5.1 |
| C@1000zł | 1152 | 1152 | 2679.92 | +532.08 | +19.85% [-2.87%, +44.06%] | +0.0397 [+0.0297, +0.0497] (n=1152, kl.=249) | 2.2 |
| C-bez-wyłącznika | 1424 | 1424 | 37574.00 | +6054.47 | +16.11% [-1.17%, +35.99%] | +0.0376 [+0.0287, +0.0464] (n=1424, kl.=259) | 2.8 |

## Tabela per liga — A i C (hipoteza wyboru lig do Filaru 2, bez korekty na wielokrotne porównania)

| przebieg | liga | kuponów | CLV [CI 95%] | yield | kuponów / tydzień sezonu | rankingowana (≥ 300 A) |
|---|---|---|---|---|---|---|
| A | B1 | 119 | -0.0070 [-0.0239, +0.0108] | -5.77% | 0.49 | nie |
| A | D1 | 77 | +0.0380 [+0.0136, +0.0629] | -37.34% | 0.34 | nie |
| A | D2 | 80 | +0.0158 [-0.0070, +0.0398] | -3.78% | 0.33 | nie |
| A | E0 | 52 | +0.0347 [+0.0045, +0.0617] | +40.38% | 0.21 | nie |
| A | E1 | 92 | +0.0246 [+0.0035, +0.0463] | +3.86% | 0.38 | nie |
| A | E2 | 165 | +0.0237 [+0.0097, +0.0385] | -1.00% | 0.63 | nie |
| A | E3 | 204 | +0.0201 [+0.0060, +0.0345] | +1.20% | 0.78 | nie |
| A | EC | 226 | +0.0226 [+0.0072, +0.0401] | +17.93% | 0.90 | nie |
| A | F1 | 87 | +0.0158 [-0.0159, +0.0485] | +3.26% | 0.37 | nie |
| A | F2 | 165 | +0.0167 [+0.0040, +0.0298] | -1.23% | 0.67 | nie |
| A | G1 | 226 | +0.0160 [-0.0020, +0.0338] | +18.18% | 0.96 | nie |
| A | I1 | 49 | +0.0438 [+0.0069, +0.0779] | +31.02% | 0.20 | nie |
| A | I2 | 129 | +0.0226 [+0.0097, +0.0356] | +29.63% | 0.56 | nie |
| A | N1 | 136 | +0.0131 [-0.0075, +0.0346] | +0.87% | 0.60 | nie |
| A | P1 | 90 | +0.0149 [-0.0117, +0.0422] | -6.91% | 0.37 | nie |
| A | SC0 | 66 | +0.0072 [-0.0183, +0.0334] | -9.55% | 0.28 | nie |
| A | SC1 | 61 | +0.0258 [+0.0006, +0.0518] | -11.83% | 0.26 | nie |
| A | SC2 | 99 | +0.0180 [-0.0077, +0.0419] | +7.28% | 0.42 | nie |
| A | SC3 | 115 | +0.0500 [+0.0292, +0.0712] | +1.46% | 0.49 | nie |
| A | SP1 | 73 | -0.0091 [-0.0364, +0.0178] | +33.28% | 0.30 | nie |
| A | SP2 | 215 | +0.0116 [-0.0005, +0.0239] | +0.05% | 0.77 | nie |
| A | T1 | 102 | +0.0382 [+0.0091, +0.0650] | +38.77% | 0.41 | nie |
| C | B1 | 9 | -0.0267 [-0.1295, +0.0918] | +97.31% | 0.04 | — |
| C | D1 | 11 | +0.1494 [+0.0403, +0.2767] | -65.21% | 0.05 | — |
| C | D2 | 7 | -0.0159 [-0.0499, +0.0207] | -100.00% | 0.03 | — |
| C | E0 | 8 | -0.0149 [-0.0833, +0.0827] | +37.77% | 0.03 | — |
| C | E1 | 16 | +0.0362 [-0.0055, +0.0836] | -89.24% | 0.07 | — |
| C | E2 | 30 | +0.0595 [+0.0217, +0.0991] | +100.51% | 0.12 | — |
| C | E3 | 35 | +0.0388 [-0.0077, +0.0913] | +17.69% | 0.13 | — |
| C | EC | 43 | +0.0131 [-0.0320, +0.0586] | +69.78% | 0.17 | — |
| C | F1 | 10 | +0.0545 [-0.0689, +0.2174] | -14.56% | 0.04 | — |
| C | F2 | 22 | +0.0512 [+0.0106, +0.0989] | +78.45% | 0.09 | — |
| C | G1 | 23 | +0.0336 [-0.0236, +0.0948] | +6.81% | 0.10 | — |
| C | I1 | 13 | +0.0869 [+0.0075, +0.1654] | +146.85% | 0.05 | — |
| C | I2 | 16 | +0.0330 [-0.0350, +0.0911] | -44.89% | 0.07 | — |
| C | N1 | 11 | -0.0133 [-0.0899, +0.0603] | -41.68% | 0.05 | — |
| C | P1 | 7 | +0.1000 [-0.0289, +0.2308] | +179.89% | 0.03 | — |
| C | SC0 | 9 | -0.0191 [-0.0774, +0.0487] | -55.91% | 0.04 | — |
| C | SC1 | 5 | -0.0906 [-0.1368, -0.0485] | -100.00% | 0.02 | — |
| C | SC2 | 3 | +0.0389 [n/d, n/d] | -100.00% | 0.01 | — |
| C | SC3 | 15 | +0.1098 [+0.0551, +0.1678] | +17.44% | 0.06 | — |
| C | SP1 | 12 | -0.0397 [-0.1140, +0.0395] | +23.33% | 0.05 | — |
| C | SP2 | 28 | +0.0233 [-0.0198, +0.0690] | +29.49% | 0.10 | — |
| C | T1 | 15 | +0.0526 [-0.0191, +0.1309] | +118.46% | 0.06 | — |

## Kapitał, wyłącznik, podatek, liczniki

- **A**: kapitał końcowy 23377.58 zł (start 10000); ROC roczny +14.02%; maks. obsunięcie 17.6%; najdłużej pod kreską 675 dni; bootstrap kapitału końcowego {'p05': 13547.705999999998, 'p50': 23347.924999999996, 'p95': 33200.0115}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 2628}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka < min. stawki (T12)': 2, 'stawka 0': 22}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2628}; kuponów mieszanych grup 0
- **A3**: kapitał końcowy 47437.61 zł (start 10000); ROC roczny +27.20%; maks. obsunięcie 15.5%; najdłużej pod kreską 634 dni; bootstrap kapitału końcowego {'p05': 25196.905000000002, 'p50': 47403.17, 'p95': 69288.91949999997}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 3146}; G-K od kuponu 161; pominięte {'stawka 0': 78, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 8073; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 3146}; kuponów mieszanych grup 0
- **B365**: kapitał końcowy 14617.56 zł (start 10000); ROC roczny +6.04%; maks. obsunięcie 18.2%; najdłużej pod kreską 743 dni; bootstrap kapitału końcowego {'p05': 7700.239999999999, 'p50': 14438.244999999997, 'p95': 21673.52399999999}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 2461}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 21}; wyłączone (brak kompletu) 130; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2461}; kuponów mieszanych grup 0
- **B-BW**: kapitał końcowy 16562.87 zł (start 10000); ROC roczny +8.17%; maks. obsunięcie 9.2%; najdłużej pod kreską 723 dni; bootstrap kapitału końcowego {'p05': 11990.5565, 'p50': 16496.225, 'p95': 20945.639}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 446}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3532; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 446}; kuponów mieszanych grup 0
- **B-WH**: kapitał końcowy 22184.49 zł (start 10000); ROC roczny +15.16%; maks. obsunięcie 16.6%; najdłużej pod kreską 518 dni; bootstrap kapitału końcowego {'p05': 12207.169500000002, 'p50': 22078.640000000003, 'p95': 32247.378499999995}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 1041}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 8}; wyłączone (brak kompletu) 6121; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 1041}; kuponów mieszanych grup 0
- **D**: kapitał końcowy 7709.72 zł (start 10000); ROC roczny -3.94%; maks. obsunięcie 25.8%; najdłużej pod kreską 2341 dni; bootstrap kapitału końcowego {'p05': 6020.3595000000005, 'p50': 7723.38, 'p95': 9277.753999999999}; wyłącznik: pierwszy kupon PAPER 2020-01-31 18:01:00+00:00, kuponów paper 2149, ich hipotetyczny P&L -2466.24 zł; podatek {'single 0.88': 2628}; G-K od kuponu None; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka < min. stawki (T12)': 2, 'stawka 0': 22}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2628}; kuponów mieszanych grup 0
- **E**: kapitał końcowy 63239.71 zł (start 10000); ROC roczny +32.97%; maks. obsunięcie 26.4%; najdłużej pod kreską 277 dni; bootstrap kapitału końcowego {'p05': 21732.078000000012, 'p50': 62913.49999999999, 'p95': 104691.60649999997}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 8559}; G-K od kuponu 223; pominięte {'stawka 0': 5818, 'stawka < min. stawki (T12)': 65, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 0; odrzucone A4a-01 {'E0 / 2324 / b: EV > 0.50 względem Pinnacle': 1, 'G1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2526 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 8559}; kuponów mieszanych grup 0
- **C**: kapitał końcowy 16054.47 zł (start 10000); ROC roczny +7.59%; maks. obsunięcie 19.4%; najdłużej pod kreską 936 dni; bootstrap kapitału końcowego {'p05': 10135.173999999999, 'p50': 15935.35, 'p95': 22239.2435}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 1212, 'single 1.00': 212}; G-K od kuponu 151; pominięte {'stawka 0': 15, 'kupon poza progiem po podatku': 1, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1424}; kuponów mieszanych grup 230
- **C-udział-kupony**: kapitał końcowy 16054.47 zł (start 10000); ROC roczny +7.59%; maks. obsunięcie 19.4%; najdłużej pod kreską 936 dni; bootstrap kapitału końcowego {'p05': 10135.173999999999, 'p50': 15935.35, 'p95': 22239.2435}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 1212, 'single 1.00': 212}; G-K od kuponu 151; pominięte {'stawka 0': 15, 'kupon poza progiem po podatku': 1, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1424}; kuponów mieszanych grup 230
- **F**: kapitał końcowy 10502.98 zł (start 10000); ROC roczny +31.79%; maks. obsunięcie 1.4%; najdłużej pod kreską 35 dni; bootstrap kapitału końcowego {'p05': 10095.58, 'p50': 10502.98, 'p95': 10963.47}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 10}; G-K od kuponu None; pominięte {}; wyłączone (brak kompletu) 0; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 10}; kuponów mieszanych grup 0
- **A@θ0.01**: kapitał końcowy 21035.14 zł (start 10000); ROC roczny +12.18%; maks. obsunięcie 20.3%; najdłużej pod kreską 675 dni; bootstrap kapitału końcowego {'p05': 11568.5315, 'p50': 21083.665, 'p95': 30342.888499999997}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 4330}; G-K od kuponu 220; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka < min. stawki (T12)': 7, 'stawka 0': 57}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 4330}; kuponów mieszanych grup 0
- **A3@θ0.01**: kapitał końcowy 39412.31 zł (start 10000); ROC roczny +23.61%; maks. obsunięcie 17.0%; najdłużej pod kreską 634 dni; bootstrap kapitału końcowego {'p05': 19185.5035, 'p50': 39141.994999999995, 'p95': 60581.37249999998}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 4926}; G-K od kuponu 235; pominięte {'stawka 0': 228, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 8073; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 4926}; kuponów mieszanych grup 0
- **B365@θ0.01**: kapitał końcowy 13490.25 zł (start 10000); ROC roczny +4.74%; maks. obsunięcie 23.4%; najdłużej pod kreską 818 dni; bootstrap kapitału końcowego {'p05': 6635.9155, 'p50': 13308.629999999997, 'p95': 20328.995}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 3970}; G-K od kuponu 206; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 27}; wyłączone (brak kompletu) 130; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 3970}; kuponów mieszanych grup 0
- **B-BW@θ0.01**: kapitał końcowy 17079.20 zł (start 10000); ROC roczny +8.62%; maks. obsunięcie 10.5%; najdłużej pod kreską 753 dni; bootstrap kapitału końcowego {'p05': 12446.598, 'p50': 16982.53, 'p95': 21791.681499999995}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 887}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3532; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 887}; kuponów mieszanych grup 0
- **B-WH@θ0.01**: kapitał końcowy 21783.10 zł (start 10000); ROC roczny +14.79%; maks. obsunięcie 16.7%; najdłużej pod kreską 518 dni; bootstrap kapitału końcowego {'p05': 11861.510999999999, 'p50': 21653.66, 'p95': 32472.934}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 1494}; G-K od kuponu 230; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 17}; wyłączone (brak kompletu) 6121; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 1494}; kuponów mieszanych grup 0
- **D@θ0.01**: kapitał końcowy 7443.68 zł (start 10000); ROC roczny -4.46%; maks. obsunięcie 27.9%; najdłużej pod kreską 2341 dni; bootstrap kapitału końcowego {'p05': 5581.7645, 'p50': 7475.1, 'p95': 9196.206500000002}; wyłącznik: pierwszy kupon PAPER 2019-12-03 18:01:00+00:00, kuponów paper 3806, ich hipotetyczny P&L -6048.85 zł; podatek {'single 0.88': 4330}; G-K od kuponu None; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka < min. stawki (T12)': 7, 'stawka 0': 57}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 4330}; kuponów mieszanych grup 0
- **E@θ0.01**: kapitał końcowy 64111.08 zł (start 10000); ROC roczny +33.25%; maks. obsunięcie 25.5%; najdłużej pod kreską 638 dni; bootstrap kapitału końcowego {'p05': 19097.797500000004, 'p50': 64024.970000000016, 'p95': 109665.76149999996}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 11033}; G-K od kuponu 267; pominięte {'stawka 0': 15020, 'stawka < min. stawki (T12)': 171, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 0; odrzucone A4a-01 {'E0 / 2324 / b: EV > 0.50 względem Pinnacle': 1, 'G1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2526 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 11033}; kuponów mieszanych grup 0
- **C@θ0.01**: kapitał końcowy 7731.87 zł (start 10000); ROC roczny -3.90%; maks. obsunięcie 25.7%; najdłużej pod kreską 2348 dni; bootstrap kapitału końcowego {'p05': 6210.1655, 'p50': 7683.67, 'p95': 9343.0955}; wyłącznik: pierwszy kupon PAPER 2020-12-01 18:01:00+00:00, kuponów paper 1515, ich hipotetyczny P&L +5060.37 zł; podatek {'multi 1.00': 2068, 'single 0.94': 3, 'single 1.00': 77}; G-K od kuponu 151; pominięte {'stawka 0': 176, 'kupon poza progiem po podatku': 2, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2148}; kuponów mieszanych grup 453
- **A@θ0.03**: kapitał końcowy 22299.29 zł (start 10000); ROC roczny +13.20%; maks. obsunięcie 15.9%; najdłużej pod kreską 781 dni; bootstrap kapitału końcowego {'p05': 12860.2855, 'p50': 22328.125, 'p95': 31466.8005}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 1675}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 14}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1675}; kuponów mieszanych grup 0
- **A3@θ0.03**: kapitał końcowy 47220.74 zł (start 10000); ROC roczny +27.11%; maks. obsunięcie 15.8%; najdłużej pod kreską 668 dni; bootstrap kapitału końcowego {'p05': 24920.147500000003, 'p50': 46605.80500000001, 'p95': 68957.129}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 2096}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 35}; wyłączone (brak kompletu) 8073; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 2096}; kuponów mieszanych grup 0
- **B365@θ0.03**: kapitał końcowy 15361.93 zł (start 10000); ROC roczny +6.86%; maks. obsunięcie 16.8%; najdłużej pod kreską 633 dni; bootstrap kapitału końcowego {'p05': 8355.501, 'p50': 15400.73, 'p95': 22532.230499999994}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 1606}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 14}; wyłączone (brak kompletu) 130; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1606}; kuponów mieszanych grup 0
- **B-BW@θ0.03**: kapitał końcowy 15207.09 zł (start 10000); ROC roczny +6.74%; maks. obsunięcie 7.6%; najdłużej pod kreską 583 dni; bootstrap kapitału końcowego {'p05': 11465.687, 'p50': 15251.16, 'p95': 18838.9845}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 253}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3532; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 253}; kuponów mieszanych grup 0
- **B-WH@θ0.03**: kapitał końcowy 22555.49 zł (start 10000); ROC roczny +15.51%; maks. obsunięcie 14.7%; najdłużej pod kreską 518 dni; bootstrap kapitału końcowego {'p05': 12561.325499999999, 'p50': 22599.394999999997, 'p95': 32613.363499999996}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 738}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 7}; wyłączone (brak kompletu) 6121; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 738}; kuponów mieszanych grup 0
- **D@θ0.03**: kapitał końcowy 7674.74 zł (start 10000); ROC roczny -4.01%; maks. obsunięcie 26.2%; najdłużej pod kreską 2328 dni; bootstrap kapitału końcowego {'p05': 5254.032499999999, 'p50': 7669.21, 'p95': 10020.984}; wyłącznik: pierwszy kupon PAPER 2021-01-26 18:01:00+00:00, kuponów paper 1115, ich hipotetyczny P&L -188.79 zł; podatek {'single 0.88': 1675}; G-K od kuponu None; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 14}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1675}; kuponów mieszanych grup 0
- **E@θ0.03**: kapitał końcowy 61777.23 zł (start 10000); ROC roczny +32.49%; maks. obsunięcie 23.1%; najdłużej pod kreską 278 dni; bootstrap kapitału końcowego {'p05': 26895.35549999998, 'p50': 61899.075, 'p95': 98081.95799999993}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 6318}; G-K od kuponu 182; pominięte {'stawka 0': 1877, 'stawka < min. stawki (T12)': 23, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 0; odrzucone A4a-01 {'E0 / 2324 / b: EV > 0.50 względem Pinnacle': 1, 'G1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2526 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 6318}; kuponów mieszanych grup 0
- **C@θ0.03**: kapitał końcowy 11349.69 zł (start 10000); ROC roczny +1.98%; maks. obsunięcie 21.4%; najdłużej pod kreską 994 dni; bootstrap kapitału końcowego {'p05': 7283.525, 'p50': 11346.85, 'p95': 15641.735999999999}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 730, 'single 0.94': 2, 'single 1.00': 149}; G-K od kuponu 151; pominięte {'stawka 0': 73, 'kupon poza progiem po podatku': 5, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 881}; kuponów mieszanych grup 126
- **A@θ0.05**: kapitał końcowy 12708.37 zł (start 10000); ROC roczny +3.79%; maks. obsunięcie 19.1%; najdłużej pod kreską 772 dni; bootstrap kapitału końcowego {'p05': 6890.095, 'p50': 12796.145, 'p95': 18525.146499999995}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 708}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 6}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 708}; kuponów mieszanych grup 0
- **A3@θ0.05**: kapitał końcowy 29695.07 zł (start 10000); ROC roczny +19.03%; maks. obsunięcie 18.7%; najdłużej pod kreską 558 dni; bootstrap kapitału końcowego {'p05': 15201.785000000005, 'p50': 29713.954999999998, 'p95': 44307.772000000004}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 991}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 8}; wyłączone (brak kompletu) 8073; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 991}; kuponów mieszanych grup 0
- **B365@θ0.05**: kapitał końcowy 10079.97 zł (start 10000); ROC roczny +0.12%; maks. obsunięcie 23.3%; najdłużej pod kreską 1017 dni; bootstrap kapitału końcowego {'p05': 5208.407500000001, 'p50': 10050.335, 'p95': 14937.536999999998}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 680}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 8}; wyłączone (brak kompletu) 130; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 680}; kuponów mieszanych grup 0
- **B-BW@θ0.05**: kapitał końcowy 13334.79 zł (start 10000); ROC roczny +4.59%; maks. obsunięcie 6.5%; najdłużej pod kreską 532 dni; bootstrap kapitału końcowego {'p05': 10423.631, 'p50': 13349.64, 'p95': 16449.8655}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 120}; G-K od kuponu None; pominięte {'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3532; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 120}; kuponów mieszanych grup 0
- **B-WH@θ0.05**: kapitał końcowy 26409.95 zł (start 10000); ROC roczny +18.80%; maks. obsunięcie 12.1%; najdłużej pod kreską 427 dni; bootstrap kapitału końcowego {'p05': 16766.3465, 'p50': 26387.754999999997, 'p95': 36380.653999999995}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 429}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 3}; wyłączone (brak kompletu) 6121; odrzucone A4a-01 {'F1 / 2021 / b: EV > 0.50 względem Pinnacle': 1, 'SP2 / 2122 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 429}; kuponów mieszanych grup 0
- **D@θ0.05**: kapitał końcowy 7465.74 zł (start 10000); ROC roczny -4.43%; maks. obsunięcie 25.3%; najdłużej pod kreską 2354 dni; bootstrap kapitału końcowego {'p05': 3890.6790000000015, 'p50': 7468.9400000000005, 'p95': 11184.9345}; wyłącznik: pierwszy kupon PAPER 2025-10-17 17:01:00+00:00, kuponów paper 19, ich hipotetyczny P&L -410.87 zł; podatek {'single 0.88': 708}; G-K od kuponu None; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka 0': 6}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 708}; kuponów mieszanych grup 0
- **E@θ0.05**: kapitał końcowy 20523.52 zł (start 10000); ROC roczny +11.75%; maks. obsunięcie 25.5%; najdłużej pod kreską 1345 dni; bootstrap kapitału końcowego {'p05': 4977.247000000003, 'p50': 20243.085000000003, 'p95': 36574.2705}; wyłącznik: pierwszy kupon PAPER 2022-12-30 18:01:00+00:00, kuponów paper 1072, ich hipotetyczny P&L +14099.17 zł; podatek {'single 1.00': 2961}; G-K od kuponu 151; pominięte {'stawka 0': 75, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 0; odrzucone A4a-01 {'E0 / 2324 / b: EV > 0.50 względem Pinnacle': 1, 'G1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2223 / b: EV > 0.50 względem Pinnacle': 1, 'I1 / 2526 / b: EV > 0.50 względem Pinnacle': 1}; reconcile {'ok': True, 'n': 2961}; kuponów mieszanych grup 0
- **C@θ0.05**: kapitał końcowy 9031.05 zł (start 10000); ROC roczny -1.57%; maks. obsunięcie 18.1%; najdłużej pod kreską 1351 dni; bootstrap kapitału końcowego {'p05': 6305.124, 'p50': 8900.675, 'p95': 12130.327999999998}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 267, 'single 0.94': 14, 'single 1.00': 24}; G-K od kuponu 151; pominięte {'kupon poza progiem po podatku': 56, 'stawka 0': 86, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 305}; kuponów mieszanych grup 47
- **A@1000zł**: kapitał końcowy 2339.47 zł (start 1000); ROC roczny +14.04%; maks. obsunięcie 17.6%; najdłużej pod kreską 675 dni; bootstrap kapitału końcowego {'p05': 1356.0085000000001, 'p50': 2336.95, 'p95': 3322.544499999999}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 2626}; G-K od kuponu 151; pominięte {'stawka < min. stawki (T12)': 4, 'mecz bez notowania Pinnacle': 3588, 'stawka 0': 22}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2626}; kuponów mieszanych grup 0
- **A-bez-wyłącznika**: kapitał końcowy 23377.58 zł (start 10000); ROC roczny +14.02%; maks. obsunięcie 17.6%; najdłużej pod kreską 675 dni; bootstrap kapitału końcowego {'p05': 13547.705999999998, 'p50': 23347.924999999996, 'p95': 33200.0115}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'single 1.00': 2628}; G-K od kuponu 151; pominięte {'mecz bez notowania Pinnacle': 3588, 'stawka < min. stawki (T12)': 2, 'stawka 0': 22}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 2628}; kuponów mieszanych grup 0
- **C@1000zł**: kapitał końcowy 1532.08 zł (start 1000); ROC roczny +6.82%; maks. obsunięcie 23.7%; najdłużej pod kreską 942 dni; bootstrap kapitału końcowego {'p05': 1014.9979999999999, 'p50': 1523.545, 'p95': 2093.104}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 1147, 'single 0.94': 5}; G-K od kuponu 151; pominięte {'stawka 0': 222, 'stawka < min. stawki (T12)': 65, 'mecz bez notowania Pinnacle': 3588, 'kupon poza progiem po podatku': 1}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1152}; kuponów mieszanych grup 204
- **C-bez-wyłącznika**: kapitał końcowy 16054.47 zł (start 10000); ROC roczny +7.59%; maks. obsunięcie 19.4%; najdłużej pod kreską 936 dni; bootstrap kapitału końcowego {'p05': 10135.173999999999, 'p50': 15935.35, 'p95': 22239.2435}; wyłącznik: pierwszy kupon PAPER None, kuponów paper 0, ich hipotetyczny P&L +0.00 zł; podatek {'multi 1.00': 1212, 'single 1.00': 212}; G-K od kuponu 151; pominięte {'stawka 0': 15, 'kupon poza progiem po podatku': 1, 'mecz bez notowania Pinnacle': 3588}; wyłączone (brak kompletu) 3645; odrzucone A4a-01 {}; reconcile {'ok': True, 'n': 1424}; kuponów mieszanych grup 230

Każda liczba z n i CI (reguła 11); CI yieldu i CLV — bootstrap klastrowy po tygodniach ISO.
PNG: pominięte — brak matplotlib (uv sync --extra viz).
