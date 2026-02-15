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

    # extract namespace and imports
    file_namespace = get_namespace(bundle.tree.root_node)
    file_imports = "\n".join(get_imports(bundle.tree.root_node))

    # Prepare query
    lang = bundle.tree.language
    query = Query(lang, query_text)
    cursor = QueryCursor(query)

    # execute query
    matches = cursor.matches(bundle.tree.root_node)

    chunks = []
    properties = {}

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

            # check if node is a property and store in dict for later retrieval
            if chunk_node.type == "property_declaration":
                if parent_class not in properties:
                    properties[parent_class] = []
                properties[parent_class].append(code_text)
                continue # skip adding properties to chunks list for now

            chunk_info = {
                "name": name_text,
                "code": code_text,
                "class": parent_class,
                "file": str(bundle.path),
                "type": chunk_node.type,
                "start_line": chunk_node.start_point[0] + 1,
                "end_line": chunk_node.end_point[0] + 1,
                "language": bundle.language,
                "namespace": file_namespace,
                "imports": file_imports # unlikely to have duplicates but just in case
            }

            chunks.append(chunk_info)
    
    # Add properties to chunk list with associated class context
    for class_name, props in properties.items():
        merged_code = "\n".join(props)
        chunk_info = {
            "name": f"{class_name}_properties",
            "code": merged_code,
            "class": class_name,
            "file": str(bundle.path),
            "type": "property_declaration",
            "start_line": None, # properties may be non-contiguous, so line numbers are not applicable
            "end_line": None,
            "language": bundle.language,
            "namespace": file_namespace,
            "imports": "\n".join(sorted(set(file_imports)))
        }
        chunks.append(chunk_info)    

    return chunks

def get_class_name(node: Node) -> str:
    """!
    @brief Identifies the parent class name for a given AST node.
    @details Traverses upward from the provided node through its ancestors 
    until a 'class_declaration' node is found. It then extracts the text 
    from the class's identifier child. For embedded classes, it concatenates
    parent class names with a dot separator.
    
    @param node The tree_sitter.Node to start the upward search from.
    @return The name of the parent class as a string, or "Global" if no class is found.
    @exception TypeError Raised if the input node is not a tree_sitter.Node instance.
    """
    # Validate input
    if not isinstance(node, Node):
        raise TypeError(f"Expected 'node' to be a tree_sitter.Node, got {type(node).__name__}")
    
    class_name = []
    current = node.parent
    while current:
        if current.type == "class_declaration":
            # class name stored in identifier child node
            for child in current.children:
                if child.type == "identifier":
                    # add class name to list
                    class_name.append(child.text.decode("utf-8"))
                    break
        current = current.parent
    
    if not class_name:
        return "Global"
    
    # Reverse class_name list to get outermost class first and join with dot
    return ".".join(reversed(class_name))

def get_namespace(root: Node) -> str:
    """!
    @brief Extracts the namespace(s) from a C# source file.
    @details Scans the top-level children of the root node for traditional 
    or file-scoped namespace declarations. Extracts the identifier or 
    qualified name for each.
    
    @param root The tree_sitter.Node representing the root of the AST.
    @return A string of comma-separated namespaces, or "Global" if none found.
    @exception TypeError Raised if the input root is not a tree_sitter.Node.
    """
    # Validate input
    if not isinstance(root, Node):
        raise TypeError(f"Expected 'root' to be a tree_sitter.Node, got {type(root).__name__}")
    
    found_namespaces = []
    # check children of root for namespace declarations
    for child in root.children:
        if child.type in ["namespace_declaration", "file_scoped_namespace_declaration"]:
            # check for identifier or qualified_name child node
            for sub in child.children:
                if sub.type in ["identifier", "qualified_name"]:
                    found_namespaces.append(sub.text.decode("utf-8"))
                    break
                    
    if not found_namespaces:
        return "Global"
        
    # Usually just one, but this handles the edge case
    return ", ".join(found_namespaces)

def get_imports(root: Node) -> list[str]:
    """!
    @brief Extracts all 'using' directives from the file root.
    @details Identifies using_directive nodes and extracts their full text 
    literal to preserve aliases and static imports.
    
    @param root The tree_sitter.Node representing the root of the AST.
    @return A list of strings containing the raw 'using' statements.
    @exception TypeError Raised if the input root is not a tree_sitter.Node.
    """
    # Validate input
    if not isinstance(root, Node):
        raise TypeError(f"Expected 'root' to be a tree_sitter.Node, got {type(root).__name__}")
    
    imports = []
    # check children of root for using_directive
    for child in root.children:
        if child.type == "using_directive":
            # Don't look for identifiers since using directives can be complex
            imports.append(child.text.decode("utf-8"))
    return imports