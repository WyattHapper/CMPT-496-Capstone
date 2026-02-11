"""!
@file tree_parse.py
@brief Library for parsing files using tree-sitter.
@details Provides utility functions to traverse directories and convert source 
code into Abstract Syntax Trees (AST) using the Tree-sitter library.
"""

import tree_sitter_language_pack as tslp
from tree_sitter import Parser, Tree
from pathlib import Path
from dataclasses import dataclass

@dataclass
class CodeBundle:
    """!
    @brief Data container for a parsed source file.
    @param path The pathlib.Path of the source file.
    @param content The raw bytes of the file content.
    @param tree The tree_sitter.Tree object resulting from the parse.
    """
    path: Path
    content: bytes
    tree: Tree

def parse_file(filepath: Path, parser: Parser) -> CodeBundle:
    """!
    @brief Parses a specific file into a CodeBundle.
    @param filepath Path object representing the file to be parsed.
    @param parser An initialized tree_sitter.Parser instance for the target language.
    @return A CodeBundle instance containing the file metadata and AST.
    @exception TypeError Raised if inputs are not of the expected type.
    @exception FileNotFoundError Raised if the provided filepath does not exist.
    """
    # Validate inputs
    if not isinstance(filepath, Path):
        raise TypeError(f"Expected 'filepath' to be a pathlib.Path, got {type(filepath).__name__}")
    
    if not isinstance(parser, Parser):
        raise TypeError(f"Expected 'parser' to be a tree_sitter.Parser, got {type(parser).__name__}")
    
    if not filepath.exists():
        raise FileNotFoundError(f"Source file not found: {filepath}")
    
    # Parse file
    print(f"Parsing: {filepath}")
    code_bytes = filepath.read_bytes()
    ast = parser.parse(code_bytes)

    # Assemble bundle
    bundle = CodeBundle(path=filepath, content=code_bytes, tree=ast)

    return bundle

def parse_dir(dirpath: str) -> list[CodeBundle]:
    """!
    @brief Recursively parses all C# files within a given directory.
    @param dirpath String representing the path to the directory.
    @return A list of CodeBundle objects for all discovered .cs files.
    @exception TypeError Raised if dirpath is not a string.
    @exception NotADirectoryError Raised if the provided path is not a directory.
    
    @note Currently hardcoded to C#, may add additional language support in the future.
    """
    # Validate inputs
    if not isinstance(dirpath, str):
        raise TypeError(f"Expected 'dirpath' to be a string, got {type(dirpath).__name__}")

    # Create Path
    pathway = Path(dirpath)

    # Validate pathway is valid path
    if not pathway.is_dir():
        raise NotADirectoryError(f"The path {dirpath} is not a valid directory.")

    # Create Parser
    cs_lang = tslp.get_language("csharp")
    parser = Parser(cs_lang)
    bundle_list = []

    # Parse all files
    for file in pathway.rglob("*.cs"):
        bundle = parse_file(file, parser)
        bundle_list.append(bundle)

    return bundle_list