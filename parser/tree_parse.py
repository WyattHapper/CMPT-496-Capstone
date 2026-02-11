"""
File: tree_parse.py
Purpose: Library for parsing files using tree-sitter
"""
import tree_sitter_language_pack as tslp
from tree_sitter import Parser, Tree
from pathlib import Path
from dataclasses import dataclass

@dataclass
class CodeBundle:
    path: Path
    content: bytes
    tree: Tree

# parse file function
def parse_file(filepath: Path, parser: Parser) -> CodeBundle:
    """
    :parse_file function: Parses given file in given language
    :param filepath: Path - pathway to file you want to parse
    :param parser: Parser - Initialized parser for the given language
    :return: CodeBundle - dataclass containing path, bytes, and tree
    """
    # Validate inputs
    # Validate filepath is Path object
    if not isinstance(filepath, Path):
        raise TypeError(f"Expected 'filepath' to be a pathlib.Path, got {type(filepath).__name__}")
    
    # Validate parser is Parser object
    if not isinstance(parser, Parser):
        raise TypeError(f"Expected 'parser' to be a tree_sitter.Parser, got {type(parser).__name__}")
    
    # Validate path exists
    if not filepath.exists():
        raise FileNotFoundError(f"Source file not found: {filepath}")
    
    # If all inputs valid
    # Parse file
    print(f"Parsing: {filepath}")
    code_bytes = filepath.read_bytes()
    ast = parser.parse(code_bytes)

    # Assemble bundle
    bundle = CodeBundle(path=filepath, content=code_bytes, tree=ast)

    return bundle

# parse directory function
def parse_dir(dirpath: str) -> list[CodeBundle]:
    """
    :parse_dir function: Parses given directory
    :param dirpath: string - pathway to directory you want to parse
    :return: list - List of CodeBundles
    
    NOTE: Currently hardcoded to c_sharp, may add additional functionality later
    """
    # Validate inputs
    # Validate dirpath is String object
    if not isinstance(dirpath, str):
        raise TypeError(f"Exptected 'dirpath' to be a string, got {type(dirpath).__name__}")

    # Create Path
    pathway = Path(dirpath)

    # Validate pathway is valid path
    if not pathway.is_dir():
        raise NotADirectoryError(f"The path {dir_path} is not a valid directory.")

    # Create Parser
    cs_lang = tslp.get_language("c_sharp")
    parser = Parser(cs_lang)
    bundle_list = []

    # Parse all files
    for file in pathway.rglob("*.cs"):
        bundle = parse_file(file, parser)
        bundle_list.append(bundle)

    return bundle_list