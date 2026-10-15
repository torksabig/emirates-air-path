#!/usr/bin/env python3
"""Generate Aether Applied Qorina flight-routing case study PDF (EGA-style layout)."""

from pathlib import Path

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Flowable,
    KeepTogether,
    Image,
)

OUT = Path(__file__).resolve().parent / "Qorina_Flight_Routing_Case_Study.pdf"
ASSET_LADDER = Path(__file__).resolve().parent / "_assets" / "value_ladder.png"

# Palette: professional navy (not McKinsey/EGA blue copy)
NAVY = HexColor("#0B1F3A")
ACCENT = HexColor("#1B4F8A")
LIGHT = HexColor("#F4F6F9")
MUTED = HexColor("#4A5568")
RULE = HexColor("#D0D7E2")
CALLOUT_BG = HexColor("#EEF2F7")
CALLOUT_BORDER = HexColor("#1B4F8A")


class MetricBlock(Flowable):
    """Large number + caption, EGA impact-style."""

    def __init__(self, value, caption, width=2.35 * inch, height=1.05 * inch):
        Flowable.__init__(self)
        self.value = value
        self.caption = caption
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(LIGHT)
        self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        self.canv.setFillColor(ACCENT)
        self.canv.setFont("Times-Bold", 20)
        self.canv.drawString(10, self.height - 30, self.value)
        self.canv.setFillColor(MUTED)
        words = self.caption.split()
        line = ""
        y_lines = []
        for w in words:
            trial = (line + " " + w).strip()
            if self.canv.stringWidth(trial, "Helvetica", 8) < self.width - 18:
                line = trial
            else:
                y_lines.append(line)
                line = w
        if line:
            y_lines.append(line)
        y = self.height - 48
        for ln in y_lines[:3]:
            self.canv.setFont("Helvetica", 8)
            self.canv.drawString(10, y, ln)
            y -= 11


def styles():
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            name="DocTitle",
            fontName="Times-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            name="DocSubtitle",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            name="BrandLine",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=ACCENT,
            spaceAfter=14,
        )
    )
    s.add(
        ParagraphStyle(
            name="SectionHead",
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            name="LeadIn",
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=black,
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            name="BodyTight",
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=black,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=black,
        )
    )
    s.add(
        ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=white,
        )
    )
    s.add(
        ParagraphStyle(
            name="CalloutTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=NAVY,
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            name="CalloutBody",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=MUTED,
            spaceAfter=2,
        )
    )
    s.add(
        ParagraphStyle(
            name="Footer",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
        )
    )
    s.add(
        ParagraphStyle(
            name="LessonTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=NAVY,
            spaceAfter=3,
        )
    )
    s.add(
        ParagraphStyle(
            name="LessonBody",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=black,
        )
    )
    return s


def two_col_section(lead, body_paras, sty, lead_width=1.85 * inch):
    """EGA-like: bold lead-in left, body right."""
    left = Paragraph(lead, sty["LeadIn"])
    right = Paragraph("<br/><br/>".join(body_paras), sty["BodyTight"])
    data = [[left, right]]
    t = Table(data, colWidths=[lead_width, 5.35 * inch - lead_width])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def callout_box(sty):
    title = Paragraph("What this does not claim", sty["CalloutTitle"])
    items = [
        "Not airline live operations or a production dispatch tool.",
        "Not a replacement for certified operational flight plans (OFP).",
        "Not proven network-wide airline savings.",
        "Not quantum hardware advantage (GPU simulation of ~14 qubits).",
        "Not automatic decision-making; a human decides.",
    ]
    rows = [[title]]
    for it in items:
        rows.append([Paragraph("•  " + it, sty["CalloutBody"])])
    t = Table(rows, colWidths=[6.5 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CALLOUT_BG),
                ("BOX", (0, 0), (-1, -1), 1.25, CALLOUT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (0, 0), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        )
    )
    return t


def comparison_table(sty):
    header = [
        Paragraph("Forecast age", sty["TableHeader"]),
        Paragraph("Qorina vs wind-blind", sty["TableHeader"]),
        Paragraph("Share of available saving", sty["TableHeader"]),
        Paragraph("Notes", sty["TableHeader"]),
    ]
    rows_raw = [
        ("21 days", "~291 kg", "~34%", "Fuel saved on 9 of 10 days"),
        ("10 days", "~430 kg", "~50%", "Best method in this small sample"),
        ("4 days", "~492 kg", "~57%", "Steady rise with fresher forecasts"),
        ("Freshest", "~555 kg", "~65%", "Exact opt leads (~97% capture)"),
    ]
    data = [header]
    for a, b, c, d in rows_raw:
        data.append(
            [
                Paragraph(a, sty["TableCell"]),
                Paragraph(b, sty["TableCell"]),
                Paragraph(c, sty["TableCell"]),
                Paragraph(d, sty["TableCell"]),
            ]
        )
    t = Table(data, colWidths=[1.1 * inch, 1.55 * inch, 1.7 * inch, 2.15 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT),
                ("BACKGROUND", (0, 3), (-1, 3), LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def yardstick_table(sty):
    header = [
        Paragraph("Yardstick", sty["TableHeader"]),
        Paragraph("Observed result", sty["TableHeader"]),
        Paragraph("Why it matters", sty["TableHeader"]),
    ]
    rows = [
        (
            "Wind-blind plan",
            "~291-555 kg saved as the forecast gets fresher; 9/10 days",
            "Baseline showing why wind-aware routing matters",
        ),
        (
            "Exact optimisation on forecast",
            "Wins when freshest (~97% vs Qorina ~65%); Qorina competitive / best at ~10 days (small sample)",
            "Today's strong fresh-forecast bar",
        ),
        (
            "MLP / Set Transformer",
            "On par at ~10.5-day winter set (~1.07-1.18% above theoretical optimum)",
            "Fair classical model comparison",
        ),
        (
            "Hindsight optimum",
            "Ceiling using weather known after the fact",
            "Upper bound, not a live operating target",
        ),
    ]
    data = [header]
    for a, b, c in rows:
        data.append(
            [
                Paragraph(a, sty["TableCell"]),
                Paragraph(b, sty["TableCell"]),
                Paragraph(c, sty["TableCell"]),
            ]
        )
    t = Table(data, colWidths=[1.55 * inch, 2.85 * inch, 2.1 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BACKGROUND", (0, 2), (-1, 2), LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def add_page_decor(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(2)
    canvas.line(
        0.75 * inch,
        letter[1] - 0.45 * inch,
        letter[0] - 0.75 * inch,
        letter[1] - 0.45 * inch,
    )
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(0.75 * inch, 0.45 * inch, "Aether Applied  ·  Qorina case study")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.45 * inch, str(doc.page))
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.58 * inch, letter[0] - 0.75 * inch, 0.58 * inch)
    canvas.restoreState()


def build():
    sty = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title="Qorina Flight Route Optimisation - Aether Applied Case Study",
        author="Aether Applied",
    )

    story = []

    story.append(Paragraph("Qorina flight route optimisation", sty["DocTitle"]))
    story.append(
        Paragraph("Wind-aware routing under forecast uncertainty", sty["DocSubtitle"])
    )
    story.append(
        Paragraph(
            "AN AETHER APPLIED CASE STUDY  ·  LHR → JFK PROOF OF CONCEPT",
            sty["BrandLine"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=10))

    story.append(Paragraph("The opportunity", sty["SectionHead"]))
    story.append(
        two_col_section(
            "Long-haul fuel still depends on imperfect weather",
            [
                "Airlines already plan wind-aware routes. The harder question is whether the forecast available before departure is trustworthy enough to act on.",
                "On a busy North Atlantic city pair, a path that looks optimal on a stale forecast can lose the advantage, or reverse it. Forecast age, ensemble disagreement, and comparison choice therefore belong in the fuel conversation, not only path geometry.",
                "Aether Applied set out to test whether Qorina, a quantum-inspired decision model, could turn the forecast actually available before departure into a stable, inspectable route recommendation, with the human flight team keeping the final say.",
            ],
            sty,
        )
    )

    story.append(Paragraph("The challenge", sty["SectionHead"]))
    story.append(
        two_col_section(
            "Exact maths can look strong when the forecast is fresh, and fail when it is old",
            [
                "Certified flight planning already uses weather as an input. Classical learners can also be trained on the same fields. What the PoC needed to show was not a new map drawer, but an honest ranking against clear yardsticks: a wind-blind plan; exact optimisation on the forecast used for decisions; classical machine learning (MLP and Set Transformer) with the same inputs; and a hindsight optimum as a ceiling, not a live operating target.",
                "The trial had to stay advisory. It was not airline live operations, not a certified operational flight plan replacement, and not a claim of quantum hardware advantage.",
            ],
            sty,
        )
    )

    story.append(Paragraph("The approach", sty["SectionHead"]))
    story.append(
        Paragraph(
            "<b>One real route, real forecasts, frozen weights on unseen days.</b> "
            "Route: London Heathrow (LHR) to New York JFK on an Airbus A330-200. "
            "Weather truth: ECMWF ERA5. Forecasts: archived NOAA GFS and the 11-member GEFS ensemble, "
            "from three weeks ahead to the morning of departure. Execution: GPU simulation of an approximately "
            "14-qubit circuit (12 decision + 2 environment qubits); not quantum hardware. "
            "Evaluation used frozen weights on days and seasons never used for training.",
            sty["Body"],
        )
    )
    story.append(
        Paragraph(
            "Qorina encodes candidate lateral track, flight level, and Mach choices, with wind and procedural "
            "constraints, into the circuit. Forecast ensemble members are held as uncertainty inside the quantum state. "
            "Physics is the only hard veto: a move is refused only if the aircraft cannot fly it. "
            "Confidence and disagreement signals are logged for audit.",
            sty["Body"],
        )
    )

    story.append(Paragraph("The solution", sty["SectionHead"]))
    story.append(
        two_col_section(
            "Trust-checked path choice from the forecast available at the time",
            [
                "Value is created as a short ladder: forecast → trust check → path choice → fuel result. The human flight team decides whether to use the recommendation.",
                "The product framing is robust decision support under forecast uncertainty: show the fuel result against the right comparison, then leave the operational decision with people.",
            ],
            sty,
        )
    )
    if ASSET_LADDER.exists():
        story.append(Spacer(1, 6))
        story.append(Image(str(ASSET_LADDER), width=6.5 * inch, height=1.02 * inch))
        story.append(Spacer(1, 6))

    story.append(Paragraph("The results", sty["SectionHead"]))
    story.append(
        Paragraph(
            "<b>Measured savings vs wind-blind, with forecast age as the key condition.</b> "
            "On ten unseen days covering every season, with no retraining, Qorina saved fuel against a "
            "wind-blind plan at every forecast age tested, on 9 of 10 days.",
            sty["Body"],
        )
    )

    metrics = Table(
        [
            [
                MetricBlock("~291-555 kg", "Saving vs wind-blind by forecast age"),
                MetricBlock("9 / 10 days", "Fuel saved at every age tested"),
                MetricBlock("~97% vs ~65%", "Exact opt vs Qorina on freshest forecast"),
            ]
        ],
        colWidths=[2.2 * inch, 2.2 * inch, 2.2 * inch],
    )
    metrics.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(metrics)
    story.append(Spacer(1, 4))
    story.append(comparison_table(sty))
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "<b>Versus exact optimisation.</b> Exact optimisation wins when the forecast is freshest "
            "(about 97% of available saving versus about 65% for Qorina). At about 10 days, in this small sample, "
            "Qorina was competitive and was the best method tested.",
            sty["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Versus classical learners.</b> On a larger winter set of 35 unseen days with a roughly "
            "10.5-day-old forecast, Qorina was on par with an MLP and a Set Transformer "
            "(about 1.07-1.18% above the theoretical optimum).",
            sty["Body"],
        )
    )
    story.append(
        Paragraph(
            "All Qorina figures are GPU simulations. Quantum hardware was not used. Fuel is from a physics "
            "model of the A330-200, not airline fuel records. Ten days at the 10-day horizon is a small sample; "
            "intervals are indicative.",
            sty["Body"],
        )
    )

    story.append(Spacer(1, 4))
    story.append(
        KeepTogether(
            [
                Paragraph("Comparison ladder", sty["SectionHead"]),
                yardstick_table(sty),
            ]
        )
    )
    story.append(Spacer(1, 12))

    story.append(callout_box(sty))
    story.append(Spacer(1, 12))

    lesson_data = [
        [
            Paragraph("Close the fresh-forecast gap", sty["LessonTitle"]),
            Paragraph("Confirm the 10-day signal", sty["LessonTitle"]),
            Paragraph("Stay advisory", sty["LessonTitle"]),
        ],
        [
            Paragraph(
                "Aim at the bar exact optimisation sets on fresh forecasts (about 97% of available saving) "
                "with longer training and real operational restrictions trained in.",
                sty["LessonBody"],
            ),
            Paragraph(
                "The 10-day lead is indicative on a small all-season sample. A larger held-out set is the "
                "next proof step before firm claims at that horizon.",
                sty["LessonBody"],
            ),
            Paragraph(
                "A human decides. The case for partners is a trust-checked recommendation beside existing "
                "planning tools, not a certified OFP replacement or a network savings promise.",
                sty["LessonBody"],
            ),
        ],
    ]
    lessons = Table(lesson_data, colWidths=[2.15 * inch, 2.15 * inch, 2.15 * inch])
    lessons.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (0, -1), 0.5, RULE),
                ("BOX", (1, 0), (1, -1), 0.5, RULE),
                ("BOX", (2, 0), (2, -1), 0.5, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                Paragraph("Outlook", sty["SectionHead"]),
                lessons,
                Spacer(1, 12),
                Paragraph(
                    "For partners, the PoC already delivers a validated end-to-end pipeline on real flights, real weather, "
                    "and real archived forecasts; a measured picture of how forecast age changes the value of routing advice; "
                    "and an architecture that reached parity with established machine-learning methods in its first application, "
                    "with decisions that can be audited part by part.",
                    sty["Body"],
                ),
                Spacer(1, 8),
                HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=6),
                Paragraph(
                    "Source: Qorina flight-routing proof of concept (LHR→JFK, A330-200). "
                    "Aether Applied partner results. Indicative route-level evidence, not a network-wide operating result.",
                    sty["Footer"],
                ),
            ]
        )
    )

    doc.build(story, onFirstPage=add_page_decor, onLaterPages=add_page_decor)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
