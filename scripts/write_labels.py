"""Writes data/labels.csv: Claude-read silver labels (2026-10-10), read by eye from straightened full-res rod strips
with a pixel ruler (scripts/label_strips.py, label_profile.py, label_crops.py). rings = red rings above the sleeve,
including rings hidden by leaves (inferred from spacing; occluded=1). A ring cut by the sleeve counts 1 if more than
half of it shows, else 0 (whole rings; rule set by the user 2026-10-11 after spot-check round 1).
first/last = image y of the first (top) and last (bottom) ring centre. conf=low: blurred, far, or sleeve hidden."""
import csv

L = {  # k: (rings, first_y, last_y, occluded, conf, note)
 0: (19, 885, 1553, 1, "low", "sleeve hidden by rice heads"), 1: (20, 880, 1360, 1, "low", "rod tilted, lower part hidden"),
 2: (24, 922, 1888, 1, "high", ""), 3: (24, 845, 1808, 1, "high", ""), 4: (24, 1137, 2035, 1, "high", ""),
 5: (23, 1073, 1923, 1, "high", "fixed after human spot-check 2026-10-11 (was 24)"), 6: (16, 1232, 1838, 0, "high", ""), 7: (16, 1243, 1852, 0, "high", ""),
 8: (20, 1243, 1953, 1, "high", ""), 9: (20, 770, 1525, 1, "high", ""), 10: (22, 1305, 2060, 1, "low", "leaves across rod"),
 11: (22, 1300, 2060, 1, "low", "leaves across rod"), 12: (20, 922, 1650, 1, "high", ""), 13: (12, 663, 1003, 0, "high", ""),
 14: (12, 1055, 1503, 1, "high", ""), 15: (2, 1037, 1075, 0, "high", ""), 16: (2, 972, 1010, 0, "high", ""),
 17: (21, 950, 1640, 1, "high", ""), 18: (21, 1107, 1497, 1, "high", ""), 19: (4, 985, 1065, 0, "high", ""),
 20: (4, 1207, 1322, 0, "high", ""), 21: (24, 587, 1468, 0, "high", "fixed after human spot-check 2026-10-11 (was 25)"), 22: (24, 589, 1471, 0, "high", "fixed after human spot-check 2026-10-11 (was 25)"),
 23: (3, 805, 890, 0, "high", ""), 24: (3, 808, 893, 0, "high", ""), 25: (3, 607, 698, 0, "high", ""),
 26: (3, 573, 662, 0, "high", ""), 27: (3, 820, 880, 0, "high", ""), 28: (3, 780, 840, 0, "high", ""),
 29: (3, 918, 1025, 0, "high", ""), 30: (3, 893, 1000, 0, "high", ""), 31: (4, 893, 953, 0, "high", ""),
 32: (4, 1240, 1328, 0, "high", ""), 33: (4, 1258, 1402, 0, "high", ""), 34: (4, 1568, 1708, 0, "high", ""),
 35: (3, 803, 875, 0, "high", ""), 36: (3, 1170, 1227, 0, "high", ""), 37: (24, 688, 1470, 1, "high", ""),
 38: (23, 385, 1545, 1, "high", ""), 39: (22, 725, 1633, 1, "high", ""), 40: (22, 815, 1740, 1, "high", ""),
 41: (24, 548, 1860, 0, "high", ""), 42: (24, 538, 1848, 0, "high", ""), 43: (15, 653, 1515, 1, "high", ""),
 44: (15, 593, 1458, 1, "high", ""), 45: (22, 610, 1968, 1, "high", ""), 46: (22, 580, 1935, 1, "high", ""),
 47: (14, 1010, 1715, 1, "high", ""), 48: (14, 983, 1690, 1, "high", ""), 49: (13, 357, 705, 1, "high", ""),
 50: (9, 797, 1132, 1, "high", ""), 51: (9, 677, 1125, 0, "high", ""), 52: (10, 993, 1228, 1, "high", ""),
 53: (10, 828, 1290, 0, "high", ""), 54: (12, 980, 1340, 0, "high", ""), 55: (12, 1020, 1380, 0, "high", ""),
 56: (4, 1205, 1260, 0, "low", "blurred"), 57: (4, 1275, 1340, 0, "low", "blurred"), 58: (21, 560, 1285, 1, "high", ""),
 59: (21, 1197, 1935, 1, "high", ""), 67: (23, 955, 1525, 1, "high", ""), 68: (23, 1208, 1805, 1, "high", ""),
 69: (6, 830, 930, 0, "low", "blurred"), 70: (6, 1125, 1225, 0, "low", "blurred"), 71: (24, 1440, 1880, 0, "low", "far shot"),
 72: (24, 1340, 1860, 0, "low", "far shot"), 73: (24, 625, 1140, 0, "high", ""), 74: (24, 655, 1150, 1, "high", ""),
 77: (22, 742, 1290, 0, "high", ""), 78: (22, 725, 1278, 1, "high", ""), 79: (22, 752, 1305, 1, "high", ""),
 80: (22, 1150, 1745, 0, "high", ""), 81: (22, 1165, 1755, 0, "high", ""), 82: (24, 825, 1432, 1, "high", ""),
 83: (24, 820, 1430, 1, "high", ""), 84: (22, 683, 1210, 1, "high", ""), 85: (22, 665, 1197, 1, "high", ""),
 88: (19, 848, 1225, 1, "low", "motion blur"), 89: (19, 1250, 1610, 0, "low", "far shot"), 90: (23, "", "", 0, "low", "very far shot"),
 91: (23, 930, 1420, 0, "high", ""), 92: (23, 725, 1500, 1, "high", ""), 93: (24, 552, 1295, 1, "high", ""),
 94: (24, 365, 1110, 1, "high", ""), 95: (18, 508, 1058, 1, "high", ""), 96: (18, 972, 1525, 1, "high", ""),
 97: (3, 1307, 1380, 0, "high", ""), 98: (3, 1315, 1385, 0, "high", ""), 99: (3, 1487, 1563, 0, "high", ""),
 100: (3, 1507, 1583, 0, "high", ""), 101: (3, 1003, 1070, 1, "low", "weeds over lowest ring"),
 102: (25, 717, 1390, 1, "high", ""), 103: (22, 1050, 1478, 0, "high", ""), 104: (22, 880, 1290, 0, "high", ""),
 105: (9, 732, 1003, 0, "high", ""), 106: (9, 1017, 1265, 0, "high", ""), 107: (3, 922, 983, 0, "high", ""),
 108: (3, 1140, 1205, 0, "high", ""),
}
ZERO = [60, 61, 62, 63, 64, 65, 66, 75, 76, 86, 87] + list(range(109, 127))
LOWZ = {109: "rod behind rice head", 110: "rod behind rice head", 113: "dark, leaves", 114: "dark, leaves",
        115: "dark", 116: "dark", 119: "leaves", 120: "leaves", 123: "blurred", 124: "rod barely visible"}
for k in ZERO:
    L[k] = (0, "", "", 0, "low" if k in LOWZ else "high", LOWZ.get(k, "all grey: no ring above sleeve"))

rows = list(csv.DictReader(open("data/index.csv")))
assert sorted(L) == list(range(len(rows))), set(range(len(rows))) - set(L)
with open("data/labels.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["photo", "plot", "visit", "shot", "rings", "first_ring_y", "last_ring_y", "occluded", "confidence", "source", "note"])
    for k, r in enumerate(rows):
        n, a, b, occ, conf, note = L[k]
        w.writerow([r["photo"], r["plot"], r["visit"], r["shot"], n, a, b, occ, conf, "claude-silver", note])
print(len(rows), "labels;", sum(L[k][4] == "low" for k in L), "low-confidence")
