import networkx as nx
from pyvis.network import Network
import os

class KnowledgeGraphService:
    @staticmethod
    # Builds an interactive PyVis HTML graph from annotated clinical results
    def generate_interactive_html(annotated_results: list, output_html_path="frontend/graph.html"):
        net = Network(height="500px", width="100%", directed=True, bgcolor="#0e1117", font_color="white")
        
        # Color & Shape Schema
        COLOR_MAP = {
            "Gene": "#FF4B4B",
            "Mutation": "#FFAA00",
            "Disease": "#00C0F2",
            "Drug": "#00D47E"
        }

        for record in annotated_results[:10]:  # Limit top variants for clean visualization
            var = record["variant_info"]
            gene_id = f"Gene:{var['gene']}"
            mut_id = f"Mut:{var['gene']}_{var['mutation']}"
            
            net.add_node(gene_id, label=f"Gene: {var['gene']}", color=COLOR_MAP["Gene"], shape="ellipse", title="Target Gene")
            net.add_node(mut_id, label=f"Mut: {var['mutation']}", color=COLOR_MAP["Mutation"], shape="diamond", title="Somatic Variant")
            net.add_edge(gene_id, mut_id, label="HAS_MUTATION", color="#555555")
            
            for match in record["clinical_matches"][:3]:  # Top evidence only
                if match["disease"] != "No Direct Match":
                    disease_id = f"Disease:{match['disease']}"
                    drug_id = f"Drug:{match['therapy']}"
                    
                    net.add_node(disease_id, label=match['disease'], color=COLOR_MAP["Disease"], shape="box")
                    net.add_node(drug_id, label=match['therapy'], color=COLOR_MAP["Drug"], shape="star")
                    
                    net.add_edge(mut_id, disease_id, label="INDICATES", color="#777777")
                    net.add_edge(mut_id, drug_id, label=match['evidence_tier'], color="#00D47E")

        net.set_options("""
        var options = {
          "physics": {
            "barnesHut": { "gravitationalConstant": -8000, "springLength": 120 }
          }
        }
        """)
        
        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
        net.save_graph(output_html_path)
        return output_html_path