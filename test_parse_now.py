from backend.app.services.vcf_parser import VariantAnnotationEngine
with open('old_vcf.vcf', 'rb') as f:
    v, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(f.read())
print(v[0]['mutation'])
