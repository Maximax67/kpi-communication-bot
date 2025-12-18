from typing import BinaryIO

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.core.constants import GOOGLE_AUTH_SCOPES
from app.core.settings import settings

credentials = Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
    settings.SERVICE_ACCOUNT_FILE, scopes=GOOGLE_AUTH_SCOPES
)
drive_client = build("drive", "v3", credentials=credentials)


def download_file(
    file_id: str,
    out: BinaryIO,
    export_mime_type: str | None = None,
) -> None:
    if export_mime_type:
        request = drive_client.files().export_media(
            fileId=file_id, mimeType=export_mime_type
        )
    else:
        request = drive_client.files().get_media(fileId=file_id)

    file_content: bytes = request.execute()
    out.write(file_content)
