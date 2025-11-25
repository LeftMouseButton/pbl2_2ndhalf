import os
import json
import tkinter as tk
from tkinter import ttk, messagebox

try:
    # Python 3.11+
    import importlib.resources as pkg_resources  # noqa: F401
except ImportError:
    pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_DIR = os.path.join(BASE_DIR, "config_default")
SOURCES_PLUGIN_DIR = os.path.join(
    BASE_DIR, "src", "kg", "module1_crawler", "sources"
)


class KGConfigEditorApp:
    def __init__(self, root):
        self.root = root
        root.title("Knowledge Graph Config Editor")

        # --- top-level state ---
        self.current_graph_name = None
        self.sources_state = {}  # {source: {"enabled": bool, "weight": float}}

        # --- top bar: graph name + load/save ---
        top_frame = ttk.Frame(root, padding=8)
        top_frame.pack(fill="x", side="top")

        ttk.Label(top_frame, text="Graph name:").pack(side="left")

        self.graph_name_var = tk.StringVar()
        graph_entry = ttk.Entry(top_frame, textvariable=self.graph_name_var, width=30)
        graph_entry.pack(side="left", padx=(4, 4))

        load_btn = ttk.Button(top_frame, text="Load", command=self.on_load_clicked)
        load_btn.pack(side="left", padx=(4, 4))

        save_btn = ttk.Button(top_frame, text="Save", command=self.on_save_clicked)
        save_btn.pack(side="left", padx=(4, 4))

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

        self.nodes_text = self._create_labeled_text(
            self.nodes_edges_frame,
            "Nodes & node properties (free-form, one per line, e.g. 'disease: name, synonyms, summary'):",
        )
        self.edges_text = self._create_labeled_text(
            self.nodes_edges_frame,
            "Edges & edge properties (required: source_type, target_type; free-form, e.g. 'causes: disease -> gene | evidence, confidence'):",
        )

        # 3) Sources + weights
        self.sources_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.sources_frame, text="Sources")

        self._build_sources_section(self.sources_frame)

        # 4) LLM config (schema + prompt)
        self.llm_frame = ttk.Frame(notebook, padding=8)
        notebook.add(self.llm_frame, text="LLM Config")

        self._build_llm_section(self.llm_frame)

        # Load default prompt on startup, as requested
        self._load_default_prompt()

        # Populate sources from plugin directory
        self._load_sources_from_plugins()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _create_labeled_text(self, parent, label_text, height=10):
        """Create a label + scrollable Text widget; return the Text."""
        label = ttk.Label(parent, text=label_text)
        label.pack(anchor="w", pady=(0, 2))

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=(0, 8))

        text = tk.Text(frame, wrap="word", height=height)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vscroll.set)

        text.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

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

        # Attach frame to canvas
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        inner_frame.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_width)

        # Will be populated by _load_sources_from_plugins
        self.source_vars = {}      # source -> tk.BooleanVar
        self.source_weight_vars = {}  # source -> tk.StringVar

    def _build_llm_section(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill="both", expand=True)

        # Example schema box + Generate button
        left_frame = ttk.Frame(top_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        schema_label_frame = ttk.Frame(left_frame)
        schema_label_frame.pack(anchor="w", fill="x")

        ttk.Label(schema_label_frame, text="Example schema JSON for LLM:").pack(
            side="left"
        )

        generate_btn = ttk.Button(
            schema_label_frame,
            text="Generate",
            command=self.on_generate_schema_clicked,
        )
        generate_btn.pack(side="right")

        self.schema_text = self._create_labeled_text(
            left_frame,
            "(Generated example will follow the entities/relationships structure, "
            "similar to your example JSON.)",
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
            #messagebox.showerror("Error", "Please enter a graph name.")
            #return

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

        # LLM schema JSON
        self._load_text_file_to_widget(
            os.path.join(config_dir, "llm_schema_example.json"),
            self.schema_text,
        )

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

        # Expecting {source_name: {"enabled": bool, "weight": float}}
        self.sources_state = data
        for source, cfg in data.items():
            if source in self.source_vars:
                self.source_vars[source].set(bool(cfg.get("enabled", False)))
            if source in self.source_weight_vars:
                w = cfg.get("weight", 1.0)
                self.source_weight_vars[source].set(f"{float(w):.3f}")

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
        schema_keys_path = os.path.join(graph_config_dir, "schema_keys.json")
        schema_keys = self._generate_condensed_schema()
        try:
            with open(schema_keys_path, "w", encoding="utf-8") as f:
                json.dump(schema_keys, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {schema_keys_path}: {e}")


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
            # Clamp to [0.0, 1.0]
            weight = max(0.0, min(1.0, weight))
            sources_cfg[source] = {"enabled": enabled, "weight": weight}
        try:
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump(sources_cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not save {sources_path}: {e}")

        # After saving, ensure missing keys from defaults are appended
        self._apply_default_keys(graph_config_dir)

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
            # For other extensions, we do nothing (entity_list.ini is line-based).

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
        import configparser

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
    # LLM schema generation
    # ------------------------------------------------------------------
    def on_generate_schema_clicked(self):
        """
        Generate sample JSON schema with per-entity, per-attribute,
        and per-relationship confidence scores.
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
                ("vtuber", ["name", "debut_date", "agency"]),
            ]
        if not edge_types:
            edge_types = [
                ("belongs_to", "vtuber", "agency", ["notes"]),
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
                "confidence": 0.88  # relationship-level
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

        # ---------------------------------------------------------------
        # Parse node definitions (entities)
        # ---------------------------------------------------------------
        for line in nodes_spec:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue

            node_type, rest = line.split(":", 1)
            node_type = node_type.strip()
            attributes = [a.strip() for a in rest.split(",") if a.strip()]

            # Build attributes with confidence
            attr_obj = {
                attr: {
                    "value": "",
                    "confidence": 0.0
                }
                for attr in attributes
            }

            entities_schema[node_type] = {
                "attributes": attr_obj,
                "confidence": 0.0
            }

        # ---------------------------------------------------------------
        # Parse edge definitions (relationships)
        # ---------------------------------------------------------------
        for line in edges_spec:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            relation = None
            src_type = None
            tgt_type = None
            props = []

            # Extract relation
            if ":" in line:
                relation_part, rest = line.split(":", 1)
                relation = relation_part.strip()
            else:
                rest = line

            # Extract properties
            if "|" in rest:
                src_tgt_part, props_part = rest.split("|", 1)
                props = [p.strip() for p in props_part.split(",") if p.strip()]
            else:
                src_tgt_part = rest

            # Extract source → target
            if "->" in src_tgt_part:
                s, t = src_tgt_part.split("->", 1)
                src_type = s.strip()
                tgt_type = t.strip()

            if not (relation and src_type and tgt_type):
                continue

            # Build property object with value + confidence
            prop_obj = {
                p: {
                    "value": "",
                    "confidence": 0.0
                }
                for p in props
            }

            # Final relationship schema
            relationships_schema[relation] = {
                "source_type": src_type,
                "target_type": tgt_type,
                "properties": prop_obj,
                "confidence": 0.0
            }

        # ---------------------------------------------------------------
        # Final composed schema
        # ---------------------------------------------------------------
        condensed = {
            "entities": entities_schema,
            "relationships": relationships_schema
        }

        return condensed


def main():
    root = tk.Tk()
    app = KGConfigEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
