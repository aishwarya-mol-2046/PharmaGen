import { describe, expect, it } from "vitest";
import { aggregateCohort, highConfidenceCount, splitByMatch, topAlteredGenes } from "./utils";
import type { MatrixRow } from "./types";

const row = (over: Partial<MatrixRow> = {}): MatrixRow => ({
  gene: "BRAF", mutation: "V600E", chromosome: "7", disease: "Melanoma",
  targetedDrug: "Vemurafenib", evidenceLevel: "Level A",
  source: "CIViC Database", matchType: "exact", ...over,
});

describe("aggregateCohort", () => {
  it("collapses identical paths across patients and counts them", () => {
    const rows = [row(), row(), row({ gene: "EGFR", mutation: "L858R" })];
    const cohort = aggregateCohort(rows);
    expect(cohort).toHaveLength(2);
    expect(cohort[0].patients).toBe(2);
    expect(cohort[0].gene).toBe("BRAF");
  });

  it("returns empty for empty input", () => {
    expect(aggregateCohort([])).toEqual([]);
  });
});

describe("splitByMatch", () => {
  it("separates exact from contextual rows", () => {
    const { exact, contextual } = splitByMatch([
      row(),
      row({ matchType: "gene_context" }),
      row({ matchType: "none" }),
    ]);
    expect(exact).toHaveLength(1);
    expect(contextual).toHaveLength(1);
  });
});

describe("highConfidenceCount", () => {
  it("counts unique Level A/B exact biomarkers only", () => {
    const n = highConfidenceCount([
      row(),
      row(),
      row({ mutation: "G12D", evidenceLevel: "Level C" }),
      row({ gene: "BRCA1", matchType: "gene_context" }),
      row({ gene: "ALK", mutation: "G1202R", evidenceLevel: "Level B" }),
    ]);
    expect(n).toBe(2);
  });
});

describe("topAlteredGenes", () => {
  it("ranks genes by unique variant count", () => {
    const top = topAlteredGenes([
      row(), row({ mutation: "G469A" }), row({ gene: "TP53", mutation: "R273H" }),
    ]);
    expect(top[0]).toEqual(["BRAF", 2]);
    expect(top).toHaveLength(2);
  });
});
