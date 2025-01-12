"""contains the scraper class"""

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Union

import aiohttp
from aiohttp import ClientTimeout
from efoli import get_edifact_format_version
from more_itertools import chunked

from edi_energy_scraper.apidocument import Document, ResponseModel
from edi_energy_scraper.utilities import _have_different_metadata

_logger = logging.getLogger(__name__)


class EdiEnergyScraper:
    """
    A class that uses beautiful soup to extract and download data from bdew-mako.de API.
    """

    def __init__(
        self,
        root_url: str = "https://www.bdew-mako.de",
        path_to_mirror_directory: Union[Path, str] = Path("edi_energy_de"),  # keep this path for legacy compatibility
        # HTML and PDF files will be stored relative to this
        connection_limit: int = 3,  # using trial and error this was found as a good value to not get blocked
    ):
        """
        Initialize the Scaper by providing the URL, a path to save the files to and a function that prevents DOS.
        """
        self._root_url = root_url.strip()
        if self._root_url.endswith("/"):
            # remove trailing slash if any
            self._root_url = self._root_url[:-1]
        if isinstance(path_to_mirror_directory, str):
            self._root_dir = Path(path_to_mirror_directory)
        else:
            self._root_dir = path_to_mirror_directory
        self.tcp_connector = aiohttp.TCPConnector(limit_per_host=connection_limit)
        self._session = aiohttp.ClientSession(connector=self.tcp_connector)
        self._timeout = ClientTimeout(total=30.0)

    async def get_documents_overview(self) -> list[Document]:
        """
        download meta information about all available documents
        """
        documents_response = await self._session.get(f"{self._root_url}/api/documents", timeout=self._timeout)
        response_body = await documents_response.json()
        response_model = ResponseModel.model_validate(response_body)
        return response_model.data

    def _remove_old_files(self, documents: list[Document]) -> None:
        """removes those files that are no longer available online"""
        all_downloaded_files = (f for f in self._root_dir.rglob("**/*") if f.is_file())
        all_recent_file_ids = {str(d.fileId) for d in documents}
        for downloaded_file in all_downloaded_files:
            file_id_of_downloaded_file = downloaded_file.stem.split("_")[-1]
            if file_id_of_downloaded_file not in all_recent_file_ids:
                _logger.debug("Removing %s", downloaded_file.absolute())
                downloaded_file.unlink()

    async def download_document(self, document: Document) -> Path:
        """
        downloads the file related to the given document and returns its path
        """
        format_version = get_edifact_format_version(document.validFrom)
        fv_path = self._root_dir / Path(format_version)
        if not fv_path.exists():
            _logger.debug("Creating directory %s", fv_path.absolute())
            fv_path.mkdir(exist_ok=True, parents=True)
        target_file_name = document.get_meaningful_file_name()
        tmp_target_file_name = document.get_meaningful_file_name() + ".tmp"
        file_path = fv_path / Path(target_file_name)
        tmp_file_path = fv_path / Path(tmp_target_file_name)
        response = await self._session.get(f"{self._root_url}/api/downloadFile/{document.fileId}")
        with open(tmp_file_path, "wb+") as downloaded_file:
            while chunk := await response.content.read(1024):
                downloaded_file.write(chunk)
        if file_path.exists() and file_path.suffix == ".pdf":
            _logger.debug("PDF file %s already exists. Checking metadata")
            if _have_different_metadata(file_path, tmp_file_path):
                _logger.debug("Metadata for %s differ. Overwriting...", file_path.absolute())
                file_path.unlink()
                tmp_file_path.replace(file_path)
            else:
                _logger.debug("Metadata for %s are the same. Nothing to do.", file_path.absolute())
                tmp_file_path.unlink()
        else:
            tmp_file_path.replace(file_path)
        _logger.debug("Successfully downloaded File with ID %i to %s", document.fileId, file_path.absolute())
        return file_path

    async def mirror(self) -> None:
        """
        Main method of the scraper.
        Downloads all the files and pages and stores them in the filesystem.
        """
        if not self._root_dir.exists() or not self._root_dir.is_dir():
            # we'll raise an error for the root dir, but create sub dirs on the fly
            raise ValueError(f"The path {self._root_dir} is either no directory or does not exist")
        download_tasks: list[Awaitable[Path]] = []
        all_metadata = await self.get_documents_overview()
        for document in all_metadata:
            if not document.isFree:
                _logger.debug("Skipping %s because it's not free", document.title)
                continue
            download_tasks.append(self.download_document(document))
        for download_chunk in chunked(download_tasks, 10):
            await asyncio.gather(*download_chunk)
        _logger.info("Downloaded %i files", len(download_tasks))
        self._remove_old_files(all_metadata)
        _logger.info("Finished mirroring")


__all__ = ["EdiEnergyScraper"]
