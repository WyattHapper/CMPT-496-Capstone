"""
@file file_summary_output.py
@brief This file defines the FileSummaryOutput class, which is used to represent the structured output of a summary of a file's contents.
@details This file defines a nested structured output format for LLM summarization of a code file's contents, including separate classes for
function and class summaries
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

Visibility = Literal["public", "private", "protected"]
ParamDirection = Literal["in", "out", "inout"]
TypeKind = Literal["class", "enum", "interface", "struct"]
RelationshipType = Literal["inheritance", "association"]


class ParameterSummary(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a function parameter.
    """
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Parameter name.")
    type: Optional[str] = Field(None, description="Parameter type if known.")
    direction: ParamDirection = Field(..., description="Whether the parameter is input only (in), output only (out), or both read and modified (inout).")

class MethodSummary(BaseModel):
    """
    @brief Represents a method or constructor.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="The method name.")
    description: str = Field(..., description="A short description of what the method does.")
    visibility: Visibility = Field(None,description="Method visibility: public, private, or protected.")
    return_type: Optional[str] = Field(None,description="The return type if known.")
    parameters: list[ParameterSummary] = Field(default_factory=list,description="Parameters accepted by the method.")
    is_static: bool = Field(False,description="True if the method is static.")
    is_constructor: bool = Field(False,description="True if the method is a constructor.")

class FunctionSummary(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a function defined in a code file.
    """
    model_config = ConfigDict(extra="forbid")
    # Required fields
    name: str = Field(..., description="The name of the function.")
    description: str = Field(..., description="A concise description of what the function does.")
    parameters: list[ParameterSummary] = Field(default_factory=list, description="Parameters accepted by the function.")
    calls: list[str] = Field(default_factory=list, description="Other functions or methods called by this function.")

    # Optional fields
    visibility: Visibility = Field(None, description="Function/method visibility: public, private, or protected.")
    return_type: Optional[str] = Field(None, description="The return type, if known.")

class PropertySummary(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a class property/field.
    """
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="The property or field name.")
    type: Optional[str] = Field(None,description="The property or field type if known.")
    description: str = Field(...,description="A short description of the property or field.")
    visibility: Visibility = Field(None,description="Property visibility: public, private, or protected.")
    is_static: bool = Field(False,description="True if the property or field is static.")

class RelationshipSummary(BaseModel):
    """
    @brief Represents a UML relationship between two types.
    """
    model_config = ConfigDict(extra="forbid")
    source: str = Field(...,description="The source type in the relationship.")
    target: str = Field(...,description="The target type in the relationship.")
    relationship_type: RelationshipType = Field(...,description="The UML relationship type: inheritance or association.")

class TypeSummary(BaseModel):
    """
    @brief Represents a type defined in the file.
    """
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="The type name.")
    kind: TypeKind = Field(...,description="The kind of type: class, enum, interface, or struct.")
    description: str = Field(...,description="A short description of the type.")
    properties: list[PropertySummary] = Field(default_factory=list,description="Properties or fields defined in the type.")
    methods: list[MethodSummary] = Field(default_factory=list,description="Methods or constructors defined in the type.")
    enum_values: list[str] = Field(default_factory=list,description="Enum values if the type is an enum.")
    inherits_from: list[str] = Field(default_factory=list,description="Base classes this type inherits from.")
    plantuml: str = Field(...,description="Standalone PlantUML snippet describing this type.")

class BusinessRule(BaseModel):
    """
    @brief Represents a business rule extracted from source code.
    """
    model_config = ConfigDict(extra="forbid")
    rule: str = Field(..., description="A concise statement of a business rule implied by the code.")
    source_file: Optional[str] = Field(None, description="Source file path this rule was extracted from. Populated by agent code post-LLM call, not by the LLM.")

class FileSummaryOutput(BaseModel):
    """
    @brief Represents the structured summary of a source file.
    """
    model_config = ConfigDict(extra="forbid")
    path: str = Field(...,description="The path of the file being summarized.")
    summary: str = Field(...,description="A concise summary of the file contents.")
    dependencies: list[str] = Field(default_factory=list,description="External libraries and imports used in the file.")
    functions: list[FunctionSummary] = Field(default_factory=list,description="Top-level functions defined in the file.")
    types: list[TypeSummary] = Field(default_factory=list,description="Types defined in the file.")
    relationships: list[RelationshipSummary] = Field(default_factory=list,description="Relationships where both source and target types are defined in the file.")
    external_relationships: list[RelationshipSummary] = Field(default_factory=list,description="Relationships from types in this file to types defined outside the file.")
    relationship_plantuml: str = Field(...,description="Standalone PlantUML diagram showing all in-file types and their relationships.")
    business_rules: list[BusinessRule] = Field(default_factory=list, description="Business rules evidenced by code in this file.")