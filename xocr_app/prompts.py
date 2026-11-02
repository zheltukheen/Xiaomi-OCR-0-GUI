"""Official Xiaomi-OCR-0 prompts (same as the Demo / model README)."""

DOCUMENT_PROMPT = (
    "Extract all information from the main body of the document image and represent it "
    "in markdown format, ignoring headers and footers. Tables should be expressed in OTSL "
    "format, formulas in the document should be represented using LATEX format, and the "
    "parsing should be organized according to the reading order."
)

TEXT_PROMPT = "Extract the text in the image."

TABLE_PROMPT = "Parse the table in the image into OTSL."

FORMULA_PROMPT = "Identify the formula in the image and represent it in LATEX format."

VQA_HEADER = "Extract key information in the image"

VQA_TASK = "Ask a question (VQA)"

TASKS = [
    "Full document parsing",
    "Text only",
    "Recognize table",
    "Recognize formula",
    "Ask a question (VQA)",
]


def prompt_for_task(task: str, question: str = "") -> str:
    if task == "Text only":
        return TEXT_PROMPT
    if task == "Recognize table":
        return TABLE_PROMPT
    if task == "Recognize formula":
        return FORMULA_PROMPT
    if task == "Ask a question (VQA)":
        return question.strip() or VQA_HEADER
    return DOCUMENT_PROMPT
