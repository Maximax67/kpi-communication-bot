from io import BytesIO
import pandas as pd
from openpyxl.utils import column_index_from_string

from app.core.google_drive import download_file


def excel_cols_to_positions(cols: list[str]) -> list[int]:
    return [column_index_from_string(c) - 1 for c in cols]


def load_spreadsheet(
    spreadsheet_id: str, sheet_name: str | None = None
) -> pd.DataFrame:
    buf = BytesIO()
    download_file(
        spreadsheet_id,
        buf,
        export_mime_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    buf.seek(0)
    file = pd.ExcelFile(buf)
    df = pd.read_excel(file, sheet_name, engine="openpyxl")
    file.close()

    if isinstance(df, dict):
        df = next(iter(df.values()))

    return df
