# Enhanced VTubersDemo Knowledge Graph Analysis Report
## Graph Summary
- Nodes: **59**
- Edges: **64**
- Types: music_release: 21 | vtuber: 15 | game: 9 | agency: 3 | event: 3 | Hololive's 1st fest: 1 | live event: 1 | fes: 1 | 3D swimsuit outfit debut: 1 | 1st sololive: 1 | 2nd Sololive: 1 | sololive concert: 1 | birthday party event: 1
- Connected components: **9**; giant component size: **51** (86.44% of nodes)
- Average degree: **2.17**
- Graph density: **0.0374**
- **13** communities detected
- Community sizes – mean: **4.5**, largest: **14**, smallest: **1**
- Isolates (preview): Gegege no Kitaro SNES game, Link Your Wish, Watame, Miko, Botan, Fubuki, Pekora, Marine

## Community Detection
```
Meaning
- Automatic grouping of nodes into clusters based on connectivity.

Purpose
- Reveals natural subgroups—e.g., fandom communities, content “neighborhoods,” or thematic clusters.

What can be learned
- Which entities tend to appear in similar contexts
- Which content types “bundle” together
```
- Detected **13** communities.

| community | leader | size |
|---|---|---|
| 0 | shirakami_fubuki | 14 |
| 1 | Nekomata Okayu | 10 |
| 2 | Usada Pekora | 10 |
| 3 | ookami_mio | 9 |
| 4 | Nonstop Story | 8 |
| 5 | Gegege no Kitaro SNES game | 1 |
| 6 | Link Your Wish | 1 |
| 7 | Watame | 1 |
| 8 | Miko | 1 |
| 9 | Botan | 1 |
| 10 | Fubuki | 1 |
| 11 | Pekora | 1 |

## Centrality (Top Hubs)
### Degree (Unweighted)
```
Meaning
- Measures how many direct connections a node has.

Purpose
- Identifies hubs — nodes that link to many others.

What can be learned
- Influential individuals
- Popular items or frequently referenced content
```
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.3103448275862069 |
| Usada Pekora | vtuber | 0.20689655172413793 |
| ookami_mio | vtuber | 0.1896551724137931 |
| Nekomata Okayu | vtuber | 0.1724137931034483 |
| Hololive | agency | 0.15517241379310345 |
| Nonstop Story | Hololive's 1st fest | 0.1206896551724138 |
| vtuber | vtuber | 0.10344827586206896 |
| Inugami Korone | vtuber | 0.06896551724137931 |
| Yo-kai Watch PuniPuni | game | 0.05172413793103448 |
| Shiny Smily Story | music_release | 0.05172413793103448 |
| INNK Music | agency | 0.034482758620689655 |
| Beyond the Stage | live event | 0.034482758620689655 |
| FBKBP2019 | birthday party event | 0.034482758620689655 |
| Bloom | event | 0.034482758620689655 |
| game | game | 0.017241379310344827 |
| tenkyu_suisei_wa_yoru_o_koede | music_release | 0.017241379310344827 |
| Animal Crossing | game | 0.017241379310344827 |
| ころねの最凶天災わんだふぉーわーるど | music_release | 0.017241379310344827 |
| Hololive GAMERS | agency | 0.017241379310344827 |
| もぐもぐYUMMY! | music_release | 0.017241379310344827 |

### Betweenness (Unweighted)
```
Meaning
- Measures how often a node lies on shortest paths between others.

Purpose
- Identifies “bridges” that connect different communities or knowledge areas.

What can be learned
- Which nodes act as connectors
- Importance beyond raw popularity

Example
- “Hololive agency has high betweenness” → agency connects VTubers with events and sponsors.
```
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.36721113127646704 |
| Nekomata Okayu | vtuber | 0.2211131276467029 |
| ookami_mio | vtuber | 0.21324863883847558 |
| Nonstop Story | Hololive's 1st fest | 0.17725347852389592 |
| Usada Pekora | vtuber | 0.17422867513611617 |
| Hololive | agency | 0.13974591651542653 |
| Yo-kai Watch PuniPuni | game | 0.1258318209316395 |
| Shiny Smily Story | music_release | 0.10889292196007261 |
| vtuber | vtuber | 0.05868118572292801 |
| Inugami Korone | vtuber | 0.05868118572292801 |
| INNK Music | agency | 0.0 |
| game | game | 0.0 |
| tenkyu_suisei_wa_yoru_o_koede | music_release | 0.0 |
| Animal Crossing | game | 0.0 |
| ころねの最凶天災わんだふぉーわーるど | music_release | 0.0 |
| Gegege no Kitaro SNES game | game | 0.0 |
| Beyond the Stage | live event | 0.0 |
| Link Your Wish | fes | 0.0 |
| Watame | vtuber | 0.0 |
| Miko | vtuber | 0.0 |

### Eigenvector (Unweighted)
```
Meaning
- Measures influence based on the influence of neighbors (like Google PageRank).

Purpose
- Shows nodes embedded in highly important regions of the graph.

What can be learned
- Which VTubers are connected to other high-profile nodes
- Whether centrality spreads through a network of key players
```
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.4739488190586315 |
| Hololive | agency | 0.38561846191027904 |
| Nonstop Story | Hololive's 1st fest | 0.3380443658464241 |
| ookami_mio | vtuber | 0.32735997333209094 |
| Usada Pekora | vtuber | 0.32572123913803513 |
| Shiny Smily Story | music_release | 0.16229310040499742 |
| Yo-kai Watch PuniPuni | game | 0.16199084244730003 |
| FBKBP2019 | birthday party event | 0.15798685858014602 |
| Inugami Korone | vtuber | 0.14264438328582715 |
| Beyond the Stage | live event | 0.13074151543696752 |
| Bloom | event | 0.13074151543696752 |
| vtuber | vtuber | 0.10288854628733847 |
| Fortnite Battle Royale | game | 0.08711135935450037 |
| Say!ファンファーレ! | music_release | 0.08711135935450037 |
| Shirakami Cafe Music | music_release | 0.08711135935450037 |
| #幻想郷ホロイズム (#GENSOKYOholoism) | music_release | 0.08711135935450037 |
| もっふもふ DE よいのじゃよ (Moffumoffu DE Yoi no Ja yo) | music_release | 0.08711135935450037 |
| クックパッドおすすめレシピ | music_release | 0.08711135935450037 |
| 朝が来て | music_release | 0.08711135935450037 |
| 香りのやる気スイッチ！ | music_release | 0.08711135935450037 |

### Degree (Weighted)
```
Meaning
- The same centrality measures, but incorporating confidence values.
- Confidence values are determined from user-input source reliability parameter (per source), and LLM-decided extraction confidence values (per attribute).

Purpose
- Improve accuracy of information when input data is suboptimal.
```
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.22155172413793103 |
| Usada Pekora | vtuber | 0.15172413793103445 |
| ookami_mio | vtuber | 0.14137931034482756 |
| Nekomata Okayu | vtuber | 0.13706896551724138 |
| Hololive | agency | 0.11206896551724138 |
| Nonstop Story | Hololive's 1st fest | 0.08103448275862067 |
| vtuber | vtuber | 0.0793103448275862 |
| Inugami Korone | vtuber | 0.054310344827586204 |
| Shiny Smily Story | music_release | 0.04137931034482759 |
| Yo-kai Watch PuniPuni | game | 0.03275862068965517 |
| INNK Music | agency | 0.02586206896551724 |
| FBKBP2019 | birthday party event | 0.022413793103448272 |
| Beyond the Stage | live event | 0.020689655172413793 |
| Bloom | event | 0.020689655172413793 |
| Hololive GAMERS | agency | 0.016379310344827584 |
| game | game | 0.013793103448275864 |
| tenkyu_suisei_wa_yoru_o_koede | music_release | 0.013793103448275864 |
| ころねの最凶天災わんだふぉーわーるど | music_release | 0.013793103448275864 |
| もぐもぐYUMMY! | music_release | 0.013793103448275864 |
| ぽいずにゃ～しんどろーむ | music_release | 0.013793103448275864 |

### Betweenness (Weighted)
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.3629764065335753 |
| Yo-kai Watch PuniPuni | game | 0.2250453720508167 |
| Nekomata Okayu | vtuber | 0.22020568663036905 |
| Nonstop Story | Hololive's 1st fest | 0.20931639443436179 |
| ookami_mio | vtuber | 0.19963702359346644 |
| Usada Pekora | vtuber | 0.19056261343012706 |
| Hololive | agency | 0.07622504537205083 |
| vtuber | vtuber | 0.05868118572292801 |
| Inugami Korone | vtuber | 0.05868118572292801 |
| Shiny Smily Story | music_release | 0.04355716878402904 |
| INNK Music | agency | 0.0 |
| game | game | 0.0 |
| tenkyu_suisei_wa_yoru_o_koede | music_release | 0.0 |
| Animal Crossing | game | 0.0 |
| ころねの最凶天災わんだふぉーわーるど | music_release | 0.0 |
| Gegege no Kitaro SNES game | game | 0.0 |
| Beyond the Stage | live event | 0.0 |
| Link Your Wish | fes | 0.0 |
| Watame | vtuber | 0.0 |
| Miko | vtuber | 0.0 |

### Eigenvector (Weighted)
| label | type | score |
|---|---|---|
| shirakami_fubuki | vtuber | 0.4726248399699146 |
| Hololive | agency | 0.40819836317201014 |
| ookami_mio | vtuber | 0.34958262292117437 |
| Usada Pekora | vtuber | 0.32006445228519936 |
| Nonstop Story | Hololive's 1st fest | 0.31779490620728224 |
| Shiny Smily Story | music_release | 0.1827934322154584 |
| Inugami Korone | vtuber | 0.1645583703446774 |
| FBKBP2019 | birthday party event | 0.14424714439952427 |
| Yo-kai Watch PuniPuni | game | 0.134907134539145 |
| Beyond the Stage | live event | 0.10726418732385118 |
| Bloom | event | 0.10726418732385118 |
| vtuber | vtuber | 0.09590364510077225 |
| Say!ファンファーレ! | music_release | 0.09472761699635529 |
| Shirakami Cafe Music | music_release | 0.09472761699635529 |
| #幻想郷ホロイズム (#GENSOKYOholoism) | music_release | 0.09472761699635529 |
| Nekomata Okayu | vtuber | 0.08979680714792844 |
| もっふもふ DE よいのじゃよ (Moffumoffu DE Yoi no Ja yo) | music_release | 0.08288666487181087 |
| クックパッドおすすめレシピ | music_release | 0.08288666487181087 |
| 朝が来て | music_release | 0.08288666487181087 |
| 香りのやる気スイッチ！ | music_release | 0.08288666487181087 |

## Link Prediction (Top Suggestions)
```
Meaning
- Predictions of edges that should exist but were not found in the input text.

Purpose
- Guides data collection, curation, and expansion of the graph.

What can be learned
- Potential VTuber collaborations
- Likely relationships not captured in text
- Areas where the graph is incomplete

Example
- Predicting Korone ↔ Pekora with score 0.650 suggests a strong expected link (shared content, games, history).
```
| u | type_u | v | type_v | ensemble_score |
|---|---|---|---|---|
| shirakami_fubuki | vtuber | Usada Pekora | vtuber | 0.705 |
| Nekomata Okayu | vtuber | shirakami_fubuki | vtuber | 0.626 |
| ookami_mio | vtuber | Usada Pekora | vtuber | 0.409 |
| nakiri_ayame | vtuber | hakui_koyori | vtuber | 0.409 |
| minecraft | game | nakiri_ayame | vtuber | 0.409 |
| minecraft | game | hakui_koyori | vtuber | 0.409 |
| howling | music_release | nakiri_ayame | vtuber | 0.409 |
| howling | music_release | hakui_koyori | vtuber | 0.409 |
| night_walk | music_release | nakiri_ayame | vtuber | 0.409 |
| night_walk | music_release | hakui_koyori | vtuber | 0.409 |
| bouquet | music_release | nakiri_ayame | vtuber | 0.409 |
| bouquet | music_release | hakui_koyori | vtuber | 0.409 |
| nakiri_ayame | vtuber | my_sparkle | music_release | 0.409 |
| hakui_koyori | vtuber | my_sparkle | music_release | 0.409 |
| Fortnite Battle Royale | game | Kurokami | vtuber | 0.396 |
| APEX Legends | game | Kurokami | vtuber | 0.396 |
| Phasmophobia | game | Kurokami | vtuber | 0.396 |
| Say!ファンファーレ! | music_release | Kurokami | vtuber | 0.396 |
| Shirakami Cafe Music | music_release | Kurokami | vtuber | 0.396 |
| #幻想郷ホロイズム (#GENSOKYOholoism) | music_release | Kurokami | vtuber | 0.396 |
| もっふもふ DE よいのじゃよ (Moffumoffu DE Yoi no Ja yo) | music_release | Kurokami | vtuber | 0.396 |
| クックパッドおすすめレシピ | music_release | Kurokami | vtuber | 0.396 |
| 朝が来て | music_release | Kurokami | vtuber | 0.396 |
| 香りのやる気スイッチ！ | music_release | Kurokami | vtuber | 0.396 |
| 2:23 AM | music_release | Kurokami | vtuber | 0.396 |

## Statistical Validation
```
Meaning
- Mathematical tests verifying how well the graph fits expected distributions (e.g., power law).

Purpose
- Confirms whether the graph behaves like a natural human-generated network.

What can be learned
- Whether the network resembles real social/knowledge networks
- Whether centrality correlations are strong or weak
- Whether graph structure is meaningful, not random

Example
- AIC comparison showing power-law fit → hierarchically structured VTuber ecosystems.
- Spearman: whether nodes rank similarly across different centrality metrics.
- - eg: If high-degree nodes also tend to have high betweenness → Spearman ρ is high.
```
- Degree distribution is **more consistent with a power-law** than a simple exponential (AIC comparison).
- Spearman correlation (degree vs betweenness): **r = 0.753**, p = 6.29e-12
- Spearman correlation (degree vs eigenvector): **r = 0.827**, p = 7.23e-16
- Weighted Spearman (degree vs betweenness): **r = 0.663**, p = 1.03e-08
- Weighted Spearman (degree vs eigenvector): **r = 0.675**, p = 4.47e-09

## Node Property Prediction
```
Meaning
- Predicts unknown attributes using neighbors.

Purpose
- Shows whether the graph contains enough structure to infer missing information.

What can be learned
- Whether metadata can be inferred for incomplete pages
- Which node types cluster strongly by property
- How effective future GNNs might be on the dataset

Example
- Low accuracy (~14%) → current graph is too small for strong inferences; need more data.
```
- Neighbor-majority accuracy: **0.00%** on 5 hidden nodes.

## Traversal & Shortest Paths
### BFS (depth ≤ 3) from seeds
```
Meaning: Layer-by-layer expansion from a seed node.
Purpose: Shows local neighborhoods and nearby relationships.
Learning: Which nodes are conceptually close even if not adjacent.

Example:
BFS from Fubuki reaches many music releases and events within 3 steps.
```
```text
Seed: Shirakami Fubuki
  shirakami_fubuki → ookami_mio → Hololive → Kurokami → Fortnite Battle Royale → Say!ファンファーレ! → FBKBP2019 → Shiny Smily Story → Shirakami Cafe Music → #幻想郷ホロイズム (#GENSOKYOholoism) → もっふもふ DE よいのじゃよ (Moffumoffu DE Yoi no Ja yo) → クックパッドおすすめレシピ → 朝が来て → 香りのやる気スイッチ！ → 2:23 AM → Nonstop Story → APEX Legends → Phasmophobia → Yo-kai Watch PuniPuni → nakiri_ayame

[seed missing] Hoshimachi Suisei
```

### DFS (preorder) from seeds
```
Meaning: Follows long chains of connectivity.
Purpose: Reveals narrative or sequential connections.
Learning: What long relationship chains look like in the graph.

Example:
DFS reveals long chains linking Fubuki → Mio → Suisei → Tetris → comet → AZKi.
```
```text
Seed: Shirakami Fubuki
  shirakami_fubuki → ookami_mio → Hololive → Inugami Korone → Animal Crossing → ころねの最凶天災わんだふぉーわーるど → Nonstop Story → vtuber → INNK Music → game → tenkyu_suisei_wa_yoru_o_koede → Usada Pekora → Yo-kai Watch PuniPuni → Nekomata Okayu → Hololive GAMERS → おかゆにゅ～～む！~Okayunyumu~ → もぐもぐYUMMY! → Shiny Smily Story → ぽいずにゃ～しんどろーむ → holo*27 Originals Vol.1

[seed missing] Hoshimachi Suisei
```

_No valid seed pairs or no paths found._

## Interpretation (High-Level)
- The graph is densely connected, with many entities linked through shared contextual relationships.
- The rich community structure points to multiple functional clusters within the graph (e.g., related concepts, co-occurring attributes, or entities that frequently appear together).
- The highest-scoring predicted relation is between **shirakami_fubuki** and **Usada Pekora** (vtuber–vtuber), with ensemble score ≈ **0.705**. This edge is a strong candidate for follow-up curation.

---
Generated by Module 6 (enhanced analysis).
