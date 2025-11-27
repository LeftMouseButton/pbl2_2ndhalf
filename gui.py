import os
import json
import threading
import subprocess
import configparser
import tkinter as tk
from tkinter import ttk, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_DIR = os.path.join(BASE_DIR, "config_default")
SOURCES_PLUGIN_DIR = os.path.join(
    BASE_DIR, "src", "kg", "module1_crawler", "sources"
)


class KGConfigEditorApp:
    def __init__(self, root):
        self.root = root
        root.title("Knowledge Graph Config Editor")

        # --- runtime state ---
        self.current_graph_name = None
        self.unsaved_changes = False
        self.nodes_modified_since_schema = False
        self.edges_modified_since_schema = False

        self.sources_state = {}          # {source: {"enabled": bool, "weight": float}}
        self.pipeline_process = None     # subprocess.Popen or None
        self.pipeline_thread = None      # threading.Thread or None
        self.stop_requested = False      # flag for stopping pipeline

        # --- top bar: graph name + load/save + seeds + run/stop ---
        top_frame = ttk.Frame(root, padding=8)
        top_frame.pack(fill="x", side="top")

        ttk.Label(top_frame, text="Graph name:").pack(side="left")

        self.graph_name_var = tk.StringVar()
        graph_entry = ttk.Entry(top_frame, textvariable=self.graph_name_var, width=30)
        graph_entry.pack(side="left", padx=(4, 4))

        load_btn = ttk.Button(top_frame, text="Load", command=self.on_load_clicked)
        load_btn.pack(side="left", padx=(4, 6))

        save_btn = ttk.Button(top_frame, text="Save", command=self.on_save_clicked)
        save_btn.pack(side="left", padx=(4, 20))   # extra space before run section

        # Seeds
        ttk.Label(top_frame, text="Seed 1:").pack(side="left")
        self.seed1_var = tk.StringVar()
        seed1_entry = ttk.Entry(top_frame, textvariable=self.seed1_var, width=18)
        seed1_entry.pack(side="left", padx=(4, 8))
        seed1_entry.bind("<Key>", lambda e: self._mark_unsaved())
        seed1_entry.bind("<<Paste>>", lambda e: self._mark_unsaved())
        seed1_entry.bind("<<Cut>>", lambda e: self._mark_unsaved())
        self.seed1_var.trace_add("write", lambda *_: self._mark_unsaved())

        ttk.Label(top_frame, text="Seed 2:").pack(side="left")
        self.seed2_var = tk.StringVar()
        seed2_entry = ttk.Entry(top_frame, textvariable=self.seed2_var, width=18)
        seed2_entry.pack(side="left", padx=(4, 8))
        seed2_entry.bind("<Key>", lambda e: self._mark_unsaved())
        seed2_entry.bind("<<Paste>>", lambda e: self._mark_unsaved())
        seed2_entry.bind("<<Cut>>", lambda e: self._mark_unsaved())
        self.seed2_var.trace_add("write", lambda *_: self._mark_unsaved())

        # Run / Stop buttons
        self.run_btn = ttk.Button(
            top_frame,
            text="Run Pipeline",
            command=self.on_run_pipeline_clicked
        )
        self.run_btn.pack(side="left", padx=(4, 4))

        self.stop_btn = ttk.Button(
            top_frame,
            text="Stop",
            command=self.on_stop_pipeline_clicked
        )
        self.stop_btn.pack(side="left", padx=(4, 4))
        self.stop_btn["state"] = "disabled"

        # --- notebook with sections ---
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # 1) entity_list.ini
        self.entity_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.entity_frame, text="Entities (entity_list.ini)")
        self.entity_text = self._create_labeled_text(
            self.entity_frame,
            "Entities to crawl (one per line, used by crawler.py):",
        )

        # 2) nodes + edges
        self.nodes_edges_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.nodes_edges_frame, text="Nodes & Edges")

        # Toggle: allow extra nodes/edges beyond those defined here
        self.allow_extra_nodes_var = tk.BooleanVar(value=False)
        toggle_frame = ttk.Frame(self.nodes_edges_frame)
        toggle_frame.pack(fill="x", pady=(0, 4))
        extra_cb = ttk.Checkbutton(
            toggle_frame,
            text="Allow extra nodes/edges (LLM may introduce additional types)",
            variable=self.allow_extra_nodes_var,
            command=self._mark_unsaved,
        )
        extra_cb.pack(anchor="w")

        self.nodes_text = self._create_labeled_text(
            self.nodes_edges_frame,
            "Nodes & node properties (e.g. 'vtuber: name, synonyms, description'):",
            field_name="nodes"
        )
        self.edges_text = self._create_labeled_text(
            self.nodes_edges_frame,
            "Edges & edge properties (required: source_type, target_type; "
            "e.g. 'belongs_to: vtuber -> agency | notes'):",
            field_name="edges"
        )

        # 3) Sources + weights
        self.sources_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.sources_frame, text="Sources")
        self._build_sources_section(self.sources_frame)

        # 4) LLM config (schema + prompt)
        self.llm_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.llm_frame, text="LLM Config")
        self._build_llm_section(self.llm_frame)

        # 5) Pipeline output (terminal)
        self.output_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.output_frame, text="Pipeline Output")
        self._build_output_section(self.output_frame)

        # Load default prompt on startup, as requested
        self._load_default_prompt()

        # Populate sources from plugin directory
        self._load_sources_from_plugins()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _create_labeled_text(self, parent, label_text, height=10, field_name=None):
        label = ttk.Label(parent, text=label_text)
        label.pack(anchor="w", pady=(0, 2))

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=(0, 8))

        text = tk.Text(frame, wrap="word", height=height)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vscroll.set)

        text.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # --- FIX unsaved_changes for text widgets ---
        def on_modified(event, widget=text):
            if widget.edit_modified():
                self.unsaved_changes = True
                widget.edit_modified(False)

                # Track nodes/edges changes for schema regeneration
                if field_name == "nodes":
                    self.nodes_modified_since_schema = True
                elif field_name == "edges":
                    self.edges_modified_since_schema = True


        text.bind("<<Modified>>", on_modified)

        return text


    def _build_sources_section(self, parent):
        description = (
            "Sources (automatically discovered from "
            "'src/kg/module1_crawler/sources').\n"
            "Check = enabled. Set source_weight as float from 0.000 to 1.000."
        )
        ttk.Label(parent, text=description).pack(anchor="w", pady=(0, 4))

        # Scrollable frame for many sources
        outer_frame = ttk.Frame(parent)
        outer_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner_frame = ttk.Frame(canvas)
        self.sources_inner_frame = inner_frame

        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        inner_frame.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_width)

        self.source_vars = {}        # source -> tk.BooleanVar
        self.source_weight_vars = {} # source -> tk.StringVar

    def _build_llm_section(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(top_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # Example schema JSON + Generate button
        schema_label_frame = ttk.Frame(left_frame)
        schema_label_frame.pack(anchor="w", fill="x")

        ttk.Label(schema_label_frame, text="Example schema JSON for LLM:").pack(
            side="left"
        )

        generate_btn = ttk.Button(
            schema_label_frame,
            text="Generate Example",
            command=self.on_generate_schema_clicked,
        )
        generate_btn.pack(side="right")

        self.schema_text = self._create_labeled_text(
            left_frame,
            "(Generated example will follow the entities/relationships structure, "
            "with confidence fields.)",
            height=18,
        )

        # Prompt box
        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))

        ttk.Label(right_frame, text="LLM prompt (prompt.ini):").pack(
            anchor="w", pady=(0, 2)
        )

        self.prompt_text = self._create_labeled_text(
            right_frame,
            "Prompt used for the LLM.",
            height=18,
        )

    def _build_output_section(self, parent):
        ttk.Label(parent, text="Pipeline output (stdout + stderr):").pack(
            anchor="w", pady=(0, 2)
        )

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        self.output_text = tk.Text(frame, wrap="word", height=20)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=vscroll.set)

        self.output_text.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(4, 0))
        clear_btn = ttk.Button(button_frame, text="Clear Output", command=self.on_clear_output)
        clear_btn.pack(side="right")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _get_graph_config_dir(self, graph_name):
        return os.path.join(BASE_DIR, "data", graph_name, "config")

    # ------------------------------------------------------------------
    # Loading logic
    # ------------------------------------------------------------------
    def on_load_clicked(self):
        graph_name = self.graph_name_var.get().strip()
        #if not graph_name:
        #    messagebox.showerror("Error", "Please enter a graph name.")
        #    return

        self.current_graph_name = graph_name
        graph_config_dir = self._get_graph_config_dir(graph_name)
        if os.path.isdir(graph_config_dir):
            config_dir = graph_config_dir
        else:
            messagebox.showinfo(
                "Info",
                f"No config found in data/{graph_name}/config.\n"
                f"Loading defaults from config_default/ instead.",
            )
            config_dir = DEFAULT_CONFIG_DIR

        self._load_text_file_to_widget(
            os.path.join(config_dir, "entity_list.ini"),
            self.entity_text,
        )
        self._load_text_file_to_widget(
            os.path.join(config_dir, "nodes.ini"),
            self.nodes_text,
        )
        self._load_text_file_to_widget(
            os.path.join(config_dir, "edges.ini"),
            self.edges_text,
        )

        # Update common seeds from entity list
        self._update_common_seeds_from_entity_list()

        # LLM schema JSON
        self._load_text_file_to_widget(
            os.path.join(config_dir, "llm_schema_example.json"),
            self.schema_text,
        )

        # Extra-nodes toggle: load from simple JSON flag if present, else default False.
        extra_flag_path = os.path.join(config_dir, "allow_extra_nodes.json")
        allow_extra = False
        if os.path.isfile(extra_flag_path):
            try:
                with open(extra_flag_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("allow_extra_nodes"), bool):
                    allow_extra = data["allow_extra_nodes"]
            except Exception:
                allow_extra = False
        self.allow_extra_nodes_var.set(allow_extra)

        # Prompt: prefer graph-specific prompt.ini if present, else default
        prompt_path_graph = os.path.join(graph_config_dir, "prompt.ini")
        if os.path.isfile(prompt_path_graph):
            self._load_text_file_to_widget(prompt_path_graph, self.prompt_text)
        else:
            self._load_default_prompt()

        # Sources config
        self._load_sources_config(os.path.join(config_dir, "sources.json"))

        messagebox.showinfo("Loaded", f"Configuration loaded for graph '{graph_name}'.")

    def _load_text_file_to_widget(self, path, widget):
        widget.delete("1.0", "end")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    widget.insert("1.0", f.read())
            except Exception as e:
                messagebox.showwarning("Warning", f"Could not read {path}: {e}")

    def _load_default_prompt(self):
        prompt_default_path = os.path.join(DEFAULT_CONFIG_DIR, "prompt.ini")
        self._load_text_file_to_widget(prompt_default_path, self.prompt_text)

    def _load_sources_from_plugins(self):
        # Clear previous widgets
        for child in self.sources_inner_frame.winfo_children():
            child.destroy()

        self.source_vars.clear()
        self.source_weight_vars.clear()

        if not os.path.isdir(SOURCES_PLUGIN_DIR):
            ttk.Label(
                self.sources_inner_frame,
                text=f"(No plugin directory found at {SOURCES_PLUGIN_DIR})",
            ).pack(anchor="w")
            return

        row = 0
        for filename in sorted(os.listdir(SOURCES_PLUGIN_DIR)):
            full_path = os.path.join(SOURCES_PLUGIN_DIR, filename)
            if os.path.isdir(full_path) and filename == "__pycache__":
                continue
            if not filename.endswith(".py"):
                continue
            if filename in ("registry.py", "__init__.py"):
                continue

            source_name = os.path.splitext(filename)[0]

            enabled_var = tk.BooleanVar(value=False)
            weight_var = tk.StringVar(value="1.000")

            cb = ttk.Checkbutton(
                self.sources_inner_frame, text=source_name, variable=enabled_var
            )
            cb.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)

            weight_entry = ttk.Entry(
                self.sources_inner_frame, textvariable=weight_var, width=7
            )
            weight_entry.grid(row=row, column=1, sticky="w", pady=2)

            ttk.Label(self.sources_inner_frame, text="source_weight").grid(
                row=row, column=2, sticky="w", padx=(4, 0)
            )
    
            enabled_var.trace_add("write", lambda *_: self._mark_unsaved())
            weight_var.trace_add("write", lambda *_: self._mark_unsaved())

            self.source_vars[source_name] = enabled_var
            self.source_weight_vars[source_name] = weight_var
            row += 1

    def _load_sources_config(self, sources_json_path):
        # Start from plugin list; then overlay enabled+weights from config
        for source, enabled_var in self.source_vars.items():
            enabled_var.set(False)
        for source, weight_var in self.source_weight_vars.items():
            weight_var.set("1.000")

        if not os.path.isfile(sources_json_path):
            return

        try:
            with open(sources_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showwarning(
                "Warning", f"Could not read sources config {sources_json_path}: {e}"
            )
            return

        self.sources_state = data
        for source, cfg in data.items():
            if source in self.source_vars:
                self.source_vars[source].set(bool(cfg.get("enabled", False)))
            if source in self.source_weight_vars:
                w = cfg.get("weight", 1.0)
                self.source_weight_vars[source].set(f"{float(w):.3f}")

    def _update_common_seeds_from_entity_list(self):
        """
        Auto-fill
        Seed 1/Seed 2 if empty.
        """
        text = self.entity_text.get("1.0", "end-1c")
        lines = [ln.strip() for ln in text.splitlines()]
        seeds = [
            ln for ln in lines
            if ln and not ln.lstrip().startswith("#")
        ]

        # Auto-fill seed1/seed2 if they are empty
        if seeds:
            if not self.seed1_var.get():
                self.seed1_var.set(seeds[0])
            if len(seeds) > 1 and not self.seed2_var.get():
                self.seed2_var.set(seeds[1])

    # ------------------------------------------------------------------
    # Saving logic
    # ------------------------------------------------------------------
    def on_save_clicked(self):
        graph_name = self.graph_name_var.get().strip()
        if not graph_name:
            messagebox.showerror("Error", "Please enter a graph name.")
            return

        self.current_graph_name = graph_name
        graph_config_dir = self._get_graph_config_dir(graph_name)
        os.makedirs(graph_config_dir, exist_ok=True)

        # Write text areas to files
        self._save_widget_to_text_file(
            self.entity_text, os.path.join(graph_config_dir, "entity_list.ini")
        )
        self._save_widget_to_text_file(
            self.nodes_text, os.path.join(graph_config_dir, "nodes.ini")
        )
        self._save_widget_to_text_file(
            self.edges_text, os.path.join(graph_config_dir, "edges.ini")
        )
        self._save_widget_to_text_file(
            self.schema_text, os.path.join(graph_config_dir, "llm_schema_example.json")
        )
        self._save_widget_to_text_file(
            self.prompt_text, os.path.join(graph_config_dir, "prompt.ini")
        )

        # Sources
        sources_path = os.path.join(graph_config_dir, "sources.json")
        sources_cfg = {}
        for source in self.source_vars:
            enabled = bool(self.source_vars[source].get())
            weight_str = self.source_weight_vars[source].get().strip()
            try:
                weight = float(weight_str)
            except ValueError:
                weight = 1.0
            weight = max(0.0, min(1.0, weight))
            sources_cfg[source] = {"enabled": enabled, "weight": weight}
        try:
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump(sources_cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {sources_path}: {e}")

        # Persist extra-nodes toggle as a tiny JSON flag
        extra_flag_path = os.path.join(graph_config_dir, "allow_extra_nodes.json")
        try:
            with open(extra_flag_path, "w", encoding="utf-8") as f:
                json.dump({"allow_extra_nodes": bool(self.allow_extra_nodes_var.get())}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {extra_flag_path}: {e}")

        # NEW: auto-generate condensed schema_keys.json on save
        schema_keys_path = os.path.join(graph_config_dir, "schema_keys.json")
        schema_keys = self._generate_condensed_schema()
        try:
            with open(schema_keys_path, "w", encoding="utf-8") as f:
                json.dump(schema_keys, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {schema_keys_path}: {e}")

        # After saving, ensure missing keys from defaults are appended
        self._apply_default_keys(graph_config_dir)

        self.unsaved_changes = False

        messagebox.showinfo("Saved", f"Configuration saved for graph '{graph_name}'.")

    def _save_widget_to_text_file(self, widget, path):
        text = widget.get("1.0", "end-1c")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {path}: {e}")

    def _apply_default_keys(self, graph_config_dir):
        """
        For each file in config_default/, if the corresponding file in the graph
        config exists and both are JSON or both are INI, append any missing keys
        from the default into the graph-specific config.
        """
        if not os.path.isdir(DEFAULT_CONFIG_DIR):
            return

        for filename in os.listdir(DEFAULT_CONFIG_DIR):
            default_path = os.path.join(DEFAULT_CONFIG_DIR, filename)
            target_path = os.path.join(graph_config_dir, filename)

            if not os.path.isfile(default_path) or not os.path.isfile(target_path):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext == ".json":
                self._merge_json_default_keys(default_path, target_path)
            elif ext == ".ini":
                self._merge_ini_default_keys(default_path, target_path)

    def _merge_json_default_keys(self, default_path, target_path):
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                default_data = json.load(f)
            with open(target_path, "r", encoding="utf-8") as f:
                target_data = json.load(f)
        except Exception:
            return

        if not isinstance(default_data, dict) or not isinstance(target_data, dict):
            return

        changed = False
        for key, value in default_data.items():
            if key not in target_data:
                target_data[key] = value
                changed = True

        if changed:
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(target_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _merge_ini_default_keys(self, default_path, target_path):
        default_cfg = configparser.ConfigParser()
        target_cfg = configparser.ConfigParser()

        try:
            default_cfg.read(default_path, encoding="utf-8")
            target_cfg.read(target_path, encoding="utf-8")
        except Exception:
            return

        changed = False
        for section in default_cfg.sections():
            if not target_cfg.has_section(section):
                target_cfg.add_section(section)
                changed = True
            for option in default_cfg.options(section):
                if not target_cfg.has_option(section, option):
                    target_cfg.set(section, option, default_cfg.get(section, option))
                    changed = True

        if changed:
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    target_cfg.write(f)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # LLM example-schema generation (with confidence)
    # ------------------------------------------------------------------
    def on_generate_schema_clicked(self):
        """
        Use nodes/edges text to generate a sample JSON structure
        with entities[] and relationships[] that could be used as
        an example for an LLM.

        Every entity, every attribute, and every relationship includes
        a 'confidence' field (float 0.00–1.00).
        """
        nodes_spec = self.nodes_text.get("1.0", "end-1c").strip().splitlines()
        edges_spec = self.edges_text.get("1.0", "end-1c").strip().splitlines()

        # --- Parse node types ---
        node_types = []
        for line in nodes_spec:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 1)
            node_type = parts[0].strip()
            attrs = []
            if len(parts) > 1:
                attrs = [a.strip() for a in parts[1].split(",") if a.strip()]
            node_types.append((node_type, attrs))

        # --- Parse edge types ---
        edge_types = []
        for line in edges_spec:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            rel = None
            src_type = None
            tgt_type = None
            props = []

            rel_part, rest = None, None
            if ":" in line:
                rel_part, rest = line.split(":", 1)
                rel = rel_part.strip()
            else:
                rest = line

            src_tgt_part, props_part = rest, ""
            if "|" in rest:
                src_tgt_part, props_part = rest.split("|", 1)

            if "->" in src_tgt_part:
                s, t = src_tgt_part.split("->", 1)
                src_type = s.strip()
                tgt_type = t.strip()

            if props_part:
                props = [p.strip() for p in props_part.split(",") if p.strip()]

            if rel and src_type and tgt_type:
                edge_types.append((rel, src_type, tgt_type, props))

        # --- Fallbacks ---
        if not node_types:
            node_types = [
                ("entity", ["name", "type"]),
            ]
        if not edge_types:
            edge_types = [
                ("related_to", "entity", "entity", ["notes"]),
            ]

        # --- Build Entities with confidence ---
        entities = []
        for i, (node_type, attrs) in enumerate(node_types, start=1):
            node_id = f"{node_type.lower()}_{i}"

            # Attributes with per-attribute confidence
            attributes = {}
            for j, attr in enumerate(attrs, start=1):
                attributes[attr] = {
                    "value": f"example_{attr}_{j}",
                    "confidence": 0.85
                }

            entity = {
                "id": node_id,
                "type": node_type,
                "name": f"Example {node_type.title()} {i}",
                "confidence": 0.90
            }

            if attributes:
                entity["attributes"] = attributes

            entities.append(entity)

        # --- Build Relationships with confidence ---
        relationships = []
        for i, (rel, src_type, tgt_type, props) in enumerate(edge_types, start=1):
            src_id = f"{src_type.lower()}_1"
            tgt_id = f"{tgt_type.lower()}_1"

            rel_obj = {
                "source": src_id,
                "relation": rel,
                "target": tgt_id,
                "confidence": 0.88
            }

            if props:
                properties = {}
                for p in props:
                    properties[p] = {
                        "value": f"example_{p}",
                        "confidence": 0.80
                    }
                rel_obj["properties"] = properties

            relationships.append(rel_obj)

        example = {
            "entities": entities,
            "relationships": relationships
        }

        pretty = json.dumps(example, indent=2, ensure_ascii=False)
        self.schema_text.delete("1.0", "end")
        self.schema_text.insert("1.0", pretty)

        # Reset modification flags for schema dependency
        self.nodes_modified_since_schema = False
        self.edges_modified_since_schema = False


    # ------------------------------------------------------------------
    # Condensed schema (schema_keys.json) generation with confidence
    # ------------------------------------------------------------------
    def _generate_condensed_schema(self):
        """
        Generate a condensed JSON schema (schema_keys.json-style) in which:
        - Every entity has a confidence score.
        - Every attribute is {value:"", confidence:0.0}.
        - Every relationship has a confidence score.
        - Every relationship property is {value:"", confidence:0.0}.
        Returned object is a Python dict, ready for json.dump().
        """
        nodes_spec = self.nodes_text.get("1.0", "end-1c").strip().splitlines()
        edges_spec = self.edges_text.get("1.0", "end-1c").strip().splitlines()

        entities_schema = {}
        relationships_schema = {}

        # Parse node definitions (entities)
        for line in nodes_spec:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue

            node_type, rest = line.split(":", 1)
            node_type = node_type.strip()
            attributes = [a.strip() for a in rest.split(",") if a.strip()]

            attr_obj = {
                attr: {
                    "value": "",
                    "confidence": 0.0
                }
                for attr in attributes
            }

            entities_schema[node_type] = {
                "id": {
                    "value": "",
                    "confidence": 0.0
                },
                "attributes": attr_obj,
                "confidence": 0.0
            }

        # Parse edge definitions (relationships)
        for line in edges_spec:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            relation = None
            src_type = None
            tgt_type = None
            props = []

            if ":" in line:
                relation_part, rest = line.split(":", 1)
                relation = relation_part.strip()
            else:
                rest = line

            if "|" in rest:
                src_tgt_part, props_part = rest.split("|", 1)
                props = [p.strip() for p in props_part.split(",") if p.strip()]
            else:
                src_tgt_part = rest

            if "->" in src_tgt_part:
                s, t = src_tgt_part.split("->", 1)
                src_type = s.strip()
                tgt_type = t.strip()

            if not (relation and src_type and tgt_type):
                continue

            prop_obj = {
                p: {
                    "value": "",
                    "confidence": 0.0
                }
                for p in props
            }

            relationships_schema[relation] = {
                "source_type": src_type,
                "target_type": tgt_type,
                "properties": prop_obj,
                "confidence": 0.0
            }

        condensed = {
            "entities": entities_schema,
            "relationships": relationships_schema
        }
        return condensed

    # ------------------------------------------------------------------
    # Pipeline run / stop / output
    # ------------------------------------------------------------------
    def on_run_pipeline_clicked(self):
        """
        Executes: python main.py --graph-name X --sources s1 s2 ... --seed "text1" --seed "text2"
        Streams output live into the Pipeline Output tab.
        """
        if self.pipeline_process is not None and self.pipeline_process.poll() is None:
            messagebox.showwarning("Pipeline running", "A pipeline is already running.")
            return

        graph_name = self.graph_name_var.get().strip()
        if not graph_name:
            messagebox.showerror("Error", "Please enter a graph name before running the pipeline.")
            return

        # ====== 0) Check if nodes/edges changed since last schema generation ======
        if self.nodes_modified_since_schema or self.edges_modified_since_schema:
            result = messagebox.askyesno(
                "Schema Generation Reminder",
                "You modified NODES or EDGES.\n\n"
                "Did you remember to go to LLM Config -> Generate Example\n"
                "to regenerate the example extraction schema?\n\n"
                "YES = Continue without updating the example\n"
                "NO  = I will update it first"
            )
            if not result:
                return


        # ------- 1) Check unsaved changes -------
        if self.unsaved_changes:
            result = messagebox.askyesno(
                "Unsaved Changes",
                "Did you remember to SAVE first to apply your changes?\n\n"
                "Press YES = Continue without my changes\n"
                "Press NO  = I will save first"
            )
            if not result:
                return
        # ------- 2) Ensure graph directory exists -------
        graph_name = self.graph_name_var.get().strip()
        if not graph_name:
            messagebox.showerror("Error", "Please enter a graph name.")
            return

        graph_dir = os.path.join(BASE_DIR, "data", graph_name)
        config_dir = os.path.join(graph_dir, "config")

        if not os.path.isdir(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
                # Copy default files into new config dir
                for filename in os.listdir(DEFAULT_CONFIG_DIR):
                    src = os.path.join(DEFAULT_CONFIG_DIR, filename)
                    dst = os.path.join(config_dir, filename)
                    if os.path.isfile(src):
                        with open(src, "r", encoding="utf-8") as f_src:
                            with open(dst, "w", encoding="utf-8") as f_dst:
                                f_dst.write(f_src.read())
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Could not create default configuration in {config_dir}:\n{e}"
                )
                return


        enabled_sources = [
            src for src, var in self.source_vars.items()
            if var.get()
        ]

        if not enabled_sources:
            if not messagebox.askyesno(
                "No sources selected",
                "No sources are enabled. Run pipeline anyway?"
            ):
                return

        seed1 = self.seed1_var.get().strip()
        seed2 = self.seed2_var.get().strip()

        seeds = []
        if seed1:
            seeds.append(seed1)
        if seed2:
            seeds.append(seed2)

        if not seeds:
            messagebox.showerror("Error", "Please enter at least one seed to run the pipeline.")
            return

        cmd = ["python", "main.py", "--graph-name", graph_name]

        # Propagate extra-nodes toggle down the pipeline.
        if bool(self.allow_extra_nodes_var.get()):
            cmd.append("--allow-extra-nodes")

        if enabled_sources:
            cmd.append("--sources")
            cmd.extend(enabled_sources)

        for seed in seeds:
            cmd += ["--seed", seed]

        readable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        if not messagebox.askyesno("Run pipeline", f"Execute:\n\n{readable}\n\nContinue?"):
            return

        self._append_output_text(f"\n=== Running: {readable} ===\n")
        self.stop_requested = False

        try:
            self.pipeline_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            messagebox.showerror("Execution Error", f"Could not run pipeline:\n{e}")
            self.pipeline_process = None
            return

        # Disable Run, enable Stop
        self.run_btn["state"] = "disabled"
        self.stop_btn["state"] = "normal"

        self.pipeline_thread = threading.Thread(
            target=self._stream_process_output,
            args=(self.pipeline_process,),
            daemon=True
        )
        self.pipeline_thread.start()

    def _stream_process_output(self, process):
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    if self.stop_requested:
                        break
                    self.root.after(0, self._append_output_text, line)
        except Exception as e:
            self.root.after(0, self._append_output_text, f"\n[Error reading output: {e}]\n")

        rc = process.poll()
        if rc is None:
            rc = process.wait()

        self.root.after(0, self._on_pipeline_finished, rc)

    def _on_pipeline_finished(self, return_code):
        self._append_output_text(f"\n=== Pipeline finished with code {return_code} ===\n")
        self.pipeline_process = None
        self.pipeline_thread = None
        self.run_btn["state"] = "normal"
        self.stop_btn["state"] = "disabled"
        self.stop_requested = False

    def on_stop_pipeline_clicked(self):
        """
        Request to stop the running pipeline (terminate subprocess).
        """
        if self.pipeline_process is None or self.pipeline_process.poll() is not None:
            messagebox.showinfo("Info", "No running pipeline to stop.")
            return

        self.stop_requested = True
        self._append_output_text("\n[Stop requested…]\n")

        try:
            self.pipeline_process.terminate()
        except Exception as e:
            self._append_output_text(f"[Error sending terminate: {e}]\n")

    def _append_output_text(self, text):
        self.output_text.insert("end", text)
        self.output_text.see("end")

    def on_clear_output(self):
        self.output_text.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Common seeds dropdown behavior
    # ------------------------------------------------------------------
    def on_common_seed_selected(self, event=None):
        """
        When user selects a common seed, fill Seed 1 if empty, else Seed 2,
        else overwrite Seed 2.
        """
        seed = self.common_seed_var.get().strip()
        if not seed:
            return
        previous = (self.seed1_var.get(), self.seed2_var.get())

        if not self.seed1_var.get():
            self.seed1_var.set(seed)
        elif not self.seed2_var.get():
            self.seed2_var.set(seed)
        else:
            self.seed2_var.set(seed)

        # Mark unsaved if this actually changed something
        current = (self.seed1_var.get(), self.seed2_var.get())
        if current != previous:
            self._mark_unsaved()


    def _mark_unsaved(self, event=None):
        self.unsaved_changes = True



def main():
    root = tk.Tk()
    app = KGConfigEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
