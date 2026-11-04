"""Stream selected sequences out of a remote GlareMOT zip on Google Drive without downloading the whole archive.

Zips (--zip): v2 = `GlareMOT2 full.zip` (218 GB, 119 seqs); v1 / v1synth = the real and synthetic-twin trees of
the old `GlareMOT_full.zip` (86 GB) that the paper numbers and our reference results were produced on.
Both are stored (uncompressed) public Google Drive files that answer HTTP Range requests. We read
only its central directory (zipfile over a ranged file object), pick the members we want, group members that sit
next to each other in the archive into ~group_mb chunks, and fetch each chunk with one ranged GET, writing the
members straight to disk (CRC-checked). Works the same locally and on a Colab VM; stdlib only.

Layout: v2 `GlareMOT2 full/{train,test}/<seq>/{images,mot,meta,labels,labels_all}/...` plus README.md,
split.json, {train,test}_sequences.txt (test is bytes 0-102 GB, train 102-218 GB). v1 `GlareMOT/<seq>/...` (real)
and `GlareMOT-Synth/<seq>/...` (twins). Seq dirs carry no _complete/_new suffix; --old_split adds them.

Examples:
  # paper Table I data: frozen test split (20 seqs) from the old zip, named as in glaremot/data/splits.json
  python scripts/24_fetch_glaremot.py --zip v1 --out datasets/real --old_split test --parts images,mot,meta
  # synthetic twins of the test split (Tables II-IV)
  python scripts/24_fetch_glaremot.py --zip v1synth --out datasets/synth --old_split test
  # GlareMOT2 official train split (71 seqs, 115 GB) for retraining on Colab
  python scripts/24_fetch_glaremot.py --zip v2 --out /content/glaremot2/train --split train --workers 8
  # just list what a selection would fetch
  python scripts/24_fetch_glaremot.py --zip v2 --out x --split test --dry_run
"""
import argparse
import io
import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# name -> (Drive file id, member prefix, has a {train,test} level under the prefix)
ZIPS = {
    "v2": ("1kUTdfRNbZzbwyl94JE--Vz8C5YVkzgms", "GlareMOT2 full/", True),
    "v1": ("1LEHAvE7r85UsUUdZcDeRONabZSUwxIt-", "GlareMOT/", False),
    "v1synth": ("1LEHAvE7r85UsUUdZcDeRONabZSUwxIt-", "GlareMOT-Synth/", False),
}


def drive_url(file_id):
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


class QuotaError(IOError):
    """Drive refused the range read (download quota). Transient: it lifted within an hour on 2026-11-03."""


# on a quota refusal, wait this long and try again (does not use up the network-error retries), for at most QUOTA_MAX_H
QUOTA_WAIT_S = float(os.environ.get("GMOT_QUOTA_WAIT_S", 600))
QUOTA_MAX_H = float(os.environ.get("GMOT_QUOTA_MAX_H", 24))


def http_range(url, start, end, timeout=120):
    """Open a ranged GET for bytes [start, end] (inclusive); returns the response object (a stream).

    With GDRIVE_TOKEN_FILE set (a file holding a short-lived OAuth access token, refreshed from outside), the read goes
    through the Drive API as that user instead of the anonymous download URL: the anonymous per-file quota then does
    not apply. The file is re-read on every request, so a refreshed token is picked up without a restart."""
    headers = {"Range": f"bytes={start}-{end}"}
    tok_file = os.environ.get("GDRIVE_TOKEN_FILE")
    if tok_file and "id=" in url:
        fid = url.split("id=")[1].split("&")[0]
        url = f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media&supportsAllDrives=true"
        headers["Authorization"] = "Bearer " + open(tok_file).read().strip()
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if tok_file and e.code in (401, 403, 429):      # stale token or API rate limit: wait for a fresh token / quota
            raise QuotaError(f"Drive API HTTP {e.code} for range {start}-{end}") from None
        raise
    if resp.status != 206:
        # Drive answers 200 + an HTML "Quota exceeded" page when the file's anonymous download quota is used up
        raise QuotaError(f"expected HTTP 206 for range {start}-{end}, got {resp.status}")
    return resp


class RangeFile(io.RawIOBase):
    """Seekable read-only view of a remote file, enough for zipfile to read the central directory."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        with http_range(url, 0, 0) as r:
            self.size = int(r.headers["Content-Range"].rsplit("/", 1)[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        with http_range(self.url, self.pos, self.pos + n - 1) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def load_index(url, cache):
    """[(name, file_size, header_offset, crc)] sorted by offset; cached as JSON (the central directory is ~80 MB)."""
    if cache and os.path.isfile(cache):
        return json.load(open(cache))
    t = time.time()
    with zipfile.ZipFile(RangeFile(url)) as z:
        ix = sorted(([i.filename, i.file_size, i.header_offset, i.CRC] for i in z.infolist()
                     if i.compress_type == zipfile.ZIP_STORED or i.file_size == 0), key=lambda e: e[2])
        bad = [i.filename for i in z.infolist() if i.compress_type != zipfile.ZIP_STORED and i.file_size]
    if bad:
        raise SystemExit(f"{len(bad)} compressed members (expected stored only), e.g. {bad[:3]}")
    print(f"[index] {len(ix)} members in {time.time() - t:.0f}s", flush=True)
    if cache:
        os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
        json.dump(ix, open(cache, "w"))
    return ix


def old_split_names(split):
    """Map numeric id -> sequence name in the frozen glaremot/data/splits.json (old names keep _complete/_new)."""
    names = json.load(open(os.path.join(ROOT, "glaremot", "data", "splits.json")))[split]
    return {s.split("_")[0]: s for s in names}


def select(ix, args):
    """Members to fetch as (name, size, offset, crc, local_path), plus the end offset of every member's data."""
    parts = set(args.parts.split(",")) if args.parts else None
    seqs = set(args.seqs.split(",")) if args.seqs else None
    rename = old_split_names(args.old_split) if args.old_split else None
    _, prefix, has_split = ZIPS[args.zip]
    out, ends = [], {}
    for k, (name, size, off, crc) in enumerate(ix):
        # the last member is followed by the central directory: header + name + data + max extra field
        ends[off] = ix[k + 1][2] if k + 1 < len(ix) else off + 30 + len(name.encode()) + size + 65535
        p = name[len(prefix):].split("/") if name.startswith(prefix) else []
        if not has_split:
            p = ["all"] + p
        if len(p) < 4 or name.endswith("/"):
            continue                                   # top-level files and directory entries
        split, seq, part = p[0], p[1], p[2]
        sid = seq.split("_")[0]
        if args.split != "all" and split != args.split and not rename:
            continue
        if seqs and seq not in seqs and sid not in seqs:
            continue
        if rename is not None:
            if sid not in rename:
                continue
            seq = rename[sid]
        if parts and part not in parts:
            continue
        out.append((name, size, off, crc, os.path.join(args.out, seq, *p[2:])))
    return out, ends


def groups(members, group_bytes):
    """Runs of members that are adjacent in the archive (no unselected member between), cut at ~group_bytes."""
    gs, cur, cur_bytes = [], [], 0
    for m in members:
        if cur and (m[2] != cur[-1][5] or cur_bytes >= group_bytes):
            gs.append(cur)
            cur, cur_bytes = [], 0
        cur.append(m)
        cur_bytes += m[1]
    if cur:
        gs.append(cur)
    return gs


def read_exact(r, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = r.read(min(n - len(buf), 1 << 20))
        if not chunk:
            raise IOError(f"stream ended early ({len(buf)}/{n})")
        buf += chunk
    return bytes(buf)


def done_already(m):
    return os.path.isfile(m[4]) and os.path.getsize(m[4]) == m[1]


def fetch_group(url, g, stats, lock, retries=6):
    todo = [m for m in g if not done_already(m)]
    attempt, quota_t0 = 0, None
    while True:
        if not todo:
            return
        start, end = todo[0][2], todo[-1][5] - 1
        try:
            with http_range(url, start, end, timeout=300) as r:
                pos = start
                for m in list(todo):
                    name, size, off, crc, path, _ = m
                    if off > pos:
                        read_exact(r, off - pos)       # skip a member that is already on disk
                        pos = off
                    hdr = read_exact(r, 30)
                    sig, _, _, _, _, _, _, _, _, nlen, elen = struct.unpack("<IHHHHHIIIHH", hdr)
                    if sig != 0x04034B50:
                        raise IOError(f"bad local header at {off} for {name}")
                    read_exact(r, nlen + elen)
                    data = read_exact(r, size)
                    if zlib.crc32(data) & 0xFFFFFFFF != crc:
                        raise IOError(f"CRC mismatch for {name}")
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    tmp = path + ".part"
                    with open(tmp, "wb") as f:
                        f.write(data)
                    os.replace(tmp, path)
                    pos = off + 30 + nlen + elen + size  # a data descriptor, if any, is skipped by the next gap read
                    todo.remove(m)
                    with lock:
                        stats["bytes"] += size
                        stats["files"] += 1
            return
        except QuotaError as e:                        # Drive quota: wait it out, then resume from the first missing member
            quota_t0 = quota_t0 or time.time()
            if time.time() - quota_t0 > QUOTA_MAX_H * 3600:
                raise
            print(f"[quota] {e}; waiting {QUOTA_WAIT_S / 60:.0f} min "
                  f"({(time.time() - quota_t0) / 3600:.1f} h so far)", flush=True)
            time.sleep(QUOTA_WAIT_S)
        except Exception as e:                         # network hiccup: resume this group from the first missing member
            if attempt == retries:
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
            attempt += 1
            print(f"[retry {attempt}] {type(e).__name__}: {e}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", required=True, choices=sorted(ZIPS), help="v2 = GlareMOT2 full; v1/v1synth = old zip")
    ap.add_argument("--out", required=True, help="destination root; files land at <out>/<seq>/<part>/...")
    ap.add_argument("--split", default="all", choices=["train", "test", "all"], help="GlareMOT2 official split (v2 only)")
    ap.add_argument("--old_split", choices=["train", "val", "test"],
                    help="instead select the frozen glaremot/data/splits.json split and use its seq names")
    ap.add_argument("--seqs", help="comma list of seq names or numeric ids (e.g. 127,136_sequence_2q)")
    ap.add_argument("--parts", help="comma list of per-seq subdirs to keep (images,mot,meta,labels,labels_all)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--group_mb", type=int, default=512)
    ap.add_argument("--index", help="central-directory cache (JSON); default cache/zipindex_<file id>.json, '' disables")
    ap.add_argument("--url", help="read the zip from this URL instead of the public Drive link, e.g. a local "
                                  "`rclone serve http` of an authenticated remote when the public link hits its quota")
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args()

    file_id = ZIPS[args.zip][0]
    args.url = args.url or drive_url(file_id)
    if args.index is None:
        args.index = os.path.join(ROOT, "cache", f"zipindex_{file_id}.json")
    ix = load_index(args.url, args.index)
    members, ends = select(ix, args)
    members = [m + (ends[m[2]],) for m in members]
    total = sum(m[1] for m in members)
    seqs = sorted({os.path.relpath(m[4], args.out).split(os.sep)[0] for m in members})
    print(f"[select] {len(members)} files, {total / 1e9:.2f} GB, {len(seqs)} seqs", flush=True)
    if args.dry_run:
        print("\n".join(seqs))
        return
    remaining = [m for m in members if not done_already(m)]
    print(f"[resume] {len(members) - len(remaining)} already present, {sum(m[1] for m in remaining) / 1e9:.2f} GB to go",
          flush=True)
    # groups are built over the full selection so adjacency holds; fetch_group skips files already on disk
    gs = [g for g in groups(members, args.group_mb << 20) if any(not done_already(m) for m in g)]
    stats, lock, t0 = {"bytes": 0, "files": 0}, threading.Lock(), time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(fetch_group, args.url, g, stats, lock) for g in gs]
        for k, f in enumerate(as_completed(futs), 1):
            f.result()
            dt = time.time() - t0
            print(f"[{k}/{len(gs)}] {stats['bytes'] / 1e9:.1f} GB, {stats['bytes'] / 1e6 / dt:.0f} MB/s", flush=True)
    missing = [m[4] for m in members if not done_already(m)]
    if missing:
        sys.exit(f"{len(missing)} files missing after fetch, e.g. {missing[:3]}")
    print(f"[done] {len(members)} files, {total / 1e9:.2f} GB in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
