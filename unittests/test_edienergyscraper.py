from pathlib import Path
from typing import List

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup
from freezegun import freeze_time
from maus.edifact import EdifactFormatVersion

from edi_energy_scraper import (
    EdiEnergyScraper,
    Epoch,
    get_edifact_format_version_range_from_filename,
    get_edifact_version_from_filename,
)


class TestEdiEnergyScraper:
    """
    A class to test the EdiEnergyScraper.
    """

    @pytest.mark.parametrize(
        "epoch,str_epoch",
        [
            pytest.param(Epoch.CURRENT, "current"),
            pytest.param(Epoch.FUTURE, "future"),
            pytest.param(Epoch.PAST, "past"),
        ],
    )
    def test_epoch_stringify(self, epoch: Epoch, str_epoch: str):
        actual = str(epoch)
        assert actual == str_epoch

    def test_instantiation(self):
        """
        Tests, that the constructor works.
        """
        instance = EdiEnergyScraper(root_url="https://my_url.de/")
        assert not instance._root_url.endswith("/")

    @pytest.mark.datafiles(
        "./unittests/testfiles/index_20210208.html",
    )
    async def test_index_retrieval(self, datafiles):
        """
        Tests that the landing page is downloaded correctly
        """
        with open(datafiles / "index_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        assert "<!--" in response_body  # original response contains comments, will be removed
        with aioresponses() as mock:
            mock.get("https://www.my_root_url.test", body=response_body)
            ees = EdiEnergyScraper("https://www.my_root_url.test")
            actual_soup = await ees.get_index()
        actual_html = actual_soup.prettify()
        assert "<!--" not in actual_html, "comments should be ignored/removed"
        assert "Startseite: BDEW Forum Datenformate" in actual_html, "content should be returned"

    async def test_get_soup(self, mocker):
        """
        Some links on edi-energy.de are relative. The call of _get_soup should automatically resolve the absolute
        URL of a page if only the relative URL is given.
        """
        ees = EdiEnergyScraper(root_url="https://my_favourite_website.inv/")
        self.has_been_called_correctly = False  # this is not the nicest test setup but hey. it's late.

        async def _request_get_sideffect(*args, **kwargs):
            assert args[0] == "https://my_favourite_website.inv/some_relative_path"
            self.has_been_called_correctly = True

        ees.requests.get = _request_get_sideffect
        try:
            await ees._get_soup(url="/some_relative_path")
        except AttributeError:
            pass
        assert self.has_been_called_correctly  # that's all we care for in this test.

    @pytest.mark.datafiles(
        "./unittests/testfiles/index_20210208.html",
    )
    async def test_dokumente_link(self, datafiles):
        """
        Tests that the "Dokumente" link is extracted from the downloaded landing page.
        """
        with open(datafiles / "index_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        with aioresponses() as mock:
            mock.get("https://www.edi-energy.de", body=response_body)
            ees = EdiEnergyScraper("https://www.edi-energy.de")
            actual_link = ees.get_documents_page_link(await ees.get_index())
        assert actual_link == "https://www.edi-energy.de/index.php?id=38"

    @pytest.mark.datafiles(
        "./unittests/testfiles/dokumente_20210208.html",
    )
    def test_epoch_links_extraction(self, datafiles):
        """
        Tests that the links to past/current/future documents overview pages are extracted.
        """
        with open(datafiles / "dokumente_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_links(soup)
        assert len(actual.keys()) == 3
        assert (
            actual[Epoch.CURRENT]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=now&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=5d1142e54d8f3a1913af8e4cc56c71b2"
        )
        assert (
            actual[Epoch.PAST]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=archive&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=6dd9d237ef46f6eebe2f4ef385528382"
        )
        assert (
            actual[Epoch.FUTURE]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=future&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=325de212fe24061e83e018a2223e6185"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/future_20210210.html",
    )
    def test_epoch_file_map_future_20210210(self, datafiles):
        with open(datafiles / "future_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 76
        for file_basename in actual.keys():
            # all the future names should contain 99991231 as "valid to" date
            assert "_99991231_" in file_basename
        assert (
            actual["UTILMDAHBWiM3.1bKonsolidierteLesefassungmitFehlerkorrekturenStand18.12.2020_99991231_20210401"]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Buid%5D=1000&tx_bdew_bdew%5Baction%5D=download&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=dbf7d932028aa2059c96b25a684d02ed"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/current_20210210.html",
    )
    def test_epoch_file_map_current_20210210(self, datafiles):
        with open(datafiles / "current_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 81
        for file_basename in actual.keys():
            # all the current documents are either "open" or valid until April 2021
            assert "_99991231_" in file_basename or "_20210331_" in file_basename
        assert (
            actual["QUOTESMIG1.1aKonsolidierteLesefassungmitFehlerkorrekturenStand15.07.2019_20210331_20191201"]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Buid%5D=738&tx_bdew_bdew%5Baction%5D=download&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=f01ed973e9947ccf6b91181c93cd2a28"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/past_20210210.html",
    )
    def test_epoch_file_map_past_20210210(self, datafiles):
        with open(datafiles / "past_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 705

    @pytest.mark.parametrize(
        "file_name, expected_file_name",
        [
            pytest.param(
                "example_ahb.pdf",
                "my_favourite_ahb_20240327_20240327.pdf",
                id="pdf",
            ),
            pytest.param(
                "Aenderungsantrag_EBD.xlsx",
                "my_favourite_ahb_20240327_20240327.xlsx",
                id="xlsx",
            ),
        ],
    )
    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/Aenderungsantrag_EBD.xlsx",
    )
    async def test_file_download_file_does_not_exists_yet(
        self,
        mocker,
        tmpdir_factory,
        datafiles,
        file_name,
        expected_file_name,
    ):
        """
        Tests that a file can be downloaded and is stored if it does not exist before.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir")
        ees_dir.mkdir("future")

        isfile_mocker = mocker.patch("edi_energy_scraper.os.path.isfile", return_value=False)
        with open(datafiles / file_name, "rb") as pdf_file:
            # Note that we do _not_ use pdf_file.read() here but provide the requests_mocker with a file handle.
            # Otherwise, you'd run into a "ValueError: Unable to determine whether fp is closed."
            # docs: https://requests-mock.readthedocs.io/en/latest/response.html?highlight=file#registering-responses
            with aioresponses() as mock:
                mock.get(
                    "https://my_file_link.inv/foo_bar",
                    body=pdf_file.read(),
                    headers={"Content-Disposition": f"attachment; filename={file_name}"},
                )
                ees = EdiEnergyScraper(
                    "https://my_file_link.inv/",
                    path_to_mirror_directory=ees_dir,
                )
                await ees._download_and_save_pdf(file_basename="my_favourite_ahb_20240327_20240327", link="foo_bar")
        assert (ees_dir / "FV2310" / expected_file_name).exists()
        isfile_mocker.assert_called_once_with(ees_dir / "FV2310" / expected_file_name)

    @pytest.mark.parametrize(
        "metadata_has_changed",
        [
            pytest.param(
                True,
                id="metadata changed",
            ),
            pytest.param(
                False,
                id="metadata not changed",
            ),
        ],
    )
    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
    )
    async def test_pdf_download_pdf_exists_already(
        self,
        mocker,
        tmpdir_factory,
        datafiles,
        metadata_has_changed: bool,
    ):
        """
        Tests that a PDF can be downloaded and is stored iff the metadata has changed.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir")
        ees_dir.mkdir("future")

        isfile_mocker = mocker.patch("edi_energy_scraper.os.path.isfile", return_value=True)
        metadata_mocker = mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper._have_different_metadata",
            return_value=metadata_has_changed,
        )
        remove_mocker = mocker.patch("edi_energy_scraper.os.remove")

        with open(datafiles / "example_ahb.pdf", "rb") as pdf_file:
            # Note that we do _not_ use pdf_file.read() here but provide the requests_mocker with a file handle.
            # Otherwise, you'd run into a "ValueError: Unable to determine whether fp is closed."
            # docs: https://requests-mock.readthedocs.io/en/latest/response.html?highlight=file#registering-responses
            with aioresponses() as mock:
                mock.get(
                    "https://my_file_link.inv/foo_bar.pdf",
                    body=pdf_file.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                ees = EdiEnergyScraper(
                    "https://my_file_link.inv/",
                    path_to_mirror_directory=ees_dir,
                )
                await ees._download_and_save_pdf(file_basename="my_favourite_ahb_20240327_20240327", link="foo_bar.pdf")
        assert (ees_dir / "FV2310/my_favourite_ahb_20240327_20240327.pdf").exists() == metadata_has_changed
        isfile_mocker.assert_called_once_with(ees_dir / "FV2310/my_favourite_ahb_20240327_20240327.pdf")
        metadata_mocker.assert_called_once()

        if metadata_has_changed:
            remove_mocker.assert_called_once_with((ees_dir / "FV2310/my_favourite_ahb_20240327_20240327.pdf"))

    @staticmethod
    def _get_soup_mocker(*args, **kwargs):
        if args[0] == "current.html":
            with open("./unittests/testfiles/current_20210210.html", "r", encoding="utf8") as infile_current:
                response_body = infile_current.read()
        elif args[0] == "past.html":
            with open("./unittests/testfiles/past_20210210.html", "r", encoding="utf8") as infile_past:
                response_body = infile_past.read()
        elif args[0] == "future.html":
            with open("./unittests/testfiles/future_20210210.html", "r", encoding="utf8") as infile_future:
                response_body = infile_future.read()
        elif args[0] == "https://www.edi-energy.de":
            with open("./unittests/testfiles/index_20210208.html", "r", encoding="utf8") as infile_index:
                response_body = infile_index.read()
        elif args[0] == "https://www.edi-energy.de/index.php?id=38":
            with open("./unittests/testfiles/dokumente_20210208.html", "r", encoding="utf8") as infile_docs:
                response_body = infile_docs.read()
        else:
            raise NotImplementedError(f"The soup for {args[0]} is not implemented in this test.")
        soup = BeautifulSoup(response_body, "html.parser")
        return soup

    @staticmethod
    def _get_efm_mocker(*args, **kwargs):
        heading = args[0].find("h2").text
        if heading == "Aktuell gültige Dokumente":
            return {"xyz_20240327_20240327": "/a_current_ahb.pdf"}
        if heading == "Zukünftige Dokumente":
            return {"def_20240327_20240327": "/a_future_ahb.xlsx"}
        if heading == "Archivierte Dokumente":
            return {"abc_20240327_20240327": "/a_past_ahb.pdf"}
        raise NotImplementedError(f"The case '{heading}' is not implemented in this test.")

    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/example_ahb_2.pdf",
    )
    def test_have_different_metadata(self, datafiles):
        """Tests the function _have_different_metadata."""
        test_file = datafiles / "example_ahb.pdf"

        # Test that metadata of the same pdf returns same metadata
        with open(test_file, "rb") as same_pdf:
            has_changed = EdiEnergyScraper._have_different_metadata(same_pdf.read(), test_file)
            assert not has_changed

        # Test that metadata of a different pdf returns different metadata
        with open(datafiles / "example_ahb_2.pdf", "rb") as different_pdf:
            has_changed = EdiEnergyScraper._have_different_metadata(different_pdf.read(), test_file)
            assert has_changed

    def test_remove_no_longer_online_files(self, mocker):
        """Tests function remove_no_longer_online_files."""
        ees = EdiEnergyScraper(
            path_to_mirror_directory=Path("unittests/testfiles/removetest"),
        )
        assert (
            ees._root_dir / "future_20210210.html"
        ).exists()  # in general html wont be removed by the function under test
        path_example_ahb = ees._get_file_path("example_ahb_20240327.pdf")
        path_example_ahb_2 = ees._get_file_path("example_ahb_2_20240327.pdf")

        # Verify remove called
        remove_mocker = mocker.patch("edi_energy_scraper.os.remove")
        test_files_online = {path_example_ahb}
        ees.remove_no_longer_online_files(test_files_online)
        remove_mocker.assert_called_once_with(path_example_ahb_2)

        # Test nothing to remove
        remove_mocker_2 = mocker.patch("edi_energy_scraper.os.remove")
        test_files_online.add(path_example_ahb_2)
        ees.remove_no_longer_online_files(test_files_online)
        remove_mocker_2.assert_not_called()  # this also asserts that the lonely html file in removetest is not removed

    @pytest.mark.parametrize(
        "headers, file_basename, expected_file_name",
        [
            pytest.param(
                {"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                "my_favourite_ahb_20240327",
                "my_favourite_ahb_20240327.pdf",
                id="pdf",
            ),
            pytest.param(
                {"Content-Disposition": 'attachment; filename="antrag.xlsx"'},
                "my_favourite_ahb_20240327",
                "my_favourite_ahb_20240327.xlsx",
                id="xlsx",
            ),
        ],
    )
    def test_add_file_extension_to_file_basename(self, headers, file_basename, expected_file_name):
        file_name_with_extension = EdiEnergyScraper._add_file_extension_to_file_basename(
            headers=headers, file_basename=file_basename
        )
        assert file_name_with_extension == expected_file_name

    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/Aenderungsantrag_EBD.xlsx",
        "./unittests/testfiles/dokumente_20210208.html",
        "./unittests/testfiles/index_20210208.html",
        "./unittests/testfiles/current_20210210.html",
        "./unittests/testfiles/past_20210210.html",
        "./unittests/testfiles/future_20210210.html",
    )
    async def test_mirroring(self, mocker, tmpdir_factory, datafiles, caplog):
        """
        Tests the overall process and mocks most of the already tested methods.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir_mirror")
        ees_dir.mkdir("future")
        ees_dir.mkdir("current")
        ees_dir.mkdir("past")
        ees_dir = Path(ees_dir)
        remove_no_longer_online_files_mocker = mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.remove_no_longer_online_files"
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.get_epoch_links",
            return_value={
                "current": "current.html",
                "future": "future.html",
                "past": "past.html",
            },
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper._get_soup",
            side_effect=TestEdiEnergyScraper._get_soup_mocker,
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.get_epoch_file_map",
            side_effect=TestEdiEnergyScraper._get_efm_mocker,
        )
        with open(datafiles / "example_ahb.pdf", "rb") as pdf_file_current, open(
            datafiles / "Aenderungsantrag_EBD.xlsx", "rb"
        ) as file_future, open(datafiles / "example_ahb.pdf", "rb") as file_past:
            with aioresponses() as mock:
                mock.get(
                    "https://www.edi-energy.de/a_future_ahb.xlsx",
                    body=file_future.read(),
                    headers={"Content-Disposition": 'attachment; filename="Aenderungsantrag_EBD.xlsx"'},
                )
                mock.get(
                    "https://www.edi-energy.de/a_current_ahb.pdf",
                    body=pdf_file_current.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                mock.get(
                    "https://www.edi-energy.de/a_past_ahb.pdf",
                    body=file_past.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                ees = EdiEnergyScraper(path_to_mirror_directory=ees_dir)
                await ees.mirror()
        assert (ees_dir / "index.html").exists()
        assert (ees_dir / "future.html").exists()
        assert (ees_dir / "current.html").exists()
        assert (ees_dir / "past.html").exists()
        assert (ees_dir / "FV2310" / "def_20240327_20240327.xlsx").exists()
        assert (ees_dir / "FV2310" / "abc_20240327_20240327.pdf").exists()
        assert (ees_dir / "FV2310" / "xyz_20240327_20240327.pdf").exists()

        test_new_file_paths: set = {
            (ees_dir / "FV2310" / "def_20240327_20240327.xlsx"),
            (ees_dir / "FV2310" / "abc_20240327_20240327.pdf"),
            (ees_dir / "FV2310" / "xyz_20240327_20240327.pdf"),
        }
        remove_no_longer_online_files_mocker.assert_called_once_with(test_new_file_paths)
        assert "Downloaded index.html" in caplog.messages

    @pytest.mark.parametrize(
        "input_filename, expected_result",
        [
            pytest.param(
                "APERAKMIG-informatorischeLesefassung2.1h_99991231_20221001.docx",
                EdifactFormatVersion.FV2210,
            ),
            pytest.param("COMDISMIG1.0c_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("CONTRLMIG2.0b_99991231_20221001.pdf", EdifactFormatVersion.FV2210),
            pytest.param(
                "IFTSTAAHB-informatorischeLesefassung2.0e_99991231_20231001.docx", EdifactFormatVersion.FV2310
            ),
            pytest.param("INSRPTAHB1.1g_99991231_20221001.pdf", EdifactFormatVersion.FV2210),
            pytest.param("INVOICMIG2.8b_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("MSCONSAHB3.1c_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("ORDCHGMIG1.1_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("ORDERSMIG1.3_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("ORDRSPMIG1.3_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("PRICATAHB2.0c_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("QUOTESMIG1.3_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("REMADVMIG2.9b_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("REQOTEMIG1.3_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("UTILMDAHBGas1.0a_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("UTILTSAHBBerechnungsformel1.0e_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("APERAKCONTRLAHB2.3m_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("INVOICREMADVAHB2.5b_20240331_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("ORDERSORDRSPAHBMaBiS2.2c_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("REQOTEQUOTESORDERSORDRSPORDCHGAHB2.2_99991231_20231001.pdf", EdifactFormatVersion.FV2310),
            pytest.param("CodelistedereuropäischenLändercodes1.0_99991231_20171001.pdf", EdifactFormatVersion.FV2104),
            pytest.param("CodelistederZeitreihentypen1.1d_99991231_20211001.pdf", EdifactFormatVersion.FV2110),
            pytest.param("KostenblattFB1.0b_99991231_20230401.pdf", EdifactFormatVersion.FV2304),
            pytest.param("PARTINMIG1.0c_20240331_20240403.pdf", EdifactFormatVersion.FV2404),
            pytest.param("PARTINMIG1.0c_20240331_20241001.pdf", EdifactFormatVersion.FV2410),
            pytest.param("PARTINMIG1.0c_20240331_20250401.pdf", EdifactFormatVersion.FV2504),
            pytest.param("PARTINMIG1.0c_20240331_20251001.pdf", EdifactFormatVersion.FV2510),
            pytest.param("IFTSTAMIG2.0e_20240402_20210929.pdf", EdifactFormatVersion.FV2104),  # Before first threshold
            pytest.param(
                "IFTSTAMIG2.0e_20240402_20210930.pdf", EdifactFormatVersion.FV2104
            ),  # Exactly at first threshold
            pytest.param("IFTSTAMIG2.0e_20240402_20211001.pdf", EdifactFormatVersion.FV2110),  # After first threshold
            pytest.param(
                "UTILMDAHBStrom-informatorischeLesefassung1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240402_20231212.docx",
                EdifactFormatVersion.FV2310,
            ),  # docx file
            pytest.param(
                "UTILTSMIG-informatorischeLesefassung1.1b_20240402_20231001.docx",
                EdifactFormatVersion.FV2310,
            ),
            pytest.param("IFTSTAMIG2.0e_20230331_20230331.pdf", EdifactFormatVersion.FV2210),  # At another threshold
            pytest.param("IFTSTAMIG2.0e_20250930_20250930.pdf", EdifactFormatVersion.FV2504),  # Last threshold
            pytest.param("IFTSTAMIG2.0e_20251001_20251001.pdf", EdifactFormatVersion.FV2510),  # After last threshold
            pytest.param(
                "MSCONSAHB-informatorischeLesefassung3.1cKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                EdifactFormatVersion.FV2310,
            ),  # Error in GH Action
        ],
    )
    def test_get_edifact_version_and_formats(self, input_filename: str, expected_result: EdifactFormatVersion):
        """
        Tests the determination of the edifact format and version for given files
        """
        actual = get_edifact_version_from_filename(Path(input_filename))

        assert actual == expected_result

    @freeze_time("2024-06-25")
    @pytest.mark.parametrize(
        "input_filename, expected_result",
        [
            pytest.param(
                "REQOTEQUOTESORDERSORDRSPORDCHGAHB-informatorischeLesefassung2.2_99991231_20231001.docx",
                [
                    EdifactFormatVersion.FV2310,
                    EdifactFormatVersion.FV2404,
                    EdifactFormatVersion.FV2410,
                ],
                id="valid for all format versions from FV2310 to future",
            ),
            pytest.param(
                "REQOTEQUOTESORDERSORDRSPORDCHGAHB-informatorischeLesefassung2.0aKonsolidierteLesefassungmitFehlerkorrekturenStand27.01.2023_20230331_20221001.docx",
                [EdifactFormatVersion.FV2210],
                id="valid for one format versions",
            ),
            pytest.param(
                "IFTSTAMIG2.0e_20240930_20231001.pdf",
                [EdifactFormatVersion.FV2310, EdifactFormatVersion.FV2404],
                id="valid for two format versions",
            ),
            pytest.param(
                "IFTSTAMIG2.0e_20280930_20231001.pdf",
                [EdifactFormatVersion.FV2310, EdifactFormatVersion.FV2404, EdifactFormatVersion.FV2410],
                id="valid in future, starting in past",
            ),
            pytest.param(
                "IFTSTAMIG2.0e_20280930_20250404.pdf",
                [EdifactFormatVersion.FV2504],
                id="starting in future",
            ),
        ],
    )
    def test_get_edifact_format_version_range(self, input_filename: str, expected_result: List[EdifactFormatVersion]):
        """
        Tests the determination of the edifact  version for given files
        """

        actual = get_edifact_format_version_range_from_filename(path=Path(input_filename))

        assert actual == expected_result
