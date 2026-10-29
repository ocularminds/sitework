"""Create a true-size ArUco print sheet and a bench capture worksheet.

Run with SiteWork's OpenCV and ReportLab installed, or supply --grid-json
generated from OpenCV when using a separate document-authoring runtime.
"""

import argparse
import json
from pathlib import Path
from textwrap import wrap

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
INK = HexColor("#162e3a")
MUTED = HexColor("#50636b")
ACCENT = HexColor("#146c73")
LINE = HexColor("#c7d1d5")
WIDTH, HEIGHT = A4
LEFT = 20 * mm


def marker_grid(path: Path | None) -> list[list[int]]:
    if path:
        data = json.loads(path.read_text())
        if data["dictionary"] != "DICT_4X4_50" or data["id"] != 0:
            raise ValueError("This sheet requires DICT_4X4_50, ID 0.")
        grid = data["grid"]
    else:
        import cv2

        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(dictionary, 0, 600)
        grid = marker[50::100, 50::100].tolist()
    if len(grid) != 6 or any(len(row) != 6 for row in grid):
        raise ValueError("Expected six modules per side, including the black border.")
    if any(value not in (0, 255) for row in grid for value in row):
        raise ValueError("Marker modules must be black or white.")
    if any(grid[y][x] for y in range(6) for x in range(6)
           if x in (0, 5) or y in (0, 5)):
        raise ValueError("The marker requires a complete black outer border.")
    return grid


def text(c, x, y, value, size=10, font="Helvetica", color=INK):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, value)


def paragraph(c, x, y, value, width=94, size=10, leading=14):
    for line in wrap(value, width):
        text(c, x, y, line, size=size)
        y -= leading
    return y


def header(c, title, subtitle, page):
    text(c, LEFT, 278 * mm, "SITEWORK  /  BENCH PREPARATION", 9, "Helvetica-Bold", ACCENT)
    text(c, LEFT, 264 * mm, title, 24, "Helvetica-Bold")
    text(c, LEFT, 253 * mm, subtitle, 10, color=MUTED)
    c.setStrokeColor(LINE)
    c.line(LEFT, 245 * mm, WIDTH - LEFT, 245 * mm)
    text(c, LEFT, 12 * mm, "Calibration and capture worksheet - record actual observations.", 8, color=MUTED)
    text(c, WIDTH - 30 * mm, 12 * mm, f"{page} / 2", 8, color=MUTED)


def marker_page(c, grid):
    header(c, "40 mm ArUco marker", "DICT_4X4_50  |  ID 0  |  A4  |  Print at Actual Size / 100%", 1)
    paragraph(c, LEFT, 235 * mm,
              "Disable Fit, Shrink and Scale to printable area. Measure both outer black edges "
              "after printing: each must be 40.00 mm. Fix the print scaling and reprint if needed.")
    x, y, side = 85 * mm, 174 * mm, 40 * mm
    c.setStrokeColor(LINE)
    c.setDash(2, 3)
    c.rect(x - 10 * mm, y - 10 * mm, 60 * mm, 60 * mm, stroke=1, fill=0)
    c.setDash()
    c.setFillColor(black)
    c.rect(x, y, side, side, stroke=0, fill=1)
    c.setFillColor(white)
    cell = side / 6
    for row in range(6):
        for col in range(6):
            if grid[row][col] == 255:
                c.rect(x + col * cell, y + (5 - row) * cell, cell, cell, stroke=0, fill=1)
    text(c, 61 * mm, 155 * mm, "Cut outside the dotted line. Keep the 10 mm white border.", 9, color=MUTED)
    text(c, LEFT, 137 * mm, "CHECK THE PRINT SCALE", 10, "Helvetica-Bold", ACCENT)
    ruler_x, ruler_y = 55 * mm, 122 * mm
    c.setStrokeColor(black)
    c.setLineWidth(0.5)
    c.line(ruler_x, ruler_y, ruler_x + 100 * mm, ruler_y)
    for tick in range(11):
        x_tick = ruler_x + tick * 10 * mm
        height = (4 if tick in (0, 10) else 2) * mm
        c.line(x_tick, ruler_y - height, x_tick, ruler_y + height)
        text(c, x_tick - 2 * mm, ruler_y - 9 * mm, str(tick * 10), 8)
    text(c, 80 * mm, 103 * mm, "End-to-end length: 100.00 mm", 10, "Helvetica-Bold")
    text(c, LEFT, 86 * mm, "MOUNT AND RECORD", 10, "Helvetica-Bold", ACCENT)
    paragraph(c, LEFT, 77 * mm,
              "Mount on flat, matte, rigid card. Put the marker in the same plane as the "
              "surface being measured. Keep all four corners and the white border visible; "
              "avoid glare, bends and motion blur.")
    text(c, LEFT, 51 * mm, "Printed black width: __________ mm    Height: __________ mm", 10)
    text(c, LEFT, 39 * mm, "100 mm bar measured: __________ mm    Checked by: ____________________", 10)
    text(c, LEFT, 27 * mm, "Date: ____________________    Marker ID: 0    Dictionary: DICT_4X4_50", 10)
    c.showPage()


def capture_page(c):
    header(c, "Bench setup and capture", "Complete these physical steps, then record the measured ground truth below.", 2)
    tasks = [
        ("1  Calibrate", "Print and measure page 1. Mount the 40 mm marker flat beside the measured surface."),
        ("2  Decking boards", "Suggested angle targets: 0, 4 and 8 degrees. Set them with a protractor; "
         "measure and record actual angle and gap with a ruler or caliper."),
        ("3  Tabletop trench", "Suggested slope targets: 20, 35 and 50 degrees from horizontal. "
         "Build rigid model walls and record each actual measured slope."),
        ("4  Push-fit joint", "Use an unpressurized bench fixture. Mark the manufacturer's insertion depth. "
         "Record one deliberately unseated joint, then seat it correctly and keep the original audio."),
        ("5  Outdoor clips", "Record the corresponding surfaces with the marker visible in their measurement "
         "plane. Include daylight and a challenging condition such as shade or glare."),
    ]
    y = 232 * mm
    for title, body in tasks:
        c.setStrokeColor(MUTED)
        c.rect(LEFT, y - 1 * mm, 3.5 * mm, 3.5 * mm, stroke=1, fill=0)
        text(c, LEFT + 7 * mm, y, title, 11, "Helvetica-Bold")
        y = paragraph(c, LEFT + 7 * mm, y - 6 * mm, body, width=94, size=9.5, leading=12)
        y -= 6 * mm
    y = paragraph(c, LEFT, y,
                  "Capture 8-10 seconds per clean clip, including about 3 seconds around a joint-seating "
                  "event. Keep original files and audio. Suggested setpoints above are test fixtures, "
                  "not policy thresholds or measured results.", width=98, size=9, leading=12)
    y -= 5 * mm
    text(c, LEFT, y, "CAPTURE LOG - FILL WITH YOUR MEASUREMENTS", 10, "Helvetica-Bold", ACCENT)
    top = y - 5 * mm
    widths = [28, 26, 40, 48, 28]
    headings = ["Clip ID", "Scene", "Actual value + unit", "Condition / seat state", "File saved?"]
    x = LEFT
    c.setFillColor(HexColor("#eef4f4"))
    c.rect(LEFT, top - 8 * mm, sum(widths) * mm, 8 * mm, stroke=0, fill=1)
    for heading, width in zip(headings, widths):
        text(c, x + 2 * mm, top - 5.5 * mm, heading, 8, "Helvetica-Bold")
        x += width * mm
    bottom = top - (8 + 5 * 9) * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    x = LEFT
    for width in widths + [0]:
        c.line(x, top, x, bottom)
        x += width * mm
    for row in range(6):
        yy = top - (8 + row * 9) * mm
        c.line(LEFT, yy, WIDTH - LEFT, yy)
    text(c, LEFT, bottom - 8 * mm, "Clean inputs: data/clips/clean/     Outdoor originals: data/clips/outdoor/", 8, color=MUTED)
    c.showPage()


def write_svg(grid, path):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="60mm" viewBox="0 0 60 60">',
             '<title>DICT_4X4_50 ID 0, 40 mm black square with 10 mm white border</title>',
             '<rect width="60" height="60" fill="white"/>',
             '<rect x="10" y="10" width="40" height="40" fill="black"/>']
    for row in range(6):
        for col in range(6):
            if grid[row][col] == 255:
                parts.append(f'<rect x="{10 + col * 40 / 6:.9f}" y="{10 + row * 40 / 6:.9f}" '
                             f'width="{40 / 6:.9f}" height="{40 / 6:.9f}" fill="white"/>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts + ["</svg>", ""]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-json", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf/sitework-bench.pdf")
    args = parser.parse_args()
    grid = marker_grid(args.grid_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(args.output), pagesize=A4, pageCompression=1)
    c.setTitle("SiteWork - 40 mm ArUco marker and bench capture worksheet")
    c.setAuthor("SiteWork")
    c.setViewerPreference("PrintScaling", "None")
    marker_page(c, grid)
    capture_page(c)
    c.save()
    svg = ROOT / "output/bench/aruco-4x4-50-id0-40mm.svg"
    write_svg(grid, svg)
    print(args.output)
    print(svg)


if __name__ == "__main__":
    main()
