from typing import TypedDict, Deque

class GraphState(TypedDict):
    directory_path: str
    files: Deque[str] 
    #summary: SummaryOutput # need to creare object
    total_number_of_files: int
