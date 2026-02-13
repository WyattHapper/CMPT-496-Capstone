"""!
@file tree_parse.py
@brief Library for parsing files using tree-sitter.
@details Provides utility functions to traverse directories and convert source 
code into Abstract Syntax Trees (AST) using the Tree-sitter library.
"""

import tree_sitter_language_pack as tslp
from tree_sitter import Parser, Tree, Node, Query, QueryCursor
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
    language: str = ""

def parse_file(filepath: Path, parser: Parser, language: str) -> CodeBundle:
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
    bundle = CodeBundle(path=filepath, content=code_bytes, tree=ast, language = language)

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
        bundle = parse_file(file, parser, "csharp")
        bundle_list.append(bundle)

    return bundle_list

def get_chunks(bundle: CodeBundle) -> list[dict]:
    """!
    @brief Selects and extracts semantic code blocks from a bundle based on a predefined query.
    @details Uses S-expression queries to identify method, constructor, and property 
    declarations. For each match, it extracts the source code, associated metadata, 
    and climbing context like the parent class name.
    
    @param bundle The CodeBundle instance containing the tree and source bytes.
    @return A list of dictionaries, each containing name, code, class, file, type, 
    line range, and language info.
    @exception TypeError Raised if the bundle or its internal attributes are of the incorrect type.
    
    @note This function specifically targets C# semantic structures (methods, constructors, properties).
    """
    # Validate CodeBundle attributes exist and are of the expected type
    if not isinstance(bundle, CodeBundle):
        raise TypeError(f"Expected 'bundle' to be a CodeBundle instance, got {type(bundle).__name__}")
    
    if not isinstance(bundle.path, Path):
        raise TypeError(f"Expected 'bundle.path' to be a pathlib.Path, got {type(bundle.path).__name__}")
    
    if not isinstance(bundle.content, bytes):
        raise TypeError(f"Expected 'bundle.content' to be bytes, got {type(bundle.content).__name__}")
    
    if not isinstance(bundle.tree, Tree):
        raise TypeError(f"Expected 'bundle.tree' to be a tree_sitter.Tree, got {type(bundle.tree).__name__}")
    
    if not isinstance(bundle.language, str):
        raise TypeError(f"Expected 'bundle.language' to be a string, got {type(bundle.language).__name__}")
    
    # define S-expression queries
    query_text = """
        (method_declaration name: (identifier) @name) @chunk
        (constructor_declaration name: (identifier) @name) @chunk
        (property_declaration name: (identifier) @name) @chunk
    """

    # Prepare query
    lang = bundle.tree.language
    query = Query(lang, query_text)
    cursor = QueryCursor(query)

    # execute query
    matches = cursor.matches(bundle.tree.root_node)

    chunks = []

    for pattern, captures in matches:
        # matches is a list of tuples
        chunk_node = captures.get("chunk")[0]
        name_node = captures.get("name")[0]

        if chunk_node and name_node:
            # Get parent class name by traversing up tree
            parent_class = get_class_name(chunk_node)

            # Extract text for name and code
            name_text = name_node.text.decode("utf-8")
            code_text = bundle.content[chunk_node.start_byte:chunk_node.end_byte].decode("utf-8")

            chunk_info = {
                "name": name_text,
                "code": code_text,
                "class": parent_class,
                "file": str(bundle.path),
                "type": chunk_node.type,
                "start_line": chunk_node.start_point[0] + 1,
                "end_line": chunk_node.end_point[0] + 1,
                "language": bundle.language
            }

            chunks.append(chunk_info)

    return chunks

def get_class_name(node: Node) -> str:
    """!
    @brief Identifies the parent class name for a given AST node.
    @details Traverses upward from the provided node through its ancestors 
    until a 'class_declaration' node is found. It then extracts the text 
    from the class's identifier child.
    
    @param node The tree_sitter.Node to start the upward search from.
    @return The name of the parent class as a string, or "Global" if no class is found.
    @exception TypeError Raised if the input node is not a tree_sitter.Node instance.
    """
    # Validate input
    if not isinstance(node, Node):
        raise TypeError(f"Expected 'node' to be a tree_sitter.Node, got {type(node).__name__}")
    
    current = node.parent
    while current:
        if current.type == "class_declaration":
            # class name stored in identifier child node
            for child in current.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        current = current.parent
    return "Global"