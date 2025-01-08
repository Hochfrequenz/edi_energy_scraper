import logging
from pathlib import Path
from typing import Union

import aiohttp
from efoli import get_edifact_format_version

from edi_energy_scraper import Document, ResponseModel

_logger = logging.getLogger(__name__)
class EdiEnergyScraper:
    """
    A class that uses beautiful soup to extract and download data from bdew-mako.de API.
    """

    def __init__(
        self,
        root_url: str = "https://www.bdew-mako.de",
        path_to_mirror_directory: Union[Path, str] = Path("edi_energy_de"),  # keep this path for legacy compatability
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

    def __del__(self):
        self._session.close()

    async def get_documents_overview(self) -> list[Document]:
        """
        download meta information about all available documents
        """
        documents_response = await self._session.get(f"{self._root_url}/api/documents", timeout=5)
        response_model = ResponseModel.model_validate(documents_response.json())
        return response_model.data

    async def _download_document(self, document:Document)->Path:
        """
        downloads the file related to the given document and returns its path
        """
        format_version = get_edifact_format_version(document.validFrom)
        target_file_name = document.get_meaningful_file_name()
        file_path = Path(format_version)/Path(target_file_name)
        response = await self._session.get(f"{self._root_url}/api/downloadFile/{document.fileId}")
        return file_path


    async def mirror(self)->None:
        """
        Main method of the scraper.
        Downloads all the files and pages and stores them in the filesystem.
        """
        if not self._root_dir.exists() or not self._root_dir.is_dir():
            # we'll raise an error for the root dir, but create sub dirs on the fly
            raise ValueError(f"The path {self._root_dir} is either no directory or does not exist")
        for document in await self.get_documents_overview():
            if not document.isFree:
                _logger.debug("Skipping %s because it's not free", document.title)
                continue

            download_task = self.requests.get("")
