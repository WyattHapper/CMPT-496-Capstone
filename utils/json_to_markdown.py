"""Convert file-summary JSON files into human-friendly Markdown.

Usage:
  python -m utils.json_to_markdown --input-dir agent/file_summary_agent_output

This script scans the input directory recursively for JSON files. For each
JSON file it finds (each representing a single-file summary), it generates a
Markdown file containing (when present):
- Filename
- File summary
- Imports/Dependencies
- Classes and their methods (with summaries, parameters, returns)

Empty or missing fields are omitted from the output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


def json_to_markdown(obj: Dict[str, Any]) -> str:
	lines: List[str] = []

	# Filename
	path = obj.get("path") or obj.get("filename") or obj.get("file")
	if path:
		# display only the basename, not the full path
		try:
			display_name = Path(path).name
		except Exception:
			display_name = str(path)
		lines.append("## Filename")
		lines.append("")
		lines.append(display_name)
		lines.append("")

	# File summary
	summary = obj.get("summary") or obj.get("description")
	if summary:
		lines.append("## File summary")
		lines.append("")
		lines.append(summary)
		lines.append("")

	# Imports / Dependencies
	deps = obj.get("dependencies") or obj.get("imports")
	if deps:
		deps_list = [d for d in deps if d]
		if deps_list:
			lines.append("## Imports/Dependencies")
			lines.append("")
			for d in deps_list:
				lines.append(f"- {d}")
			lines.append("")

	# Top-level functions
	funcs = obj.get("functions") or []
	if funcs:
		funcs = [f for f in funcs if f]
		if funcs:
			lines.append("## Functions")
			lines.append("")
			for f in funcs:
				name = f.get("name") or "<unnamed>"
				desc = f.get("description") or ""
				lines.append(f"### Function: {name}")
				lines.append("")
				if desc:
					lines.append(desc)
					lines.append("")
				params = f.get("parameters") or []
				if params:
					lines.append("- Parameters:")
					for p in params:
						lines.append(f"  - {p}")
					lines.append("")
				ret = f.get("return_type") or f.get("returns")
				if ret:
					lines.append(f"- Returns: {ret}")
					lines.append("")

	# Classes and their methods
	classes = obj.get("classes") or []
	if classes:
		classes = [c for c in classes if c]
		if classes:
			lines.append("## Classes")
			lines.append("")
			for c in classes:
				cname = c.get("name") or "<unnamed>"
				cdesc = c.get("description") or c.get("summary") or ""
				lines.append(f"### Class: {cname}")
				lines.append("")
				if cdesc:
					lines.append(cdesc)
					lines.append("")

				methods = c.get("methods") or []
				if methods:
					for m in methods:
						mname = m.get("name") or "<unnamed>"
						mdesc = m.get("description") or m.get("summary") or ""
						lines.append(f"#### Method: {mname}")
						lines.append("")
						if mdesc:
							lines.append(mdesc)
							lines.append("")
						params = m.get("parameters") or []
						if params:
							lines.append("- Parameters:")
							for p in params:
								lines.append(f"  - {p}")
							lines.append("")
						ret = m.get("return_type") or m.get("returns")
						if ret:
							lines.append(f"- Returns: {ret}")
							lines.append("")

				# visual separator between classes
				lines.append("---")
				lines.append("")

	# If nothing was added, return an empty string
	if not lines:
		return ""

	# Trim trailing separators
	while lines and lines[-1] == "":
		lines.pop()

	return "\n".join(lines)


def process_file(json_path: Path, input_dir: Path, out_dir: Path, to_stdout: bool = False, overwrite: bool = False) -> Optional[Path]:
	try:
		data = json.loads(json_path.read_text(encoding="utf-8"))
	except Exception as e:
		print(f"Skipping {json_path} (failed to parse JSON): {e}")
		return None

	# support either a single object or a list of objects
	items: List[Dict[str, Any]] = []
	if isinstance(data, dict):
		items = [data]
	elif isinstance(data, list):
		items = [i for i in data if isinstance(i, dict)]
	else:
		print(f"Skipping {json_path} (unexpected JSON root type: {type(data)})")
		return None

	created_paths: List[Path] = []
	for idx, item in enumerate(items):
		md = json_to_markdown(item)
		if not md:
			# nothing to write for this JSON object
			continue

		# choose filename based on the JSON filename stem (e.g. ConsoleTable-cs.json -> ConsoleTable-cs.md)
		if len(items) == 1:
			candidate_name = json_path.stem
		else:
			candidate_name = f"{json_path.stem}_{idx}"

		# place output in a mirrored directory structure under out_dir
		try:
			rel_parent = json_path.parent.relative_to(input_dir)
		except Exception:
			rel_parent = Path("")
		target_dir = out_dir / rel_parent
		out_path = target_dir / f"{candidate_name}.md"
		if out_path.exists() and not overwrite:
			# do not overwrite by default
			print(f"Skipping existing: {out_path} (use --overwrite to replace)")
			continue

		if to_stdout:
			sep = "\n" + ("=" * 80) + "\n"
			header = f"File: {out_path.name}\n\n"
			try:
				sys.stdout.buffer.write(sep.encode("utf-8"))
				sys.stdout.buffer.write(header.encode("utf-8"))
				sys.stdout.buffer.write((md + "\n").encode("utf-8"))
				sys.stdout.buffer.write(sep.encode("utf-8"))
			except Exception:
				# fallback to print (may raise encoding errors on some consoles)
				print(sep)
				print(header)
				print(md)
				print(sep)
		else:
			# ensure the mirrored target directory exists
			target_dir.mkdir(parents=True, exist_ok=True)
			out_path.write_text(md, encoding="utf-8")
			created_paths.append(out_path)

	return created_paths[0] if created_paths else None


def main() -> None:
	p = argparse.ArgumentParser(description="Convert file-summary JSONs to Markdown")
	p.add_argument("--input-dir", default="agent/file_summary_agent_output", help="Directory containing JSON summary files")
	p.add_argument("--output-dir", default=None, help="Directory to write Markdown files (defaults to <input-dir>/markdown)")
	# default to overwrite=True, allow opt-out with --no-overwrite
	p.add_argument("--overwrite", dest="overwrite", action="store_true", help="Overwrite existing markdown files (default: True)")
	p.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Do not overwrite existing markdown files")
	p.set_defaults(overwrite=True)
	p.add_argument("--stdout", action="store_true", help="Print results to stdout instead of files")
	p.add_argument("--ext", default=".json", help="File extension to search for (default: .json)")
	args = p.parse_args()

	input_dir = Path(args.input_dir)
	if not input_dir.exists():
		print(f"Input directory does not exist: {input_dir}")
		raise SystemExit(2)

	output_dir = Path(args.output_dir) if args.output_dir else input_dir / "markdown"

	json_files = list(input_dir.rglob(f"*{args.ext}"))
	if not json_files:
		print(f"No JSON files found under {input_dir}")
		return

	total = 0
	written = 0
	for jf in sorted(json_files):
		total += 1
		result = process_file(jf, input_dir, output_dir, to_stdout=args.stdout, overwrite=args.overwrite)
		if result:
			written += 1

	print(f"Processed {total} JSON files; wrote {written} Markdown files to {output_dir}")


if __name__ == "__main__":
	main()

