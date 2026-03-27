const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak
} = require("docx");

// ─── Constants ───
const PAGE_W = 12240;
const MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9360

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellPad = { top: 60, bottom: 60, left: 100, right: 100 };

const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "2E5090" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };

function headerCell(text, width) {
  return new TableCell({
    borders: headerBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "2E5090", type: ShadingType.CLEAR },
    margins: cellPad,
    verticalAlign: "center",
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", font: "Arial", size: 20 })] })],
  });
}

function cell(text, width, opts = {}) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.shade ? { fill: opts.shade, type: ShadingType.CLEAR } : undefined,
    margins: cellPad,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({ text, font: "Arial", size: 20, bold: opts.bold, color: opts.color })],
    })],
  });
}

function row(...cells) {
  return new TableRow({ children: cells });
}

function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    children: [new TextRun({ text, font: "Arial" })],
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120 },
    alignment: opts.align,
    children: [new TextRun({ text, font: "Arial", size: 22, bold: opts.bold, italics: opts.italic, color: opts.color })],
  });
}

function richPara(runs, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120 },
    alignment: opts.align,
    numbering: opts.numbering,
    children: runs.map(r => new TextRun({ font: "Arial", size: 22, ...r })),
  });
}

function bulletItem(text, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Arial", size: 22 })],
  });
}

function richBullet(runs, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60 },
    children: runs.map(r => new TextRun({ font: "Arial", size: 22, ...r })),
  });
}

function codeBlock(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    indent: { left: 360 },
    children: [new TextRun({ text, font: "Consolas", size: 18, color: "333333" })],
  });
}

function spacer(pts = 120) {
  return new Paragraph({ spacing: { after: pts }, children: [] });
}

// ─── A-Family results table ───
const aCols = [1200, 1000, 1200, 1060, 1200, 1200, 2500];
const aColSum = aCols.reduce((a, b) => a + b, 0);

const aResults = [
  ["A1", "task_a", "0.938", "12", "settle", "context_0=0.90", "context_1=1.00"],
  ["A2", "task_a", "0.812", "6", "settle", "context_0=0.80", "context_1=0.83"],
  ["A3", "task_a", "0.857", "9", "settle", "context_0=0.83", "context_1=0.88"],
  ["A4", "task_a", "0.938", "22", "settle", "context_0=0.83", "context_1=1.00"],
];

const aTable = new Table({
  width: { size: aColSum, type: WidthType.DXA },
  columnWidths: aCols,
  rows: [
    row(
      headerCell("Scale", aCols[0]),
      headerCell("Task", aCols[1]),
      headerCell("Final Acc", aCols[2]),
      headerCell("Slices", aCols[3]),
      headerCell("Decision", aCols[4]),
      headerCell("Ctx 0", aCols[5]),
      headerCell("Ctx 1", aCols[6]),
    ),
    ...aResults.map((r, i) => {
      const shade = i % 2 === 0 ? undefined : "F2F6FA";
      const accColor = parseFloat(r[2]) >= 0.9 ? "1B7A3D" : parseFloat(r[2]) >= 0.8 ? "2E5090" : "B85C00";
      return row(
        cell(r[0], aCols[0], { bold: true, shade }),
        cell(r[1], aCols[1], { shade }),
        cell(r[2], aCols[2], { bold: true, color: accColor, shade }),
        cell(r[3], aCols[3], { align: AlignmentType.CENTER, shade }),
        cell(r[4], aCols[4], { color: "1B7A3D", shade }),
        cell(r[5], aCols[5], { shade }),
        cell(r[6], aCols[6], { shade }),
      );
    }),
  ],
});

// ─── B-Family results table ───
const bCols = [1200, 1000, 1200, 1060, 1200, 1200, 2500];
const bColSum = bCols.reduce((a, b) => a + b, 0); // 9360

const bResults = [
  ["B2S1", "task_a", "0.938", "7", "settle", "context_0=0.75", "context_1=1.00"],
  ["B2S1", "task_b", "0.938", "11", "settle", "context_0=0.83", "context_1=1.00"],
  ["B2S1", "task_c", "0.938", "8", "settle", "context_0=1.00", "context_1=0.92"],
  ["B2S2", "task_a", "0.812", "13", "settle", "context_0=0.83", "context_1=0.80"],
  ["B2S2", "task_b", "0.812", "4", "settle", "context_0=1.00", "context_1=0.70"],
  ["B2S2", "task_c", "0.875", "8", "settle", "context_0=1.00", "context_1=0.83"],
  ["B2S3", "task_a", "0.812", "5", "settle", "context_0=0.83", "context_1=0.80"],
  ["B2S3", "task_b", "0.938", "16", "settle", "context_0=0.83", "context_1=1.00"],
  ["B2S3", "task_c", "1.000", "6", "settle", "context_0=1.00", "context_1=1.00"],
  ["B2S4", "task_a", "1.000", "17", "settle", "context_0=1.00", "context_1=1.00"],
  ["B2S4", "task_b", "0.833", "24", "settle", "context_0=0.75", "context_1=0.86"],
  ["B2S4", "task_c", "1.000", "10", "settle", "context_0=1.00", "context_1=1.00"],
  ["B2S5", "task_a", "0.812", "18", "settle", "Settled above threshold", ""],
  ["B2S6", "task_a", "0.833", "194", "settle", "Settled above threshold", ""],
];

const bTable = new Table({
  width: { size: bColSum, type: WidthType.DXA },
  columnWidths: bCols,
  rows: [
    row(
      headerCell("Scale", bCols[0]),
      headerCell("Task", bCols[1]),
      headerCell("Final Acc", bCols[2]),
      headerCell("Slices", bCols[3]),
      headerCell("Decision", bCols[4]),
      headerCell("Ctx 0", bCols[5]),
      headerCell("Ctx 1", bCols[6]),
    ),
    ...bResults.map((r, i) => {
      const shade = i % 2 === 0 ? undefined : "F2F6FA";
      const accColor = parseFloat(r[2]) >= 0.9 ? "1B7A3D" : parseFloat(r[2]) >= 0.8 ? "2E5090" : "B85C00";
      return row(
        cell(r[0], bCols[0], { bold: true, shade }),
        cell(r[1], bCols[1], { shade }),
        cell(r[2], bCols[2], { bold: true, color: accColor, shade }),
        cell(r[3], bCols[3], { align: AlignmentType.CENTER, shade }),
        cell(r[4], bCols[4], { color: "1B7A3D", shade }),
        cell(r[5], bCols[5], { shade }),
        cell(r[6], bCols[6], { shade }),
      );
    }),
  ],
});

// ─── C-Family results table ───
const cCols = [1200, 1000, 1200, 1060, 1200, 1200, 2500];

const cResults = [
  ["C3S1", "task_a", "0.812", "181", "settle", "ctx_0=0.83", "ctx_1=0.80"],
  ["C3S2", "task_a", "0.938", "17", "settle", "ctx_0=1.00", "ctx_1=0.90"],
  ["C3S3", "task_a", "0.812", "80", "settle", "ctx_0=0.75", "ctx_1=1.00"],
  ["C3S4", "task_a", "0.556", "500", "continue", "ctx_0=0.50", "ctx_1=0.62"],
];

const cTable = new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: cCols,
  rows: [
    row(
      headerCell("Scale", cCols[0]),
      headerCell("Task", cCols[1]),
      headerCell("Final Acc", cCols[2]),
      headerCell("Slices", cCols[3]),
      headerCell("Decision", cCols[4]),
      headerCell("Ctx 0", cCols[5]),
      headerCell("Ctx 1", cCols[6]),
    ),
    ...cResults.map((r, i) => {
      const shade = i % 2 === 0 ? undefined : "F2F6FA";
      const settled = r[4] === "settle";
      const accColor = parseFloat(r[2]) >= 0.9 ? "1B7A3D" : parseFloat(r[2]) >= 0.8 ? "2E5090" : "B85C00";
      const decColor = settled ? "1B7A3D" : "B85C00";
      return row(
        cell(r[0], cCols[0], { bold: true, shade }),
        cell(r[1], cCols[1], { shade }),
        cell(r[2], cCols[2], { bold: true, color: accColor, shade }),
        cell(r[3], cCols[3], { align: AlignmentType.CENTER, shade }),
        cell(r[4], cCols[4], { color: decColor, shade }),
        cell(r[5], cCols[5], { shade }),
        cell(r[6], cCols[6], { shade }),
      );
    }),
  ],
});

// ─── Misalignment table ───
const mCols = [3120, 3120, 3120];
const misalignments = [
  ["Hard max_slices cap on controller loop", "for-loop limited by pre-allocated slices", "while-True loop; only GCO STABLE triggers settlement"],
  ["Budget shrank when stalling", "Stalling multiplied budget by 0.75x", "Stalling grows budget 1.25x (system needs more time)"],
  ["Heuristic regulator owned termination", "Rule-based ESCALATE on DEGRADED/CRITICAL GCO", "Only REAL engine GCO trajectory can settle; no escalation on poor performance"],
  ["Pre-divided cycle budget", "Scenario cycles / max_slices = per-slice budget", "Budget is a simple integer; slices take what they need"],
  ["Consolidate policies shrunk budget", "budget_multiplier=0.75 on consolidate policies", "budget_multiplier=1.00; consolidation maintains effort"],
  ["Slices past schedule got no data", "No signal injection after original schedule ended", "Signal schedule wraps cyclically so learning continues"],
];

const mTable = new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: mCols,
  rows: [
    row(
      headerCell("Misalignment", mCols[0]),
      headerCell("Before (Broken)", mCols[1]),
      headerCell("After (TCL-Aligned)", mCols[2]),
    ),
    ...misalignments.map((r, i) => {
      const shade = i % 2 === 0 ? undefined : "F2F6FA";
      return row(
        cell(r[0], mCols[0], { bold: true, shade }),
        cell(r[1], mCols[1], { shade }),
        cell(r[2], mCols[2], { shade }),
      );
    }),
  ],
});

// ─── Files changed table ───
const fCols = [3600, 5760];
const files = [
  ["real_core/lamination.py", "Controller loop, HeuristicSliceRegulator budget logic, safety_limit"],
  ["real_core/meta_agent.py", "REALSliceRegulator GCO ownership, policy multipliers, observation adapter"],
  ["real_core/interfaces.py", "CoherenceModel.gco_status signature (state_after kwarg)"],
  ["real_core/engine.py", "Pass state_after to gco_status call"],
  ["phase8/lamination.py", "Removed cycles_remaining cap, signal schedule wrapping, safety_limit"],
  ["phase8/adapters.py", "gco_status signature alignment"],
  ["scripts/evaluate_laminated_phase8.py", "Removed _resolve_budget, --safety-limit CLI, compact output shows final acc, C-family support"],
  ["scripts/analyze_experiment_output.py", "Added safety_limit to metadata keys"],
  ["tests/test_lamination.py", "Removed max_slices from all LaminatedController tests"],
  ["tests/test_phase8_lamination.py", "safety_limit=10, removed stale baseline_summary assertion"],
  ["tests/test_real_core.py", "gco_status signature alignment"],
];

const fTable = new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: fCols,
  rows: [
    row(headerCell("File", fCols[0]), headerCell("Changes", fCols[1])),
    ...files.map((r, i) => {
      const shade = i % 2 === 0 ? undefined : "F2F6FA";
      return row(
        cell(r[0], fCols[0], { bold: true, shade }),
        cell(r[1], fCols[1], { shade }),
      );
    }),
  ],
});

// ─── Build document ───
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1A1A2E" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E5090" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "444444" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: 15840 },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E5090", space: 4 } },
          spacing: { after: 0 },
          children: [
            new TextRun({ text: "REAL Neural Substrate", font: "Arial", size: 18, color: "2E5090", bold: true }),
            new TextRun({ text: "    Lamination Alignment Report", font: "Arial", size: 18, color: "888888" }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 4 } },
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 16, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "888888" }),
          ],
        })],
      }),
    },
    children: [
      // ─── Title ───
      spacer(200),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
        children: [new TextRun({ text: "Temporal Constrain Lamination", font: "Arial", size: 48, bold: true, color: "1A1A2E" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
        children: [new TextRun({ text: "Theory-to-Implementation Alignment", font: "Arial", size: 36, color: "2E5090" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 40 },
        children: [new TextRun({ text: "REAL Neural Substrate Project", font: "Arial", size: 24, color: "666666" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 300 },
        children: [new TextRun({ text: "March 25, 2026", font: "Arial", size: 22, color: "888888" })],
      }),
      new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E5090", space: 1 } },
        spacing: { after: 200 },
        children: [],
      }),

      // ─── 1. Overview ───
      heading("1. Overview", HeadingLevel.HEADING_1),
      para("This document describes the alignment work performed on the Temporal Constrain Lamination (TCL) system within the REAL Neural Substrate. The implementation had drifted from the Phase 1 TCL theory in several ways that fundamentally undermined the design intent: the coupling between cycles and slices was too tight, termination was driven by counters rather than criteria, and the budget regulation was inverted."),
      para("Six specific misalignments were identified and corrected. After the fixes, all three benchmark families show strong results:"),
      bulletItem("A-family (topology scaling): 4/4 scales settled above 0.8 threshold (A1\u2013A4)"),
      bulletItem("B-family (hidden sequential dependence): 14/14 scale/task combinations settled above 0.8"),
      bulletItem("C-family (ambiguity resolution): 3/4 scales settled above 0.8; C3S4 represents a genuine capability boundary at this architecture scale"),

      // ─── 2. TCL Theory ───
      heading("2. TCL Theory Summary", HeadingLevel.HEADING_1),
      para("The Temporal Constrain Lamination theory defines a two-layer adaptive system:"),
      richBullet([
        { text: "Fast layer", bold: true },
        { text: " runs bounded exploration slices. Each slice executes the full REAL loop (observe, recognize, predict, select, execute, score, compare, consolidate) over multiple cycles." },
      ]),
      richBullet([
        { text: "Slow layer", bold: true },
        { text: " regulates via tilt (additive modulation), not reshape (parametric modulation). Tilt is robust to the timing delays inherent in cross-layer communication." },
      ]),
      richBullet([
        { text: "Termination is criteria-driven: ", bold: true },
        { text: "the system runs until the Global Coherence Observation (GCO) reaches STABLE consistently. There is no pre-allocated budget. If the problem isn\u2019t solved, the system keeps working." },
      ]),
      richBullet([
        { text: "Three constants ", bold: true },
        { text: "define an operating window for robust adaptive lamination: a timing ratio between layers, a coupling strength bound, and an information compression target." },
      ]),
      para("The key insight is that the slow layer should learn when to stop, not be told. The GCO tracks whether accuracy thresholds have been met across all contexts. Only sustained STABLE status triggers settlement.", { after: 200 }),

      // ─── 3. Misalignments ───
      heading("3. Misalignments Identified and Fixed", HeadingLevel.HEADING_1),
      para("Six misalignments between the TCL theory and the implementation were identified:"),
      spacer(60),
      mTable,
      spacer(120),

      heading("3.1 Controller Loop: Counters to Criteria", HeadingLevel.HEADING_2),
      richPara([
        { text: "The controller used a " },
        { text: "for", bold: true, font: "Consolas" },
        { text: " loop bounded by " },
        { text: "max_slices", bold: true, font: "Consolas" },
        { text: ", treating slice count as a hard budget. This was replaced with a " },
        { text: "while True", bold: true, font: "Consolas" },
        { text: " loop that only exits when the regulator issues a non-CONTINUE settlement decision (SETTLE, BRANCH). A " },
        { text: "safety_limit", font: "Consolas" },
        { text: " (default 200) exists solely as a development guard against infinite loops." },
      ]),

      heading("3.2 Budget Direction Reversal", HeadingLevel.HEADING_2),
      para("The heuristic regulator was shrinking the cycle budget (0.75x) when the system was stalling. This is backwards: a stalling system needs more time to explore, not less. The fix reverses the direction: stalling grows the budget 1.25x, while convergence maintains the current budget."),

      heading("3.3 GCO-Driven Termination Ownership", HeadingLevel.HEADING_2),
      para("The heuristic regulator was issuing ESCALATE decisions when it observed consecutive DEGRADED or CRITICAL GCO states. This is the opposite of the intended behavior: CRITICAL means the system hasn\u2019t solved the problem and should keep working. The fix removes all escalation logic from the GCO trajectory evaluation. Only consecutive STABLE states (meaning the accuracy threshold has been met across all contexts) trigger SETTLE. The slow-layer REAL engine owns this decision exclusively."),

      heading("3.4 Budget Pre-Division Removal", HeadingLevel.HEADING_2),
      richPara([
        { text: "The evaluation harness had a " },
        { text: "_resolve_budget()", font: "Consolas" },
        { text: " function that divided total scenario cycles by the number of slices to produce per-slice budgets. This was removed entirely. The " },
        { text: "--budget", font: "Consolas" },
        { text: " CLI parameter is now a simple integer (default 8), and the slow-layer regulator adjusts it dynamically based on observed performance." },
      ]),

      heading("3.5 Policy Budget Multiplier Correction", HeadingLevel.HEADING_2),
      richPara([
        { text: "Named policies with " },
        { text: "consolidate", font: "Consolas" },
        { text: " in their carryover filter had budget_multiplier=0.75, meaning consolidation was associated with reducing effort. This was changed to 1.00: consolidation should maintain the current effort level, not shrink it." },
      ]),

      heading("3.6 Signal Schedule Wrapping", HeadingLevel.HEADING_2),
      para("When slices ran past the original scenario\u2019s signal schedule, no new data was injected, causing accuracy to drop to zero. A wrapping mechanism was added: once the schedule is exhausted, it cycles back to the beginning, ensuring the system always has new examples to learn from."),

      new Paragraph({ children: [new PageBreak()] }),

      // ─── 4. Files Changed ───
      heading("4. Files Changed", HeadingLevel.HEADING_1),
      fTable,
      spacer(120),

      // ─── 5. Architecture After Changes ───
      heading("5. Architecture After Changes", HeadingLevel.HEADING_1),
      para("The post-alignment architecture works as follows:"),
      spacer(40),
      heading("5.1 Slice Execution Flow", HeadingLevel.HEADING_2),
      richPara([
        { text: "1. ", bold: true },
        { text: "LaminatedController enters a while-True loop." },
      ], { numbering: undefined }),
      richPara([
        { text: "2. ", bold: true },
        { text: "Each iteration runs one slice via Phase8SliceRunner, which executes cycle_budget REAL cycles with wrapped signal injection." },
      ]),
      richPara([
        { text: "3. ", bold: true },
        { text: "The slice produces a SliceSummary (accuracy, uncertainty, conflict, context breakdown, metadata)." },
      ]),
      richPara([
        { text: "4. ", bold: true },
        { text: "REALSliceRegulator observes the summary, runs one REAL engine cycle to select a policy, then checks GCO trajectory for settlement." },
      ]),
      richPara([
        { text: "5. ", bold: true },
        { text: "If GCO is STABLE for a consecutive window, SETTLE is issued and the loop exits. Otherwise, the regulatory signal (mode, carryover filter, budget, pressure) is applied and the next slice begins." },
      ]),

      heading("5.2 Cross-Slice State Preservation", HeadingLevel.HEADING_2),
      para("Between slices, the system now preserves substrate state across mode switches via the export_carryover/load_carryover mechanism. Before a mode switch rebuilds the NativeSubstrateSystem, each agent\u2019s carryover (substrate weights, consolidated memories, coherence history) is exported. After the rebuild, carryover is loaded into matching agents, so accumulated learning survives capability mode transitions."),
      para("Consolidation also runs at slice boundaries when memory grows large, compressing episodic entries into durable substrate state rather than simply discarding them."),

      heading("5.3 Slow-Layer Policy Space", HeadingLevel.HEADING_2),
      para("The REAL engine slow layer selects from named policies that bundle four control dimensions:"),
      richBullet([{ text: "capability_mode", bold: true, font: "Consolas" }, { text: ": which substrate mode to run (visible, growth-visible, latent-visible, etc.)" }]),
      richBullet([{ text: "carryover_filter", bold: true, font: "Consolas" }, { text: ": how aggressively to filter episodic memory between slices (keep, soften, consolidate, drop)" }]),
      richBullet([{ text: "budget_multiplier", bold: true, font: "Consolas" }, { text: ": scale factor for next-slice cycle budget (1.0\u20132.0)" }]),
      richBullet([{ text: "context_pressure", bold: true, font: "Consolas" }, { text: ": pressure label forwarded to the fast layer (normal, explore, exploit)" }]),
      para("Policy selection is learned: the engine\u2019s substrate accumulates support for (context, policy) pairs that produce accuracy improvements via the same bistable mechanism the fast layer uses for routing."),

      new Paragraph({ children: [new PageBreak()] }),

      // ─── 6. A-Family Results ───
      heading("6. Benchmark Results: A-Family (Topology Scaling)", HeadingLevel.HEADING_1),
      para("The A-family benchmark tests how the system scales with increasing topology size. A1 through A6 present progressively larger networks. All runs used the REAL slow-layer regulator with a 0.8 accuracy threshold and a safety limit of 500 slices."),
      spacer(60),
      aTable,
      spacer(120),

      heading("6.1 Key Observations", HeadingLevel.HEADING_2),
      richBullet([{ text: "100% settlement: ", bold: true }, { text: "All 4 scales settled above the 0.8 threshold." }]),
      richBullet([{ text: "Efficient scaling: ", bold: true }, { text: "A2 settled in just 6 slices; A4 (the largest tested) needed 22, showing the system allocates proportional effort without any hard cap." }]),
      richBullet([{ text: "Diverse policy usage: ", bold: true }, { text: "All four scales used a mix of growth_engage, growth_hold, growth_consolidate, and growth_reset. A4 also deployed growth_hold heavily (6 of 22 cycles), indicating the slow layer learned to stabilize during longer runs." }]),
      richBullet([{ text: "Strong context balance: ", bold: true }, { text: "Both contexts consistently above 0.8 across all scales, with several reaching 1.00 on context_1." }]),

      new Paragraph({ children: [new PageBreak()] }),

      // ─── 7. B-Family Results ───
      heading("7. Benchmark Results: B-Family (Hidden Sequential Dependence)", HeadingLevel.HEADING_1),
      para("The B-family benchmark tests hidden sequential dependence at increasing scale. B2S1 through B2S6 scale from small to large topologies. Tasks A, B, and C test different routing patterns within each scale. All runs used the REAL slow-layer regulator with a 0.8 accuracy threshold and a safety limit of 500 slices."),
      spacer(60),
      bTable,
      spacer(120),

      heading("7.1 Key Observations", HeadingLevel.HEADING_2),
      richBullet([{ text: "100% settlement: ", bold: true }, { text: "All 14 scale/task combinations settled above the 0.8 threshold." }]),
      richBullet([{ text: "Proportional effort: ", bold: true }, { text: "Smaller scales (S1\u2013S3) settled in 4\u201316 slices. Larger scales needed more: S4 took 10\u201324, S5 took 18, S6 took 194." }]),
      richBullet([{ text: "Diverse policies: ", bold: true }, { text: "The slow layer used growth_engage, growth_hold, growth_reset, growth_consolidate, and latent variants throughout runs, demonstrating genuine policy learning." }]),
      richBullet([{ text: "Context balance: ", bold: true }, { text: "Most settled runs show both contexts above 0.8, indicating the system learned to route correctly for both context patterns." }]),

      // ─── 8. C-Family Results ───
      heading("8. Benchmark Results: C-Family (Ambiguity Resolution)", HeadingLevel.HEADING_1),
      para("The C-family benchmark tests ambiguity resolution, where overlapping signal patterns must be disambiguated. C3S1 through C3S4 scale from 8 to 54 nodes. After wiring in cross-slice carryover preservation:"),
      spacer(60),
      cTable,
      spacer(120),

      heading("8.1 Key Observations", HeadingLevel.HEADING_2),
      richBullet([{ text: "3 of 4 settled: ", bold: true }, { text: "C3S1\u2013C3S3 all reached the 0.8 threshold and settled cleanly." }]),
      richBullet([{ text: "C3S4 plateau: ", bold: true }, { text: "Hit the 500-slice safety limit at 0.556 accuracy. The trajectory shows a stable plateau (0.50\u20130.65) rather than oscillation, indicating the system learned what it could but the topology (54 nodes, 103 edges) exceeds the routing architecture\u2019s disambiguation capacity at this scale." }]),
      richBullet([{ text: "Carryover impact: ", bold: true }, { text: "Before wiring in substrate preservation, C3S4 oscillated wildly (0.200\u20130.688). After carryover, the floor lifted to ~0.500 and stabilized. The improvement confirms that substrate state continuity matters for complex tasks." }]),
      richBullet([{ text: "Effort scales with difficulty: ", bold: true }, { text: "C3S2 settled in 17 slices but C3S1 needed 181, suggesting that certain topological structures are harder to disambiguate even at smaller scale." }]),

      new Paragraph({ children: [new PageBreak()] }),

      // ─── 8. Design Principles Validated ───
      heading("9. Design Principles Validated", HeadingLevel.HEADING_1),
      para("The alignment work validates several core TCL principles:"),
      spacer(40),
      heading("9.1 Criteria Over Counters", HeadingLevel.HEADING_2),
      para("Removing hard slice caps and letting GCO drive termination produced dramatically better results. The system naturally takes 5 slices for easy problems and 194 for hard ones. Pre-allocated budgets either waste time on easy problems or starve hard ones."),

      heading("9.2 Tilt, Not Reshape", HeadingLevel.HEADING_2),
      para("The slow layer communicates via bias (mode selection, context pressure, carryover filtering) rather than directly modifying fast-layer parameters. This is robust to the timing delay between layers and allows the fast layer to maintain its own internal coherence."),

      heading("9.3 Budget Grows Under Stress", HeadingLevel.HEADING_2),
      para("Reversing the budget direction (stalling = grow, not shrink) is critical. When a system is struggling, reducing its resources guarantees failure. The corrected logic gives stalling systems more cycles to explore, matching the biological principle that difficult problems require sustained attention."),

      heading("9.4 No Premature Termination", HeadingLevel.HEADING_2),
      para("Removing ESCALATE on DEGRADED/CRITICAL GCO states was essential. The old behavior would stop the system precisely when it most needed to continue. The only valid termination is success (sustained STABLE) or the development safety limit."),

      // ─── 9. Remaining Work ───
      heading("10. Remaining Work", HeadingLevel.HEADING_1),
      bulletItem("Benchmark A5 and A6 under lamination (larger topology scales, not yet tested)."),
      bulletItem("Investigate C3S4 capability boundary: may require larger substrate capacity or architectural changes to the routing disambiguation mechanism."),
      bulletItem("Tune GCO settle window size (currently requires consecutive STABLE states; optimal window may vary by task family)."),
      bulletItem("Benchmark cross-task transfer within laminated runs (e.g., train on task_a, transfer to task_b within the same laminated session)."),
      bulletItem("Profile computational cost vs. accuracy tradeoff across scale families."),
      bulletItem("Expand B-family and C-family to tasks B and C at larger scales (S5/S6 currently only have task_a results)."),

      spacer(200),
      new Paragraph({
        border: { top: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 8 } },
        spacing: { before: 200 },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "End of Report", font: "Arial", size: 20, color: "888888", italics: true })],
      }),
    ],
  }],
});

const outPath = process.argv[2] || "C:/Users/nscha/Coding/Relationally Embedded Allostatic Learning/REAL-Neural-Substrate/docs/reports/lamination_alignment_overview.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("Written to", outPath);
});
