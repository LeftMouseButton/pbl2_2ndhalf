# Knowledge Graph Pipeline

Builds and analyses a **topic-agnostic knowledge graph**  
(e.g., cancer, Pokémon, League of Legends).

The modular pipeline:

1. Crawls web sources for raw text (Module 1)
2. Cleans & normalizes text (Module 2)
3. Uses an LLM to extract entities & relationships (Module 3)
4. Validates / auto-repairs JSON outputs (Module 4)
5. Combines + ontology-normalizes JSON for analysis (Module 5)
6. Builds a heterogeneous graph and runs analytics + visualization (Module 6)

- Working data lives under: `data/{graph_name}/`
- Frozen demonstration runs (used for papers/experiments) live under: `demos/{graph_name}/`
- A LaTeX paper (for the cancer demo) lives in: `papers/cancer/`

---

## Dependencies

Core packages:

```
conda install beautifulsoup4 lxml networkx pandas scikit-learn psutil -c bioconda pronto -c conda-forge python-slugify pydantic pyvis rapidfuzz
```

Install LLM / API client:

```bash
pip install google-generativeai
```

Set your API key (required for Module 3):

```
export GOOGLE_API_KEY="YOUR_API_KEY"
```

---

## How to Use
### New: 
- Use the GUI!

---
### Old / Manual:
### Per-graph inputs (user supplied -- edit these before running)
- `data/{graph_name}/names.txt` – list of entities (eg: wikipedia page titles) to crawl.
- `data/{graph_name}/schema/schema_keys.json` – schema tailored to the topic.
- `data/{graph_name}/schema/example_entity_extraction.json` – example for the LLM (Module 3).
- `data/{graph_name}/schema/prompt.txt` – prompt template (schema+example appended automatically).
- `data/{graph_name}/ontologies/` - Optional ontologies.

### Option A – Pipeline Launcher

This runs Modules 1 → 6 sequentially for a given graph topic.

```bash
python main.py --graph-name cancer --sources wikipedia medlineplus --seed "lung cancer" --seed "liver cancer"
```

Expected layout (created automatically):

- `data/cancer/raw/`
- `data/cancer/processed/`
- `data/cancer/json/`
- `data/cancer/combined/`
- `data/cancer/analysis/`

You can then open `data/cancer/analysis/graph.html` in a browser and/or read   `data/cancer/analysis/report_module6.md` for a detailed report.

### Option B – Manual

`main.py` is a thin subprocess wrapper around the module CLIs.  
If you prefer, you can run each module manually (see examples below).

```
1) python -m src.kg.module1_crawler.crawler --graph-name cancer --sources wikipedia medlineplus
2) python -m src.kg.module2_clean.clean --data-location data/cancer
3) python -m src.kg.module3_extraction_entity_relationship.extraction_entity_relationship --data-location data/cancer --all
4) python -m src.kg.module4_validate_json.validate_json --data-location data/cancer
5) python -m src.kg.module5_prepare_for_analysis.combine_json_files --data-location data/cancer
6) python -m src.kg.module6_analysis.analyse --data-location data/cancer --validation --enhanced-viz --memory-monitor --seed "lung cancer" --seed "liver cancer"

---

Re-analyse a frozen demo, writing data somewhere else:
1) python -m src.kg.module6_analysis.analyse --data-location demos/pokemon --outdir data/pokemon/analysis
```

---

# How to Extend

New Source:
- Add a new python file under crawler/sources
- Add a new python file under clean/sources
- Run pipeline, being sure to add the new source to the parameter list (eg: --sources YOUR_NEW_SOURCE)

---

## Repository Layout (High-Level)

- `main.py` – optional pipeline launcher (sequentially runs Modules 1–6)
- `src/kg/`
  - `module1_crawler/` – topic-agnostic web crawler with pluggable sources
  - `module2_clean/` – cleaning / preprocessing with pluggable cleaners
  - `module3_extraction_entity_relationship/` – LLM entity & relation extraction
  - `module4_validate_json/` – auto-repair validator for JSON outputs
  - `module5_prepare_for_analysis/` – combine + ontology-normalize JSON
  - `module6_analysis/` – graph construction + analytics + visualization
  - `utils/` – shared helpers (paths resolution, token count prediction)
- `data/{graph_name}/`
  - `raw/` – raw HTML / text from Module 1
  - `processed/` – cleaned plain text from Module 2
  - `json/` – LLM extraction JSON from Module 3
  - `combined/` – merged + normalized JSON from Module 5
  - `analysis/` – graph files, CSVs, reports, HTML from Module 6
  - `schema/` – schema for graph building, example JSON and prompt templates for Module 3 LLM
  - `ontologies/` – local ontology files (.obo / .owl) for normalization
  - `names.txt` – list of entities for crawling (e.g., cancer types)
- `demos/{graph_name}/` – frozen snapshots (raw → combined → analysis)
- `papers/cancer/` – LaTeX + figures + PDF for the cancer case study


## Modules/Steps:
### 1) Module 1 – Web Crawler
-----------------------------------
**Location:** `src/kg/module1_crawler/`

Collects raw natural-language content (HTML or plain text) for a set of entity names.

- Topic-agnostic: works for diseases, Pokémon, League of Legends champions, etc.
- Source-specific plugins live in `sources/` and are auto-registered.
- Reliability per source is recorded for LLM extraction and downstream edge weighting.


Sources are plugin-based and auto-discovered from `src/kg/module1_crawler/sources` using a registry. No sources are enabled by default; specify `--sources` explicitly.

### Example CLI
```
python -m src.kg.module1_crawler.crawler --graph-name pokemon --sources wikipedia
python -m src.kg.module1_crawler.crawler --graph-name cancer --sources wikipedia medlineplus
```

Input:

```
(http sources)
```

Output:

```
data/<graph>/raw/{slug}_{source}.{ext}
data/<graph>/raw/metadata.jsonl    # one JSON record per fetched resource
```

Arguments:

- `--graph-name` – topic name (creates/uses `data/{graph_name}`).
- `--data-location` – explicit base directory (overrides `--graph-name`).
- `--names-file` – file with one entity name per line (default `data/{graph_name}/names.txt`).
- `--sources` – one or more of the registered sources (e.g. `wikipedia`, `medlineplus`).

### Sources

Implemented under `src/kg/module1_crawler/sources/`:

- `wikipedia.py` – REST API, extracts summary text
- `medlineplus.py` – HTML via XML search API, patient-facing handouts
- `registry.py` – `@register_source` decorator + central registry

### 2) Module 2 – Cleaning / Preprocessing
-----------------------------------

**Location:** `src/kg/module2_clean/`

Converts raw HTML or plain-text files into **normalized, cleaned text** for LLM extraction.

Key responsibilities:

- Strip HTML/JS/CSS boilerplate, nav bars, ads, etc.
- Fix common mojibake / encoding issues.
- Apply source-specific trim rules.
- Preserve enough structure for good LLM extraction while reducing noise.

### Example CLI

```bash
python -m src.kg.module2_clean.clean   --graph-name cancer
```

### Architecture

Under `src/kg/module2_clean/sources/`:

- `default.py` – generic HTML → text cleaner
- `wikipedia.py` – Wikipedia-specific cleanup
- `medlineplus.py` – strict trimming for patient handouts
- `registry.py` – `@register_cleaner`

### Inputs
```
data/raw/*.html or .txt   (from Module 1 - Web Crawler)
```

### Outputs

Under `data/{graph_name}/processed/`:
```
 {disease}_-_{source}.txt
 metadata.jsonl
```
### 3) Module 3 – LLM-based Entity and Relationship Extraction
-----------------------------------
**Location:** `src/kg/module3_extraction_entity_relationship/`

Uses the Google AI Studio API (Gemini 2.5 Flash Lite) to perform structured entity and relationship extraction for knowledge-graph population.

This step also combines all input text from all sources into one file per disease.
If we have a lot of sources for each disease in the future, this is a weak point and will need to be changed (will run into a token limit otherwise).

Note: this is also the weakest point in the entire project for scientific reproducibility. Would be ideal to avoid use of an LLM here.

Arguments:

- `--entity` – run on a single item  
- `--all` – process **all** entities in `data/{graph_name}/processed/`
- `--force` – overwrite existing JSON  
- `--schema-path` – override `{base}/schema/schema_keys.json`  
- `--example-path` – override example JSON  
- `--prompt-path` – override prompt template  

Includes:

- Injection of `schema_keys.json` and `example_entity_extraction.json` into prompt  
- Retries failed extractions up to a configurable limit.

### Inputs
```
data/{graph_name}/processed/*.txt  (from Module 2 - Cleaner)
```

### Outputs

Under `data/{graph_name}/json/`:
```
{disease-name}.json
```


### 4) Module 4 - Validator with Auto-Repair for LLM Step-1 JSON Outputs
-------------------------------------------------
Checks and fixes structural issues in extracted JSONs.
No backup files are produced — JSONs are overwritten in place.
```
Input:
    data/json/{disease-name}.json
Output:
    data/json/{disease-name}.json    # validated, schema-consistent
```

### 5) Module 5 - Analysis Preparation: Ontology Normalization & JSON Combination
-----------------------------------
- Standardizes names: ontology-based normalization with fuzzy matching.
- Combines all JSON files (from Module 4) into a single file.
- Produces an additional matched-only JSON file containing only verified entities, for building a high-quality graph.

```
Input:
    data/json/*.json                (from Module 4)
    ontologies/*.obo / *.owl        (local ontology references, e.g. DOID, NCIT)

Output:
    data/combined/all_diseases.json         # merged dataset with all normalized terms
    data/combined/all_diseases_matched.json # subset containing only ontology-matched entities
    data/combined/ontology_mapping.json     # grouped ontology match metadata (by file/key)
    data/combined/normalization_stats.json  # summary: total terms, match rate, avg. score, etc.
    data/combined/unmatched_terms.txt       # list of entities not found in any ontology


Notes:
    • Distinguishes between disease-related and gene-related ontologies to prevent cross-category errors (e.g., prevents "NF2" gene from matching "Vestibular schwannomatosis").
    • Automatically detects all ontology files in the ontologies/ directory  
      – Classifies gene-related files (e.g., HGNC, Ensembl, NCBI) separately from disease ontologies (e.g., DOID, NCIT, EFO). 
    • If no gene ontology is detected, `related_genes` normalization is automatically skipped to prevent false matches.  
    • Supports optional flags:
        --no-normalize     → combine files only (skip ontology normalization)  
        --no-lowercase     → preserve original capitalization  
    • Outputs are suitable for both manual LLM upload and non-LLM graph analysis  
      (e.g., NetworkX or PyVis workflows in Module 6)
```

```
Future Improvements Required for Module 5:
    • Match rate is low with fuzzy matching. Could use an LLM here too, but then that introduces more problems with reproducibility, and added(financial) cost.
    • Dealing with token limits constitutes a major challenge for LLM-based graph analysis.
    We need to employ RAG, Summarization, Chunking, Compression/Encoding, etc.
    Running the "TokenCount Predictor" (Utilities) suggests we should be able to store information for approximately 300 diseases before this step becomes essential, assuming the LLM provider = ChatGPT Plus.
```

### 6) Module 6 - NetworkX Analysis
-----------------------------------
Using NetworkX, produces the graph, performs analysis, exports results.

```
Input:
    data/combined/all_diseases.json
        OR
    data/json/*.json
Output:
    data/analysis/
        report_module6.md                 # Human-readable analysis report (paste-able into paper)
        graph.graphml                     # Full graph (labels & types as node/edge attributes)
        graph.html                        # Interactive PyVis visualization
        centrality.csv                    # Degree, betweenness, eigenvector (top-k and full)
        communities.csv                   # Node → community mapping
        link_predictions.csv              # Top predicted links (ensemble-ranked)
```

### 7) Module 7 - GNN Training (PyTorch Geometric)
-----------------------------------
(todo)


### Utilities
### TokenCount Predictor
-----------------------------------
Estimates token counts for JSON files (useful for planning LLM-based analysis or RAG setups).
```
Usage: 
        # For a directory
            python src/kg/utils/tokencount_predictor.py --input_path data/json
        # For a single file
            python src/kg/utils/tokencount_predictor.py --input_path data/example.json
Input:
    .json file(s) from --input_path
Output:
    Token count printed to the command line.
```


## Limitations
```
Module 1 -- More sources are required beyond Wikipedia/MedlinePlus. Code is structured such that additional sources can be added in the future.
Module 3 -- Major issues
                1) Reproducibility: LLMs generate different information with each run.
                2) Hallucinations/etc: LLMs may fabricate facts or utilize external information.
                3) Naming issues: (mitigated by Module 5)
                        1) Some entries do not share the same naming scheme (eg: "Tobacco smoking", "Smoking tobacco", "Smoking (active and passive)", "Smoking", and "Smoking cigarettes").
                        2) Excessive verbosity: "Being overweight (possibly due to smoking-related lower body weight)"
...
```

## Cancer Ontology Sources:
```

    https://raw.githubusercontent.com/DiseaseOntology/HumanDiseaseOntology/main/src/ontology/doid.obo
    https://bioportal.bioontology.org/ontologies/NCIT
    https://storage.googleapis.com/public-download-files/hgnc/owl/owl/hgnc.owl

```