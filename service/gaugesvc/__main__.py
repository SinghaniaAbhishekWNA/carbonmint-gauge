"""python -m gaugesvc watch                 watch IN_DIR for zips (the container's default command)
python -m gaugesvc run <zip> <report.json>  read one zip now
python -m gaugesvc health                exit 0 when the watch loop is alive (Docker HEALTHCHECK)"""
import json, sys
from . import batch, watch

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if cmd == "watch":
        watch.Watcher().forever()
    elif cmd == "run" and len(sys.argv) == 4:
        rep = batch.run(sys.argv[2])
        open(sys.argv[3], "w", encoding="utf-8").write(json.dumps(rep, indent=1, ensure_ascii=False))
        print(json.dumps(rep["summary"]))
    elif cmd == "health":
        sys.exit(0 if watch.healthy() else 1)
    else:
        sys.exit(__doc__)
