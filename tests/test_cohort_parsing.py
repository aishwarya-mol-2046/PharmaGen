import unittest

from backend.app.services.vcf_parser import VariantAnnotationEngine


def _vcf_bytes(rows):
    header = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    return header + "".join(rows).encode()


class CohortParsingTests(unittest.TestCase):
    """Same hotspot in DIFFERENT patients = distinct instances (kept).

    Only the same patient repeating an identical variant row is a true
    duplicate. CIViC KB multi-row evidence (disease/therapy/tier) is
    intentionally preserved upstream and is not affected here.
    """

    def test_cross_patient_recurrence_is_kept(self):
        content = _vcf_bytes(
            [
                "5\t1295228\t.\tG\tA\t.\tPASS\tGENE=TERT;MUT=G>A;SAMPLE=P-0000027\n",
                "5\t1295228\t.\tG\tA\t.\tPASS\tGENE=TERT;MUT=G>A;SAMPLE=P-0000056\n",
            ]
        )
        variants, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
        self.assertEqual(report["data_rows"], 2)
        self.assertEqual(report["parsed_rows"], 2)
        self.assertEqual(report["duplicate_rows"], 0)
        self.assertEqual(report["patients_observed"], 2)
        self.assertEqual(len(variants), 2)

    def test_same_patient_repeat_is_true_duplicate(self):
        content = _vcf_bytes(
            [
                "1\t1000\t.\tA\tT\t.\tPASS\tGENE=BRAF;MUT=V600E;SAMPLE=S1\n",
                "1\t1000\t.\tA\tT\t.\tPASS\tGENE=BRAF;MUT=V600E;SAMPLE=S1\n",
                "1\t1000\t.\tA\tT\t.\tPASS\tGENE=BRAF;MUT=V600E;SAMPLE=S2\n",
            ]
        )
        variants, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
        self.assertEqual(report["data_rows"], 3)
        self.assertEqual(report["parsed_rows"], 2)
        self.assertEqual(report["duplicate_rows"], 1)
        self.assertEqual(report["patients_observed"], 2)
        self.assertEqual(len(variants), 2)

    def test_unique_variant_combinations_counted(self):
        content = _vcf_bytes(
            [
                "7\t140453136\t.\tA\tT\t.\tPASS\tGENE=BRAF;MUT=V600E;SAMPLE=S1\n",
                "7\t55259515\t.\tC\tT\t.\tPASS\tGENE=EGFR;MUT=L858R;SAMPLE=S1\n",
            ]
        )
        _, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
        self.assertEqual(report["unique_variant_combinations"], 2)


if __name__ == "__main__":
    unittest.main()
