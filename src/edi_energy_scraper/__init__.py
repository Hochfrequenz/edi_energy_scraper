"""
A module to scrape data from edi-energy.de.
"""

import asyncio
import datetime
import io
import itertools
import logging
import os
import re
from email.message import Message
from pathlib import Path
from random import randint
from typing import Awaitable, Dict, List, Optional, Set, Union

import aiohttp
import pytz
from aiohttp import ServerDisconnectedError
from aiohttp_requests import Requests  # type:ignore[import]
from bs4 import BeautifulSoup, Comment  # type:ignore[import]
from maus.edifact import EdifactFormat, EdifactFormatVersion, get_edifact_format_version
from pypdf import PdfReader

from edi_energy_scraper.epoch import Epoch

_logger = logging.getLogger("edi_energy_scraper")
_logger.setLevel(logging.DEBUG)


class EdiEnergyScraper:
    """
    A class that uses beautiful soup to extract and download data from edi-energy.de.
    Beautiful soup is a library that makes it easy to scrape information from web pages:
    https://pypi.org/project/beautifulsoup4/
    """

    def __init__(
        self,
        root_url: str = "https://www.edi-energy.de",
        path_to_mirror_directory: Union[Path, str] = Path("edi_energy_de"),
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
        self.timeout = aiohttp.ClientTimeout(total=60 * 15)  # 15min per epoch (1 asyncio.gather)
        self.tcp_connector = aiohttp.TCPConnector(
            limit_per_host=connection_limit,
        )
        self.requests = Requests(connector=self.tcp_connector)

    async def _get_soup(self, url: str) -> BeautifulSoup:
        """
        Downloads the given absolute URL, parses it as html, removes the comments and returns the soup.
        """
        if not url.startswith("http"):
            url = f"{self._root_url}/{url.strip('/')}"  # remove trailing slashes from relative link
        response = await self.requests.get(url, timeout=5)
        soup = BeautifulSoup(await response.text(), "html.parser")
        EdiEnergyScraper.remove_comments(soup)
        return soup

    async def _download_and_save_pdf(self, file_basename: str, link: str) -> List[Path]:
        """
        Downloads a PDF file from a given link and stores it under the file name in a folder that has the same name
        as the directory if the pdf does not exist yet or if the metadata has changed since the last download.
        Returns the path to the downloaded pdf.
        """
        if not link.startswith("http"):
            link = f"{self._root_url}/{link.strip('/')}"  # remove trailing slashes from relative link

        _logger.debug("Download %s", link)
        for number_of_tries in range(5, 0, -1):
            try:
                response = await self.requests.get(link, timeout=self.timeout)
                break
            except (asyncio.TimeoutError, ServerDisconnectedError):
                _logger.warning("Timeout while downloading '%s' (%s)", link, file_basename)
                if number_of_tries <= 0:
                    _logger.exception(
                        "Too many timeouts while downloading '%s' (%s)", link, file_basename, exc_info=True
                    )
                    raise
                await asyncio.sleep(delay=randint(8, 16))  # cool down...
        file_name = EdiEnergyScraper._add_file_extension_to_file_basename(
            headers=response.headers, file_basename=file_basename
        )

        for number_of_tries in range(4, 0, -1):
            try:
                response_content = await response.content.read()
                break
            except asyncio.TimeoutError:
                _logger.exception("Timeout while reading content of '%s'", file_name, exc_info=True)
                if number_of_tries <= 0:
                    raise
                await asyncio.sleep(delay=randint(5, 10))  # cool down...

        file_paths = self._get_file_paths(file_name=file_name)
        for file_path in file_paths:
            Path.mkdir(file_path.parent, parents=True, exist_ok=True)

            # Save file if it does not exist yet
            if not os.path.isfile(file_path):
                with open(file_path, "wb+") as outfile:  # pdfs are written as binaries
                    _logger.debug("Saving new PDF %s", file_path)
                    outfile.write(response_content)
                continue

            # First fix, different file types do just the same as before, only with correct file extension
            if not file_name.endswith(".pdf"):
                with open(file_path, "wb+") as outfile:
                    _logger.debug("Saving %s", file_path)
                    outfile.write(response_content)
                continue

            # Check if metadata has changed
            metadata_has_changed = self._have_different_metadata(response_content, file_path)
            if metadata_has_changed:  # delete old file and replace with new one
                _logger.debug("Metadata for PDF %s changed; Replacing it", file_path)
                os.remove(file_path)
                with open(file_path, "wb+") as outfile:  # pdfs are written as binaries
                    outfile.write(response_content)
            else:
                _logger.debug("Meta data haven't changed for %s", file_path)
        return file_paths

    def _get_file_path(self, file_name: str) -> Path:
        if "/" in file_name:
            raise ValueError(f"file names must not contain slashes: '{file_name}'")
        format_version: EdifactFormatVersion = get_edifact_version_from_filename(path=Path(file_name))
        file_path = Path(self._root_dir).joinpath(
            f"{format_version}/{file_name}"  # e.g "{root_dir}/future/ahbmabis_99991231_20210401.pdf"
        )

        return file_path

    def _get_file_paths(self, file_name: str) -> List[Path]:
        """
        Returns a list of file paths for all valid format versions of a given file.
        """

        file_paths = []

        format_version_range = get_edifact_format_version_range_from_filename(path=Path(file_name))

        for format_version in format_version_range:
            file_path = Path(self._root_dir).joinpath(
                f"{format_version}/{file_name}"  # e.g "{root_dir}/FV2310/ahbmabis_99991231_20210401.pdf"
            )
            file_paths.append(file_path)

        return file_paths

    @staticmethod
    def _add_file_extension_to_file_basename(headers: dict, file_basename: str) -> str:
        """Extracts the extension of a file from a response header and add it to the file basename."""
        content_disposition = headers["Content-Disposition"]
        params = Message()
        params["content-type"] = content_disposition
        file_extension = Path(str(params.get_param("filename"))).suffix
        file_name = file_basename + file_extension

        return file_name

    @staticmethod
    def _have_different_metadata(data_new_file: bytes, path_to_old_file: Path) -> bool:
        """
        Compares the metadata of two pdf files.
        :param data_new_file: bytes from response.content
        :param path_to_old_file: str

        :return: bool, if metadata of the two pdf files are different or if at least one of the files is encrypted.

        """
        pdf_new = PdfReader(io.BytesIO(data_new_file))
        if pdf_new.is_encrypted:
            return True
        pdf_new_metadata = pdf_new.metadata

        with open(path_to_old_file, "rb") as file_old:
            pdf_old = PdfReader(file_old)
            if pdf_old.is_encrypted:
                return True
            pdf_old_metadata = pdf_old.metadata

        metadata_has_changed: bool = pdf_new_metadata != pdf_old_metadata

        return metadata_has_changed

    async def get_index(self) -> BeautifulSoup:
        """
        Downloads the root url and returns the soup.
        """
        # As the landing page is usually called "index.html/php/..." this method is named index.
        return await self._get_soup(self._root_url)

    @staticmethod
    def remove_comments(soup):
        """
        Removes thes HTML comments from the given soup.
        """
        for html_comment in soup.findAll(string=lambda text: isinstance(text, Comment)):
            html_comment.extract()

    def get_documents_page_link(self, index_soup) -> str:
        """
        Extracts the links for the "Dokumente" from a given index soup.
        """
        # HTML links look like this <a href="url">...</a>; That's why we search for "a"
        documents_link = index_soup.find("a", {"title": "Dokumente"})
        if not documents_link:
            raise ValueError('The soup did not contain a link called "Dokumente".')
        documents_url = documents_link.attrs["href"]
        if not documents_url.startswith("http"):
            documents_url = self._root_url + documents_link.attrs["href"]
        return documents_url

    # a dictionary that maps link titles to short names.
    _docs_texts: Dict[str, Epoch] = {
        "Aktuell gültige Dokumente": Epoch.CURRENT,
        "Zukünftig gültige Dokumente": Epoch.FUTURE,
        "Archivierte Dokumente": Epoch.PAST,
    }

    @staticmethod
    def get_epoch_links(document_soup) -> Dict[Epoch, str]:
        """
        Extract the links to
        * "Aktuell gültige Dokumente"
        * "Zukünftig gültige Dokumente"
        * "Archivierte Dokumente"
        from the "Dokumente" sub page soup.
        """
        result: Dict[Epoch, str] = {}
        for doc_text, doc_epoch in EdiEnergyScraper._docs_texts.items():
            _logger.debug("searching for '%s'", doc_text)
            result[doc_epoch] = document_soup.find("a", string=re.compile(r"\s*" + doc_text + r"\s*")).attrs["href"]
        # result now looks like this:
        # { "past": "link_to_vergangene_dokumente.html", "current": "link_to_active_docs.html", "future": ...}
        # see the unittest
        return result

    @staticmethod
    def get_epoch_file_map(epoch_soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extracts a dictionary from the epoch soup (e.g. soup of "future.html") that maps file basenames as keys
        (e.g. "APERAKCONTRLAHB2.3h_99993112_20210104") to URLs of the documents as value.
        """
        download_table = epoch_soup.find(
            "table", {"class": "table table-responsive table-condensed"}
        )  # a table that contains all the documents
        result: Dict[str, str] = {}
        for table_row in download_table.find_all("tr"):
            table_cells = list(table_row.find_all("td"))
            if len(table_cells) < 4:
                # Not all the rows in the table contain 4 columns. sad but true. Usually it's the header lines.
                # This might be subsections of the table.
                continue
            # The first cell in a row contains a lot of whitespaces and somewhere in between a name.
            # e.g. "   INVOIC / REMADV AHB 2.4 Konsolidierte Lesefassung mit Fehlerkorrekturen Stand: 01.07.2020    "
            # To normalize it, we remove all adjacent occurences of more than 1 whitespaces and replace characters that
            # might cause problems in filenames (e.g. slash)
            # Looking back, this might not be the most readable format to store the files but by keeping it, it's way
            # easier to keep track of a file based history in our git archive.
            doc_name = re.sub(r"\s{2,}", "", table_cells[0].text).replace(":", "").replace(" ", "").replace("/", "")
            # the "Gültig ab" column / publication date is the second column. e.g. "    17.12.2019    "
            # Spoiler: It's not the real publication date. They modify the files once in a while without updating it.
            publication_date = datetime.datetime.strptime(table_cells[1].text.strip(), "%d.%m.%Y")
            try:
                # the "Gültig bis" column / valid to date describes on which date the document becomes legally binding.
                # usually this is something like "   31.03.2020   " or "30.09.2019"
                valid_to_date = datetime.datetime.strptime(table_cells[2].text.strip(), "%d.%m.%Y")
            except ValueError as value_error:
                # there's a special case: "Offen" means the document is valid until further notice.
                if table_cells[2].text.strip() == "Offen":
                    valid_to_date = datetime.datetime(9999, 12, 31)
                else:
                    raise value_error
            # the 4th column contains a download link for the PDF.
            file_link = table_cells[3].find("a").attrs["href"]
            # there was a bug until 2021-02-10 where I used a weird %Y%d%m instead of %Y%m%d format.
            file_basename = f"{doc_name}_{valid_to_date.strftime('%Y%m%d')}_{publication_date.strftime('%Y%m%d')}"
            result[file_basename] = file_link
        return result

    def remove_no_longer_online_files(self, online_files: Set[Path]) -> Set[Path]:
        """
        Removes files that are no longer online. This could be due to being moved to another folder,
        e.g. from future to current.
        :param online_files: set, all the paths to the pdfs that were being downloaded and compared.
        :return: Set[Path], Set of Paths that were removed
        """
        _logger.info("Removing outdated files")
        all_files_in_mirror_dir: Set = set(self._root_dir.glob("**/*.*[!html]"))
        no_longer_online_files = all_files_in_mirror_dir.symmetric_difference(online_files)
        for path in no_longer_online_files:
            _logger.debug("Removing %s which has been removed online", path)
            os.remove(path)

        return no_longer_online_files

    async def _download(
        self, file_basename: str, link: str, optional_success_msg: Optional[str] = None
    ) -> Optional[List[Path]]:
        try:
            file_path = await self._download_and_save_pdf(file_basename=file_basename, link=link)
            if optional_success_msg is not None:
                _logger.debug(optional_success_msg)
        except KeyError as key_error:
            if key_error.args[0].lower() == "content-disposition":
                _logger.exception("Failed to download '%s'", file_basename, exc_info=True)
                # workaround to https://github.com/Hochfrequenz/edi_energy_scraper/issues/31
                return None
            raise
        return file_path

    # pylint:disable=too-many-locals
    async def mirror(self):
        """
        Main method of the scraper. Downloads all the files and pages and stores them in the filesystem
        """
        if not self._root_dir.exists() or not self._root_dir.is_dir():
            # we'll raise an error for the root dir, but create sub dirs on the fly
            raise ValueError(f"The path {self._root_dir} is either no directory or does not exist")
        for _epoch in Epoch:
            epoch_dir = self._root_dir / Path(str(_epoch))
            if not epoch_dir.exists():
                epoch_dir.mkdir(exist_ok=True)
        index_soup = await self.get_index()
        index_path: Path = Path(self._root_dir, "index.html")
        with open(index_path, "w+", encoding="utf8") as outfile:
            # save the index file as html
            _logger.info("Downloaded index.html")
            outfile.write(index_soup.prettify())
        epoch_links = EdiEnergyScraper.get_epoch_links(await self._get_soup(self.get_documents_page_link(index_soup)))
        new_file_paths: Set[Path] = set()
        for _epoch, epoch_link in epoch_links.items():
            _logger.info("Processing %s", _epoch)
            epoch_soup = await self._get_soup(epoch_link)
            epoch_path: Path = Path(self._root_dir, f"{_epoch}.html")  # e.g. "future.html"
            with open(epoch_path, "w+", encoding="utf8") as outfile:
                outfile.write(epoch_soup.prettify())
            file_map = EdiEnergyScraper.get_epoch_file_map(epoch_soup)
            download_tasks: List[Awaitable[Optional[List[Path]]]] = []
            file_counter = itertools.count()
            for file_basename, link in file_map.items():
                download_tasks.append(
                    self._download(
                        file_basename,
                        link,
                        f"Successfully downloaded {_epoch} file {next(file_counter)}/{len(file_map)}",
                    )
                )
            download_results: List[Optional[List[Path]]] = await asyncio.gather(*download_tasks)
            for download_result in download_results:
                if download_result is not None:
                    new_file_paths.update(download_result)
        self.remove_no_longer_online_files(new_file_paths)
        _logger.info("Finished mirroring")


def get_edifact_version_from_filename(path: Path) -> EdifactFormatVersion:
    """
    Determines the edifact formats and the version of a given file.
    A file can describe more than one format (for example APERAK and CONTRL).
    Therefore, a list of all formats described in a file is returned.

    example: 'IFTSTAMIG2.0e_99991231_20231001.pdf' -> FV2310
    """
    filename = path.stem
    date_string = filename.split("_")[-1]  # Assuming date is in the last part of filename
    date_format = "%Y%m%d"
    berlin = pytz.timezone("Europe/Berlin")
    berlin_local_time = datetime.datetime.strptime(date_string, date_format).astimezone(berlin)
    format_version = get_edifact_format_version(berlin_local_time)

    return format_version


def get_publication_date_from_filename(path: Path) -> datetime.datetime:
    """
    Determines the publication date of a given file.
    """
    filename = path.stem
    publication_date_string = filename.split("_")[-1]  # Assuming date is the "publication date"
    date_format = "%Y%m%d"
    berlin = pytz.timezone("Europe/Berlin")
    publication_date = datetime.datetime.strptime(publication_date_string, date_format).astimezone(berlin)

    return publication_date


def get_valid_to_date_from_filename(path: Path) -> datetime.datetime:
    """
    Determines the valid to date of a given file.
    """
    filename = path.stem
    valid_to_date_string = filename.split("_")[-2]  # Assuming date is the "valid to" date

    if valid_to_date_string == "99991231":
        return datetime.datetime(9999, 12, 31, tzinfo=datetime.timezone.utc)

    date_format = "%Y%m%d"
    berlin = pytz.timezone("Europe/Berlin")
    valid_to_date = datetime.datetime.strptime(valid_to_date_string, date_format).astimezone(berlin)

    return valid_to_date


def get_current_format_version() -> EdifactFormatVersion:
    """
    Determines the current format version.
    """
    return get_edifact_format_version(datetime.datetime.now(tz=datetime.timezone.utc))


def get_next_format_version() -> EdifactFormatVersion:
    """
    Determines the next format version.
    """
    current_format_version = get_edifact_format_version(datetime.datetime.now(tz=datetime.timezone.utc))

    format_versions = [efv.value for efv in EdifactFormatVersion]
    next_format_version = format_versions[format_versions.index(current_format_version.value) + 1]

    return EdifactFormatVersion(next_format_version)


def get_edifact_format_version_range_from_filename(path: Path) -> List[EdifactFormatVersion]:
    """
    Determines range of valid format versions of a given file.
    A document can be valid for multiple format versions.
    Therefore, a list of all valid format versions is returned.

    example:
      - 'IFTSTAMIG2.0e_20240930_20231001.pdf' -> [FV2310, FV2404]
      - 'IFTSTAMIG2.0e_99991231_20231001.pdf' -> [FV2310, FV2404, ...]  all future format versions
    """

    publication_date: datetime.datetime = get_publication_date_from_filename(path)
    valid_to_date: datetime.datetime = get_valid_to_date_from_filename(path)

    next_format_version = get_next_format_version()

    format_version_start = get_edifact_format_version(publication_date)

    format_version_end = get_edifact_format_version(valid_to_date)

    is_format_version_end_greater_than_next_format_version = format_version_end > next_format_version
    if is_format_version_end_greater_than_next_format_version:
        format_version_end = next_format_version

    format_versions = [efv.value for efv in EdifactFormatVersion]

    format_version_range = [
        EdifactFormatVersion(format_version)
        for format_version in format_versions[
            format_versions.index(format_version_start.value) : format_versions.index(format_version_end.value) + 1
        ]
    ]

    return format_version_range
