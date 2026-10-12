"""Gallery for the demo app: every photo with every method's reading -> data/gallery.json, plus a 1200 px copy of
each photo with ALL metadata stripped (DJI EXIF/XMP carries the field's GPS) -> media_private/photos/<id>.jpg.
media_private/ is served only to a signed-in user, never as a public static file."""
import csv, json
from pathlib import Path
from PIL import Image
import sys
sys.path.insert(0, ".")
from gauge.v1 import soil

W = 1200          # hosted function size limit (250 MB with numpy+scipy) sets this
OUT = Path("media_private/photos")


def public_comparison():
    c = json.load(open("data/comparison.json"))
    return {"v0": c["v0 (company, rebuilt)"], "Colour method": c["Colour method"], "v1": c["**v2**"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lab = {r["photo"]: r for r in csv.DictReader(open("data/labels.csv", newline=""))}
    reads = {r["photo"]: r for r in csv.DictReader(open("data/photo_reads_v2.csv", newline=""))}
    v0 = {r["photo"]: r for r in csv.DictReader(open("data/v0_reads.csv", newline=""))}
    v1 = {r["photo"]: r for r in csv.DictReader(open("data/v2_reads.csv", newline=""))}   # public v1 = current reader
    T = Path("methods/teammate")
    key = {int(r["idx"]): f'{r["checkpoint_folder"]}/{r["file"]}' for r in
           csv.DictReader(open(T / "sorted/visibility_labels.csv", encoding="utf-8"))}
    loc = {int(r["idx"]): r for r in csv.DictReader(open(T / "results/locate_method3final.csv"))}
    tm = {}
    for r in csv.DictReader(open(T / "results/rings_method3final.csv")):
        i = int(r["idx"])
        tm[key[i]] = dict(cm=None if r["state"] == "unreadable" else float(r["rings"] or 0),
                          accepted=loc[i]["state"] in ("colour", "found-visible") and r["state"] != "unreadable")
    items = []
    for k, (photo, l) in enumerate(lab.items()):
        pid = f"{k:03d}"
        src = Image.open("way points/" + photo).convert("RGB")
        sc = W / src.width
        dst = OUT / f"{pid}.jpg"
        if not dst.exists():
            clean = src.resize((W, round(src.height * sc)), Image.LANCZOS)
            clean.save(dst, quality=82, optimize=True)        # a fresh image: no EXIF, no XMP, no GPS
        r = reads[photo]
        f = lambda v: None if v in ("", None, "None") else float(v)
        items.append(dict(
            id=pid, plot=l["plot"], visit=l["visit"].rsplit(" - ", 1)[-1], date=r["date"], shot=int(l["shot"]),
            label=float(l["rings"]), label_conf=l["confidence"],
            v0=dict(cm=f(v0[photo]["cm"]), confidence=float(v0[photo]["confidence"]), accepted=v0[photo]["accepted"] == "True"),
            teammate=tm[photo],
            v1=dict(cm=f(v1[photo]["cm"]), confidence=float(v1[photo]["confidence_lopo"]), accepted=v1[photo]["accepted"] == "1",
                    note=v1[photo]["note"], state=soil(f(v1[photo]["cm"]))[1]),
            mark=None if f(r["first_y"]) is None or f(r["cx"]) is None else dict(
                x=round(f(r["cx"]) * sc), first=round(f(r["first_y"]) * sc), last=round(f(r["last_y"]) * sc),
                top=round(f(r["top_y"]) * sc) if f(r["top_y"]) is not None else None, half=round(f(r["half"]) * sc)),
            size=[W, round(src.height * sc)]))
    Path("data/gallery.json").write_text(json.dumps(dict(photos=items, comparison=public_comparison())))
    print(f"{len(items)} photos -> data/gallery.json, {OUT}")


if __name__ == "__main__":
    main()
