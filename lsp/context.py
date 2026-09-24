from pydantic import BaseModel, Field

from lsp.models import Definition, Reference

class CodeContext(BaseModel):
    """
    Represents the context of a code element, including its definition and references.

    Attributes:
        definition (Definition): The definition of the code element.
        references (list[Reference]): A list of references to the code element.
    """
    definitions: list[Definition] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)