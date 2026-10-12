# CarbonMint gauge reader v1: service

v1 packaged as a Docker container. Drop a zip of drone photos into a folder; the container reads every photo and
writes a JSON report to another folder. It keeps running, so the next zip is picked up the same way.

## Running it

You need Docker. From this folder:

    docker compose up -d --build

That creates two folders next to the compose file, `in` and `out`. Copy a zip into `in`. Once the copy has
finished (the file size stops changing), the container reads it, writes `out/<zipname>.report.json`, and moves
the zip to `in/done`. A zip it cannot read goes to `in/failed`, with `out/<zipname>.error.json` saying why. The
same zip dropped twice is read once (it is recognised by its SHA-256 fingerprint).

    docker compose logs -f      # watch it work
    docker compose down         # stop it

The 127-photo pilot zip (713 MB) takes about 4.5 minutes with one worker, peaking at about 520 MB of memory.

Without Docker: Python 3.11, `pip install -r requirements.txt`, then from this folder
`python -m gaugesvc run some.zip report.json`.

## What the zip should look like

One folder per visit, named `<checkpoint> - <ddmmyyHHMMSS>`, with that visit's photos inside:

    way points/
      AIT-CP-5286-2931-CKP K26 NG - 011026101600/
        dji_fly_..._photo.jpg
        dji_fly_..._photo.jpg

The folder keeps the two shots of a visit together so they can check each other. A photo outside a visit folder,
or in a folder of more than four photos, is read on its own (flag `no_twin_shot`). Only jpg and png files are
read; anything else is listed under `skipped`. Photos are read straight out of the zip and never unpacked. Names
that try to leave the zip's folder (`../`, absolute paths) are ignored. Zips with more than `MAX_IMAGES` photos
are refused.

## What is in the report

`examples/sample_report.json` is a real report trimmed to four visits; `report.schema.json` describes the shape.
A summary, then one entry per visit, then one per photo:

- `status`: `accepted`, `review` (not sure enough: no number is reported, `candidate_stripes` shows what a
  person should check), `no_gauge` or `error`.
- `stripes`: the stripe count, only for accepted photos. `0` with `dry: true` means the gauge is down: a dry
  field is a reading, not a failure.
- `confidence`: the trained model's probability that the count is exactly right. A photo is accepted at 0.7.
- `level_cm`, `level_vs_guide_cm`, `soil_state`: from the stripe count. The guide zero is 10 cm up the gauge;
  above +2 cm is Flooded, -2 to +2 Saturated, down to -12 Drying, below that Irrigate now.
- `gauge_box`: where the gauge was found, in photo pixels.
- `flags`: `no_twin_shot`, `twin_unreadable`, `colour_locator_used`, `bad_gauge`.
- Each visit has a `reading` (the mean of its accepted photos, the company's folder rule) and `consistent`
  (its accepted photos agree within 1 stripe).

## Settings

Set under `environment` in `docker-compose.yml`.

| Name | Default | |
|---|---|---|
| `POLL_SECONDS` | 10 | how often the `in` folder is checked |
| `CM_PER_STRIPE` | 1.0 | centimetres per stripe (an assumption until a gauge is measured) |
| `WORKERS` | 1 | visits read in parallel; each worker needs about 400 MB more |
| `MAX_IMAGES` | 5000 | the largest zip accepted, counted in photos |

## Tests

From the repo root:

    pip install -r service/requirements-dev.txt
    python -m unittest discover -s service/tests        # zips, limits, report schema, rules, watcher
    python service/tests/parity.py service/out/<zip>.report.json   # same answers as the research code
