# Enhanced pokemon Knowledge Graph Analysis Report
## Executive Summary
- **49** nodes and **47** edges
- **10** connected components (giant component: 14 nodes, 28.6% of all nodes)
- **11** communities detected
- Average degree: **1.92**; density: **0.0400**
- Community sizes – mean: **4.5**, largest: **14**, smallest: **1**

## Graph Summary
- Nodes: **49**
- Edges: **47**
- Types: pokemon: 21 | type: 9 | ability: 8 | item: 5 | move: 2 | region: 1
- Connected components: **10**; giant component size: **14** (28.57% of nodes)
- Average degree: **1.92**
- Graph density: **0.0400**
- Isolates (preview): Water Stone, Thunder Stone, Fire Stone, Fairy, Moss Rock, Ice Rock

## Community Detection
- Detected **11** communities.

| community | leader | size |
|---|---|---|
| 0 | Dragonite | 7 |
| 1 | Eevee | 14 |
| 2 | Water Stone | 1 |
| 3 | Thunder Stone | 1 |
| 4 | Fire Stone | 1 |
| 5 | Fairy | 1 |
| 6 | Moss Rock | 1 |
| 7 | Ice Rock | 1 |
| 8 | Gengar | 6 |
| 9 | Lucario | 6 |
| 10 | Pikachu | 10 |

## Centrality (Top Hubs)
### Degree (Unweighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.25 |
| Normal | type | 0.1875 |
| Pikachu | pokemon | 0.16666666666666666 |
| Lucario | pokemon | 0.125 |
| Dragonite | pokemon | 0.10416666666666667 |
| Gengar | pokemon | 0.08333333333333333 |
| Sylveon | pokemon | 0.0625 |
| Dragonair | pokemon | 0.041666666666666664 |
| Inner Focus | ability | 0.041666666666666664 |
| Vaporeon | pokemon | 0.041666666666666664 |
| Jolteon | pokemon | 0.041666666666666664 |
| Flareon | pokemon | 0.041666666666666664 |
| Espeon | pokemon | 0.041666666666666664 |
| Umbreon | pokemon | 0.041666666666666664 |
| Leafeon | pokemon | 0.041666666666666664 |
| Glaceon | pokemon | 0.041666666666666664 |
| Haunter | pokemon | 0.041666666666666664 |
| Alolan Raichu | pokemon | 0.041666666666666664 |
| Dratini | pokemon | 0.020833333333333332 |
| Dragon | type | 0.020833333333333332 |

### Betweenness (Unweighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.04476950354609929 |
| Lucario | pokemon | 0.0398936170212766 |
| Dragonite | pokemon | 0.03900709219858156 |
| Inner Focus | ability | 0.031914893617021274 |
| Pikachu | pokemon | 0.03102836879432624 |
| Normal | type | 0.01551418439716312 |
| Sylveon | pokemon | 0.010638297872340425 |
| Dragonair | pokemon | 0.00975177304964539 |
| Gengar | pokemon | 0.007978723404255319 |
| Alolan Raichu | pokemon | 0.0070921985815602835 |
| Haunter | pokemon | 0.0035460992907801418 |
| Dratini | pokemon | 0.0 |
| Dragon | type | 0.0 |
| Flying | type | 0.0 |
| Multiscale | ability | 0.0 |
| Run Away | ability | 0.0 |
| Adaptability | ability | 0.0 |
| Anticipation | ability | 0.0 |
| Water Stone | item | 0.0 |
| Thunder Stone | item | 0.0 |

### Eigenvector (Unweighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.5570832703328176 |
| Normal | type | 0.4955274991276959 |
| Sylveon | pokemon | 0.23270903729889816 |
| Vaporeon | pokemon | 0.22232747525961452 |
| Jolteon | pokemon | 0.22232747525961452 |
| Flareon | pokemon | 0.22232747525961452 |
| Espeon | pokemon | 0.22232747525961452 |
| Umbreon | pokemon | 0.22232747525961452 |
| Leafeon | pokemon | 0.22232747525961452 |
| Glaceon | pokemon | 0.22232747525961452 |
| Run Away | ability | 0.1176645178952697 |
| Adaptability | ability | 0.1176645178952697 |
| Anticipation | ability | 0.1176645178952697 |
| move_fairy_type_move | None | 0.04915151453601353 |
| Dragonite | pokemon | 0.0 |
| Dragonair | pokemon | 0.0 |
| Dratini | pokemon | 0.0 |
| Dragon | type | 0.0 |
| Flying | type | 0.0 |
| Inner Focus | ability | 0.0 |

### Degree (Weighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.25 |
| Normal | type | 0.1875 |
| Pikachu | pokemon | 0.16666666666666666 |
| Lucario | pokemon | 0.125 |
| Dragonite | pokemon | 0.10416666666666667 |
| Gengar | pokemon | 0.08333333333333333 |
| Sylveon | pokemon | 0.0625 |
| Dragonair | pokemon | 0.041666666666666664 |
| Inner Focus | ability | 0.041666666666666664 |
| Vaporeon | pokemon | 0.041666666666666664 |
| Jolteon | pokemon | 0.041666666666666664 |
| Flareon | pokemon | 0.041666666666666664 |
| Espeon | pokemon | 0.041666666666666664 |
| Umbreon | pokemon | 0.041666666666666664 |
| Leafeon | pokemon | 0.041666666666666664 |
| Glaceon | pokemon | 0.041666666666666664 |
| Haunter | pokemon | 0.041666666666666664 |
| Alolan Raichu | pokemon | 0.041666666666666664 |
| Dratini | pokemon | 0.020833333333333332 |
| Dragon | type | 0.020833333333333332 |

### Betweenness (Weighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.04476950354609929 |
| Lucario | pokemon | 0.0398936170212766 |
| Dragonite | pokemon | 0.03900709219858156 |
| Inner Focus | ability | 0.031914893617021274 |
| Pikachu | pokemon | 0.03102836879432624 |
| Normal | type | 0.01551418439716312 |
| Sylveon | pokemon | 0.010638297872340425 |
| Dragonair | pokemon | 0.00975177304964539 |
| Gengar | pokemon | 0.007978723404255319 |
| Alolan Raichu | pokemon | 0.0070921985815602835 |
| Haunter | pokemon | 0.0035460992907801418 |
| Dratini | pokemon | 0.0 |
| Dragon | type | 0.0 |
| Flying | type | 0.0 |
| Multiscale | ability | 0.0 |
| Run Away | ability | 0.0 |
| Adaptability | ability | 0.0 |
| Anticipation | ability | 0.0 |
| Water Stone | item | 0.0 |
| Thunder Stone | item | 0.0 |

### Eigenvector (Weighted)
| label | type | score |
|---|---|---|
| Eevee | pokemon | 0.5570832703328176 |
| Normal | type | 0.4955274991276959 |
| Sylveon | pokemon | 0.23270903729889816 |
| Vaporeon | pokemon | 0.22232747525961452 |
| Jolteon | pokemon | 0.22232747525961452 |
| Flareon | pokemon | 0.22232747525961452 |
| Espeon | pokemon | 0.22232747525961452 |
| Umbreon | pokemon | 0.22232747525961452 |
| Leafeon | pokemon | 0.22232747525961452 |
| Glaceon | pokemon | 0.22232747525961452 |
| Run Away | ability | 0.1176645178952697 |
| Adaptability | ability | 0.1176645178952697 |
| Anticipation | ability | 0.1176645178952697 |
| move_fairy_type_move | None | 0.04915151453601353 |
| Dragonite | pokemon | 0.0 |
| Dragonair | pokemon | 0.0 |
| Dratini | pokemon | 0.0 |
| Dragon | type | 0.0 |
| Flying | type | 0.0 |
| Inner Focus | ability | 0.0 |

## Link Prediction (Top Suggestions)
(none)

## Statistical Validation
- Degree distribution is **more consistent with a power-law** than a simple exponential (AIC comparison).
- Spearman correlation (degree vs betweenness): **r = 0.738**, p = 1.5e-09
- Spearman correlation (degree vs eigenvector): **r = 0.498**, p = 0.000271
- Weighted Spearman (degree vs betweenness): **r = 0.738**, p = 1.5e-09
- Weighted Spearman (degree vs eigenvector): **r = 0.498**, p = 0.000271

## Node Property Prediction
- Neighbor-majority accuracy: **25.00%** on 4 hidden nodes.

## Traversal & Shortest Paths
### BFS (depth ≤ 3) from seeds
```text
Seed: pokemon_lucario
  Lucario → Riolu → Fighting → Steel → Steadfast → Inner Focus → Justified → Dragonite → Dragonair → Dragon → Flying → Multiscale

Seed: pokemon_eevee
  Eevee → Normal → Run Away → Adaptability → Anticipation → Vaporeon → Jolteon → Flareon → Espeon → Umbreon → Leafeon → Glaceon → Sylveon → move_fairy_type_move
```

### DFS (preorder) from seeds
```text
Seed: pokemon_lucario
  Lucario → Riolu → Fighting → Steel → Steadfast → Inner Focus → Dragonite → Dragonair → Dratini → Dragon → Flying → Multiscale → Justified

Seed: pokemon_eevee
  Eevee → Normal → Vaporeon → Jolteon → Flareon → Espeon → Umbreon → Leafeon → Glaceon → Sylveon → move_fairy_type_move → Run Away → Adaptability → Anticipation
```

### Shortest paths among seeds
```text
No path between Lucario and Eevee
```

## Interpretation (High-Level)
- Multiple sizable components suggest distinct subnetworks that may reflect different themes, domains, or disconnected data sources.
- The rich community structure points to multiple functional clusters within the graph (e.g., related concepts, co-occurring attributes, or entities that frequently appear together).

---
Generated by Module 6 (enhanced analysis).
